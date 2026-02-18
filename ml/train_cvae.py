#!/usr/bin/env python3
"""
Train the Conditional VAE on Pokémon sprites.

Usage:
    python3 -m ml.train_cvae                    # Default: 500 epochs
    python3 -m ml.train_cvae --epochs 1000      # Longer training
    python3 -m ml.train_cvae --resume            # Resume from checkpoint
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader
from PIL import Image

from ml.sprite_dataset import SpriteDataset, COND_DIM
from ml.cvae_model import ConditionalVAE, vae_loss, LATENT_DIM

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPRITES_DIR = PROJECT_ROOT / "Reference" / "pokemondb" / "black-white" / "normal"
POKEMON_DATA = PROJECT_ROOT / "data" / "pokemon_data.json"
CHECKPOINTS_DIR = PROJECT_ROOT / "ml" / "checkpoints"
SAMPLES_DIR = PROJECT_ROOT / "ml" / "samples"


def get_device():
    """Auto-detect best available device."""
    if torch.backends.mps.is_available():
        return torch.device("mps")
    elif torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def save_sample_grid(model, dataset, device, epoch, num_cols=6):
    """Generate and save a grid of reconstructed + generated sprites."""
    model.eval()
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    images = []

    # Row 1: reconstructions of real sprites
    loader = DataLoader(dataset, batch_size=num_cols, shuffle=True)
    batch = next(iter(loader))
    imgs, conds, names = batch
    imgs, conds = imgs.to(device), conds.to(device)

    with torch.no_grad():
        recon, _, _ = model(imgs, conds)

    # Originals
    for i in range(min(num_cols, imgs.size(0))):
        images.append(tensor_to_pil(imgs[i]))

    # Reconstructions
    for i in range(min(num_cols, recon.size(0))):
        images.append(tensor_to_pil(recon[i]))

    # Row 3: novel generations with same conditions
    with torch.no_grad():
        novel = model.generate(conds, device)
    for i in range(min(num_cols, novel.size(0))):
        images.append(tensor_to_pil(novel[i]))

    # Build grid
    cols = num_cols
    rows = 3
    cell_size = 64
    padding = 2
    grid_w = cols * (cell_size + padding) + padding
    grid_h = rows * (cell_size + padding) + padding
    grid = Image.new("RGBA", (grid_w, grid_h), (20, 20, 30, 255))

    for idx, img in enumerate(images):
        r = idx // cols
        c = idx % cols
        x = c * (cell_size + padding) + padding
        y = r * (cell_size + padding) + padding
        grid.paste(img, (x, y))

    grid.save(SAMPLES_DIR / f"epoch_{epoch:04d}.png")
    model.train()


def tensor_to_pil(tensor):
    """Convert [4, H, W] tensor to RGBA PIL Image."""
    img = tensor.detach().cpu().clamp(0, 1)
    img = (img.permute(1, 2, 0).numpy() * 255).astype(np.uint8)
    return Image.fromarray(img, "RGBA")


def main():
    parser = argparse.ArgumentParser(description="Train CVAE on Pokémon sprites")
    parser.add_argument("--epochs", type=int, default=500)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--latent-dim", type=int, default=LATENT_DIM)
    parser.add_argument("--augment-factor", type=int, default=20)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sample-every", type=int, default=25)
    args = parser.parse_args()

    device = get_device()
    print(f"\n🧠 CVAE Sprite Generator — Training")
    print(f"   Device: {device}")
    print(f"   Epochs: {args.epochs}")
    print(f"   Latent dim: {args.latent_dim}")
    print(f"   Batch size: {args.batch_size}")
    print(f"   LR: {args.lr}")
    print()

    # Dataset
    dataset = SpriteDataset(
        sprite_dir=SPRITES_DIR,
        pokemon_data_path=POKEMON_DATA,
        img_size=64,
        augment=True,
        augment_factor=args.augment_factor,
    )

    if len(dataset) == 0:
        print("❌ No sprites matched to pokemon_data.json!")
        print("   Run: python3 scripts/scrape_pokemondb.py --gen 1 --style black-white")
        return

    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        drop_last=True,
        num_workers=0,
    )

    # Model
    model = ConditionalVAE(latent_dim=args.latent_dim, cond_dim=COND_DIM).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs, eta_min=1e-5
    )

    # Resume from checkpoint
    start_epoch = 0
    best_loss = float("inf")
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

    checkpoint_path = CHECKPOINTS_DIR / "latest.pt"
    if args.resume and checkpoint_path.exists():
        ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model"])
        optimizer.load_state_dict(ckpt["optimizer"])
        start_epoch = ckpt["epoch"] + 1
        best_loss = ckpt.get("best_loss", float("inf"))
        print(f"  Resumed from epoch {start_epoch} (best loss: {best_loss:.4f})")

    param_count = sum(p.numel() for p in model.parameters())
    print(f"  Model params: {param_count:,}")
    print(f"  Training samples: {len(dataset)}")
    print()

    # Training loop
    model.train()
    t_start = time.time()

    for epoch in range(start_epoch, args.epochs):
        epoch_loss = 0
        epoch_metrics = {"recon": 0, "alpha": 0, "kl": 0}
        n_batches = 0

        # KL annealing: ramp up KL weight over first 100 epochs
        kl_weight = min(1.0, epoch / 100.0) * 0.5

        for imgs, conds, names in loader:
            imgs = imgs.to(device)
            conds = conds.to(device)

            recon, mu, logvar = model(imgs, conds)
            loss, metrics = vae_loss(recon, imgs, mu, logvar, kl_weight)

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            epoch_loss += loss.item()
            for k in epoch_metrics:
                epoch_metrics[k] += metrics[k]
            n_batches += 1

        scheduler.step()
        avg_loss = epoch_loss / max(n_batches, 1)

        # Print progress
        if (epoch + 1) % 10 == 0 or epoch == start_epoch:
            elapsed = time.time() - t_start
            avg_m = {k: v / max(n_batches, 1) for k, v in epoch_metrics.items()}
            lr = scheduler.get_last_lr()[0]
            print(
                f"  Epoch {epoch+1:4d}/{args.epochs} │ "
                f"loss: {avg_loss:.4f} │ "
                f"recon: {avg_m['recon']:.4f} │ "
                f"kl: {avg_m['kl']:.4f} │ "
                f"lr: {lr:.2e} │ "
                f"{elapsed:.0f}s"
            )

        # Save samples
        if (epoch + 1) % args.sample_every == 0:
            save_sample_grid(model, dataset, device, epoch + 1)
            print(f"    → Sample grid saved: ml/samples/epoch_{epoch+1:04d}.png")

        # Save checkpoint
        if (epoch + 1) % 50 == 0:
            torch.save({
                "epoch": epoch,
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "best_loss": best_loss,
                "latent_dim": args.latent_dim,
                "cond_dim": COND_DIM,
            }, checkpoint_path)

        # Save best model
        if avg_loss < best_loss:
            best_loss = avg_loss
            torch.save({
                "epoch": epoch,
                "model": model.state_dict(),
                "latent_dim": args.latent_dim,
                "cond_dim": COND_DIM,
            }, CHECKPOINTS_DIR / "best.pt")

    # Final save
    torch.save({
        "epoch": args.epochs - 1,
        "model": model.state_dict(),
        "latent_dim": args.latent_dim,
        "cond_dim": COND_DIM,
    }, CHECKPOINTS_DIR / "final.pt")

    elapsed = time.time() - t_start
    print(f"\n✅ Training complete! ({elapsed:.0f}s)")
    print(f"   Best loss: {best_loss:.4f}")
    print(f"   Checkpoints: {CHECKPOINTS_DIR}")
    print(f"   Samples: {SAMPLES_DIR}")


if __name__ == "__main__":
    main()
