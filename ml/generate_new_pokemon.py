#!/usr/bin/env python3
"""
Generate new Pokémon sprites from a trained CVAE model.

Usage:
    # Generate a fire-type quadruped with high attack
    python3 -m ml.generate_new_pokemon --type1 fire --body quadruped --atk 130

    # Generate with full stat control
    python3 -m ml.generate_new_pokemon --type1 water --type2 ice --body serpentine \\
        --hp 100 --atk 80 --def 90 --spa 120 --spd 100 --spe 85

    # Generate multiple variants
    python3 -m ml.generate_new_pokemon --type1 dragon --count 6 --output dragon_set.png
"""

import argparse
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from ml.sprite_dataset import (
    ALL_TYPES, TYPE_TO_IDX, ALL_BODY_STYLES, BODY_TO_IDX,
    STAT_KEYS, COND_DIM, MAX_STAT, MAX_HEIGHT, MAX_WEIGHT,
)
from ml.cvae_model import ConditionalVAE, LATENT_DIM

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHECKPOINTS_DIR = PROJECT_ROOT / "ml" / "checkpoints"
OUTPUT_DIR = PROJECT_ROOT / "output" / "ml_generated"


def build_custom_condition(
    type1="fire", type2=None, body_style="bipedal",
    hp=80, atk=80, defense=80, spa=80, spd=80, spe=80,
    height=1.0, weight=20.0
):
    """Build a conditioning vector from user-specified characteristics."""
    vec = np.zeros(COND_DIM, dtype=np.float32)
    offset = 0

    # Type 1
    idx = TYPE_TO_IDX.get(type1, 0)
    vec[offset + idx] = 1.0
    offset += len(ALL_TYPES)

    # Type 2
    if type2 and type2 in TYPE_TO_IDX:
        idx = TYPE_TO_IDX[type2]
        vec[offset + idx] = 1.0
    offset += len(ALL_TYPES)

    # Body style
    idx = BODY_TO_IDX.get(body_style, 0)
    vec[offset + idx] = 1.0
    offset += len(ALL_BODY_STYLES)

    # Stats
    stats = [hp, atk, defense, spa, spd, spe]
    for val in stats:
        vec[offset] = val / MAX_STAT
        offset += 1

    # Height & weight
    vec[offset] = np.log1p(height) / np.log1p(MAX_HEIGHT)
    offset += 1
    vec[offset] = np.log1p(weight) / np.log1p(MAX_WEIGHT)

    return torch.from_numpy(vec)


def post_process_sprite(img_tensor, num_colors=16, upscale=4):
    """Post-process a generated sprite for pixel-art crispness.

    1. Color quantization (limit palette)
    2. Alpha threshold (remove semi-transparent fringe)
    3. Nearest-neighbor upscale for display
    """
    # Convert tensor to PIL
    img = img_tensor.detach().cpu().clamp(0, 1)
    img = (img.permute(1, 2, 0).numpy() * 255).astype(np.uint8)
    img = Image.fromarray(img, "RGBA")

    # Alpha threshold: remove semi-transparent pixels
    r, g, b, a = img.split()
    a = a.point(lambda p: 255 if p > 100 else 0)
    img = Image.merge("RGBA", (r, g, b, a))

    # Color quantization on RGB (keep alpha separate)
    rgb = Image.merge("RGB", (r, g, b))
    rgb_q = rgb.quantize(colors=num_colors, method=Image.Quantize.MEDIANCUT)
    rgb_q = rgb_q.convert("RGB")
    r2, g2, b2 = rgb_q.split()
    img = Image.merge("RGBA", (r2, g2, b2, a))

    # Upscale with nearest neighbor
    if upscale > 1:
        w, h = img.size
        img = img.resize((w * upscale, h * upscale), Image.NEAREST)

    return img


def generate_sprites(model, cond_vec, device, count=1):
    """Generate multiple sprites with different latent samples."""
    model.eval()
    results = []

    with torch.no_grad():
        for _ in range(count):
            z = torch.randn(1, model.latent_dim).to(device)
            c = cond_vec.unsqueeze(0).to(device)
            raw = model.decoder(z, c)
            results.append(raw[0])

    return results


def build_grid(sprites, cols=6, padding=4, bg_color=(20, 20, 30, 255)):
    """Build a grid image from a list of PIL sprites."""
    if not sprites:
        return None

    w, h = sprites[0].size
    rows = (len(sprites) + cols - 1) // cols
    grid_w = cols * (w + padding) + padding
    grid_h = rows * (h + padding) + padding
    grid = Image.new("RGBA", (grid_w, grid_h), bg_color)

    for idx, sprite in enumerate(sprites):
        r = idx // cols
        c = idx % cols
        x = c * (w + padding) + padding
        y = r * (h + padding) + padding
        grid.paste(sprite, (x, y))

    return grid


def main():
    parser = argparse.ArgumentParser(description="Generate new Pokémon sprites")
    parser.add_argument("--type1", default="fire", choices=ALL_TYPES)
    parser.add_argument("--type2", default=None, choices=ALL_TYPES)
    parser.add_argument("--body", default="bipedal", choices=ALL_BODY_STYLES)
    parser.add_argument("--hp", type=int, default=80)
    parser.add_argument("--atk", type=int, default=80)
    parser.add_argument("--def", dest="defense", type=int, default=80)
    parser.add_argument("--spa", type=int, default=80)
    parser.add_argument("--spd", type=int, default=80)
    parser.add_argument("--spe", type=int, default=80)
    parser.add_argument("--height", type=float, default=1.0)
    parser.add_argument("--weight", type=float, default=20.0)
    parser.add_argument("--count", type=int, default=6)
    parser.add_argument("--colors", type=int, default=16)
    parser.add_argument("--upscale", type=int, default=4)
    parser.add_argument("--checkpoint", default="best.pt")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    # Device
    if torch.backends.mps.is_available():
        device = torch.device("mps")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")

    # Load model
    ckpt_path = CHECKPOINTS_DIR / args.checkpoint
    if not ckpt_path.exists():
        print(f"❌ No checkpoint found at {ckpt_path}")
        print("   Train first: python3 -m ml.train_cvae")
        return

    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    model = ConditionalVAE(
        latent_dim=ckpt.get("latent_dim", LATENT_DIM),
        cond_dim=ckpt.get("cond_dim", COND_DIM),
    ).to(device)
    model.load_state_dict(ckpt["model"])
    print(f"✅ Loaded model from epoch {ckpt.get('epoch', '?')}")

    # Build condition
    cond = build_custom_condition(
        type1=args.type1, type2=args.type2, body_style=args.body,
        hp=args.hp, atk=args.atk, defense=args.defense,
        spa=args.spa, spd=args.spd, spe=args.spe,
        height=args.height, weight=args.weight,
    )

    print(f"🔧 Generating {args.count} sprites:")
    print(f"   Type: {args.type1}" + (f"/{args.type2}" if args.type2 else ""))
    print(f"   Body: {args.body}")
    print(f"   Stats: HP={args.hp} ATK={args.atk} DEF={args.defense} "
          f"SpA={args.spa} SpD={args.spd} SPE={args.spe}")

    # Generate
    raw_sprites = generate_sprites(model, cond, device, count=args.count)

    # Post-process
    processed = [post_process_sprite(s, num_colors=args.colors, upscale=args.upscale)
                 for s in raw_sprites]

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_name = args.output or f"{args.type1}_{'_' + args.type2 if args.type2 else ''}_{args.body}.png"
    output_path = OUTPUT_DIR / output_name

    if args.count == 1:
        processed[0].save(output_path)
    else:
        grid = build_grid(processed, cols=min(args.count, 6))
        grid.save(output_path)

    print(f"\n✅ Saved: {output_path}")


if __name__ == "__main__":
    main()
