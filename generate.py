#!/usr/bin/env python3
"""
Pokémon Sprite Generator — CLI Entry Point

Unified command-line interface for all sprite generation modes:
  - palette-swap: Apply one Pokémon's colors onto another's shape
  - type-swap:    Recolor a sprite to match a Pokémon type's palette
  - shiny-gen:    Generate custom shiny variants with hue/saturation shifts
  - spritesheet:  Assemble sprites into organized grid sheets
  - batch-shiny:  Generate multiple shinies for all sprites in a directory

Usage:
    python generate.py --mode palette-swap --source bulbasaur --target charmander
    python generate.py --mode type-swap --source bulbasaur --type fire
    python generate.py --mode shiny-gen --source pikachu --count 5
    python generate.py --mode spritesheet --input output/ --cols 12 --rows 8
    python generate.py --mode batch-shiny --input Reference/pokemondb/black-white/normal/ --count 3
"""

import argparse
import json
import random
import sys
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from pokemon_sprite_generator import (
    PokemonPalette,
    generate_palette_swap,
    generate_shiny_variant,
    generate_type_swap,
    build_spritesheet,
)


def find_sprite(name: str, sprites_dir: Path) -> Path:
    """Find a sprite file by Pokémon name in the sprites directory."""
    # Try direct match
    direct = sprites_dir / f"{name}.png"
    if direct.exists():
        return direct

    # Try in subdirectories
    for subdir in sprites_dir.iterdir():
        if subdir.is_dir():
            candidate = subdir / f"{name}.png"
            if candidate.exists():
                return candidate

    # Search recursively
    matches = list(sprites_dir.rglob(f"{name}.png"))
    if matches:
        return matches[0]

    return None


def cmd_palette_swap(args, project_root: Path):
    """Handle palette-swap mode."""
    sprites_dir = project_root / "Reference" / "pokemondb" / "black-white" / "normal"
    output_dir = Path(args.output) if args.output else project_root / "output" / "palette_swaps"

    source_path = find_sprite(args.source, sprites_dir)
    if not source_path:
        print(f"Source sprite not found: {args.source}")
        print(f"  Looked in: {sprites_dir}")
        sys.exit(1)

    target_path = find_sprite(args.target, sprites_dir)
    if not target_path:
        print(f"Target sprite not found: {args.target}")
        sys.exit(1)

    target_palette = PokemonPalette(target_path)
    out_path = output_dir / f"{args.source}_as_{args.target}.png"

    print(f"Palette swap: {args.source} → {args.target}'s colors")
    result = generate_palette_swap(source_path, target_palette, out_path)
    print(f"✓ Saved: {out_path}")


def cmd_type_swap(args, project_root: Path):
    """Handle type-swap mode."""
    sprites_dir = project_root / "Reference" / "pokemondb" / "black-white" / "normal"
    output_dir = Path(args.output) if args.output else project_root / "output" / "type_swaps"
    palette_db = project_root / "Reference" / "palettes" / "palette_db.json"

    source_path = find_sprite(args.source, sprites_dir)
    if not source_path:
        print(f"Source sprite not found: {args.source}")
        sys.exit(1)

    if not palette_db.exists():
        print(f"Palette database not found: {palette_db}")
        print("Run palette analyzer first: python scripts/palette_analyzer.py")
        sys.exit(1)

    out_path = output_dir / f"{args.source}_type_{args.type}.png"

    print(f"Type swap: {args.source} → {args.type} type palette")
    result = generate_type_swap(source_path, args.type, palette_db, out_path)
    if result:
        print(f"✓ Saved: {out_path}")


def cmd_shiny_gen(args, project_root: Path):
    """Handle shiny-gen mode."""
    sprites_dir = project_root / "Reference" / "pokemondb" / "black-white" / "normal"
    output_dir = Path(args.output) if args.output else project_root / "output" / "shinies"

    source_path = find_sprite(args.source, sprites_dir)
    if not source_path:
        print(f"Source sprite not found: {args.source}")
        sys.exit(1)

    count = args.count or 1
    print(f"Generating {count} shiny variant(s) of {args.source}...")

    for i in range(count):
        hue = random.uniform(30, 330)
        sat = random.uniform(0.7, 1.4)
        out_path = output_dir / f"{args.source}_shiny_{i+1}.png"
        generate_shiny_variant(source_path, out_path, hue_shift=hue, sat_shift=sat)
        print(f"  [{i+1}/{count}] Hue shift: {hue:.0f}°, Sat: {sat:.2f}x → {out_path.name}")

    print(f"✓ {count} shinies saved to: {output_dir}")


def cmd_batch_shiny(args, project_root: Path):
    """Handle batch-shiny mode — generate shinies for all sprites in a directory."""
    input_dir = Path(args.input) if args.input else project_root / "Reference" / "pokemondb" / "black-white" / "normal"
    output_dir = Path(args.output) if args.output else project_root / "output" / "batch_shinies"

    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        sys.exit(1)

    sprite_files = sorted(input_dir.glob("*.png"))
    if not sprite_files:
        print(f"No .png files in {input_dir}")
        sys.exit(1)

    count = args.count or 1
    total = len(sprite_files)

    print(f"Generating {count} shiny variant(s) each for {total} sprites...")

    for i, sprite_path in enumerate(sprite_files):
        name = sprite_path.stem
        for j in range(count):
            hue = random.uniform(30, 330)
            sat = random.uniform(0.7, 1.4)
            out_path = output_dir / f"{name}_shiny_{j+1}.png"
            generate_shiny_variant(sprite_path, out_path, hue_shift=hue, sat_shift=sat)

        pct = ((i + 1) / total) * 100
        print(f"  [{i+1}/{total}] {pct:.0f}% — {name}")

    print(f"✓ Done! {total * count} shinies saved to: {output_dir}")


def cmd_spritesheet(args, project_root: Path):
    """Handle spritesheet mode."""
    input_dir = Path(args.input) if args.input else project_root / "output"
    output_path = Path(args.output) if args.output else project_root / "output" / "spritesheet.png"

    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        sys.exit(1)

    cols = args.cols or 12
    rows = args.rows or 8

    print(f"Building {cols}×{rows} spritesheet from {input_dir}...")
    result = build_spritesheet(input_dir, output_path, cols=cols, rows=rows)
    if result:
        print(f"✓ Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Pokémon Sprite Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate.py --mode palette-swap --source bulbasaur --target charmander
  python generate.py --mode type-swap --source pikachu --type water
  python generate.py --mode shiny-gen --source eevee --count 10
  python generate.py --mode batch-shiny --input Reference/pokemondb/black-white/normal/ --count 3
  python generate.py --mode spritesheet --input output/shinies/ --cols 10 --rows 5
        """,
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["palette-swap", "type-swap", "shiny-gen", "batch-shiny", "spritesheet"],
        help="Generation mode",
    )
    parser.add_argument("--source", help="Source Pokémon name (for swap/shiny modes)")
    parser.add_argument("--target", help="Target Pokémon name (for palette-swap mode)")
    parser.add_argument("--type", help="Target Pokémon type (for type-swap mode)")
    parser.add_argument("--input", help="Input directory (for batch/spritesheet modes)")
    parser.add_argument("--output", help="Output path")
    parser.add_argument("--count", type=int, help="Number of variants to generate")
    parser.add_argument("--cols", type=int, help="Spritesheet columns")
    parser.add_argument("--rows", type=int, help="Spritesheet rows")

    args = parser.parse_args()
    project_root = Path(__file__).resolve().parent

    mode_handlers = {
        "palette-swap": cmd_palette_swap,
        "type-swap": cmd_type_swap,
        "shiny-gen": cmd_shiny_gen,
        "batch-shiny": cmd_batch_shiny,
        "spritesheet": cmd_spritesheet,
    }

    handler = mode_handlers.get(args.mode)
    if handler:
        handler(args, project_root)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
