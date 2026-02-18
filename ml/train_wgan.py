#!/usr/bin/env python3
"""
Train WGAN-GP on Pokémon sprites for sharp pixel art generation.

Usage:
    python3 -m ml.train_wgan --epochs 2000 --batch-size 32
"""

import argparse
import time
from pathlib import Path

import torch
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision.utils import save_image
import numpy as np
from PIL import Image

from ml.sprite_dataset import SpriteDataset, COND_DIM
from ml.wgan_gp_model import Generator, Discriminator, compute_gradient_penalty, LATENT_DIM

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPRITES_DIR = PROJECT_ROOT / "Reference" / "pokemondb" / "black-white" / "normal"
POKEMON_DATA = PROJECT_ROOT / "data" / "pokemon_data.json"
CHECKPOINTS_DIR = PROJECT_ROOT / "ml" / "checkpoints_wgan"
SAMPLES_DIR = PROJECT_ROOT / "ml" / "samples_wgan"


def get_device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    elif torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def save_sample_grid(generator, fixed_noise, fixed_cond, epoch, device):
    """Generate and save a grid of samples using fixed noise."""
    generator.eval()
    with torch.no_grad():
        fake_imgs = generator(fixed_noise, fixed_cond)
        
        # Denormalize
        # WGAN output is [-1, 1] (Tanh), so map to [0, 1]
        fake_imgs = (fake_imgs + 1) / 2.0
        
        save_image(fake_imgs, SAMPLES_DIR / f"epoch_{epoch:04d}.png", nrow=8, normalize=False)
    generator.train()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=2000)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=0.0002)
    parser.add_argument("--b1", type=float, default=0.0)  # Adam beta1 0.0 for WGAN
    parser.add_argument("--b2", type=float, default=0.9)  # Adam beta2 0.9
    parser.add_argument("--n-critic", type=int, default=5) # Train D 5 times per G step
    parser.add_argument("--lambda-gp", type=float, default=10.0)
    parser.add_argument("--sample-every", type=int, default=100)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    device = get_device()
    print(f"\n🎨 WGAN-GP Pixel Art Generator — Training")
    print(f"   Device: {device} | Epochs: {args.epochs}")

    # Dataset
    dataset = SpriteDataset(
        sprite_dir=SPRITES_DIR,
        pokemon_data_path=POKEMON_DATA,
        img_size=64,
        augment=True,
        augment_factor=20  # Keep augmentation high
    )
    
    dataloader = DataLoader(
        dataset, 
        batch_size=args.batch_size, 
        shuffle=True, 
        drop_last=True,
        num_workers=0
    )

    # Models
    generator = Generator(LATENT_DIM, COND_DIM).to(device)
    discriminator = Discriminator(COND_DIM).to(device)

    # Optimizers (Adam with beta1=0 is standard for WGAN-GP)
    optimizer_G = optim.Adam(generator.parameters(), lr=args.lr, betas=(args.b1, args.b2))
    optimizer_D = optim.Adam(discriminator.parameters(), lr=args.lr, betas=(args.b1, args.b2))

    # Formatting checkpoints/samples
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    # Fixed noise for consistent sampling
    fixed_noise = torch.randn(64, LATENT_DIM, device=device)
    # Get a fixed batch of conditions from the dataset for visualization consistency
    # We'll just take the first batch's conditions and repeat them if needed
    fixed_cond = next(iter(dataloader))[1][:64].to(device)
    if fixed_cond.size(0) < 64:
        padding = 64 - fixed_cond.size(0)
        fixed_cond = torch.cat([fixed_cond, fixed_cond[:padding]], dim=0)

    start_epoch = 0
    
    # Resume
    if args.resume:
        # Load logic similar to CVAE
        pass 

    print("   Starting training loop...")
    
    for epoch in range(start_epoch, args.epochs):
        for i, (imgs, conds, _) in enumerate(dataloader):
            imgs = imgs.to(device)
            conds = conds.to(device)
            
            # Real images are [0, 1] from dataset, map to [-1, 1] for Tanh
            real_imgs = imgs * 2.0 - 1.0
            
            # ---------------------
            #  Train Discriminator
            # ---------------------
            optimizer_D.zero_grad()
            
            # Sample noise
            z = torch.randn(imgs.size(0), LATENT_DIM, device=device)
            
            # Generate fake images
            fake_imgs = generator(z, conds)
            
            # Real validity
            real_validity = discriminator(real_imgs, conds)
            # Fake validity
            fake_validity = discriminator(fake_imgs.detach(), conds)
            
            # Gradient penalty
            gradient_penalty = compute_gradient_penalty(
                discriminator, real_imgs.data, fake_imgs.data, conds.data, device
            )
            
            # Adversarial loss (Wasserstein)
            d_loss = -torch.mean(real_validity) + torch.mean(fake_validity) + args.lambda_gp * gradient_penalty
            
            d_loss.backward()
            optimizer_D.step()
            
            # -----------------
            #  Train Generator
            # -----------------
            # Train generator every n_critic steps
            if i % args.n_critic == 0:
                optimizer_G.zero_grad()
                
                # Generate new fakes
                fake_imgs = generator(z, conds)
                
                # Loss measures generator's ability to fool the discriminator
                # We want D(fake) to be maximized, so minimize -D(fake)
                fake_validity = discriminator(fake_imgs, conds)
                g_loss = -torch.mean(fake_validity)
                
                g_loss.backward()
                optimizer_G.step()

        # Build progress string
        if epoch % 10 == 0:
            print(
                f"[Epoch {epoch}/{args.epochs}] "
                f"[D loss: {d_loss.item():.4f}] "
                f"[G loss: {g_loss.item():.4f}]"
            )

        if epoch % args.sample_every == 0:
            save_sample_grid(generator, fixed_noise, fixed_cond, epoch, device)
            print(f"    → Saved sample grid: ml/samples_wgan/epoch_{epoch:04d}.png")
            
            # Checkpoint
            torch.save(generator.state_dict(), CHECKPOINTS_DIR / "generator_latest.pt")
            torch.save(discriminator.state_dict(), CHECKPOINTS_DIR / "discriminator_latest.pt")
    
    # Final save
    torch.save(generator.state_dict(), CHECKPOINTS_DIR / "generator_final.pt")
    print("✅ Training complete.")

if __name__ == "__main__":
    main()
