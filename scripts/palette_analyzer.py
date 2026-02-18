#!/usr/bin/env python3
"""
Palette Analyzer — Extracts and catalogs color palettes from Pokémon sprites.

Scans downloaded sprites, extracts unique colors, groups them into HSL-sorted
color ramps, and tags palettes by Pokémon type. Outputs a palette database
for use by the generator.

Usage:
    python scripts/palette_analyzer.py
    python scripts/palette_analyzer.py --input Reference/pokemondb/black-white/normal/ --limit 10
"""

import argparse
import colorsys
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image
import numpy as np


def extract_colors(image_path, min_alpha=128):
    """Extract all non-transparent unique colors from a sprite image."""
    img = Image.open(image_path).convert("RGBA")
    pixels = np.array(img)

    # Filter out transparent/near-transparent pixels
    mask = pixels[:, :, 3] >= min_alpha
    opaque_pixels = pixels[mask][:, :3]

    # Get unique colors (convert numpy uint8 to plain int)
    unique_colors = set()
    for pixel in opaque_pixels:
        unique_colors.add(tuple(int(v) for v in pixel))

    return list(unique_colors)


def rgb_to_hsl(r, g, b):
    """Convert RGB (0-255) to HSL (0-360, 0-100, 0-100)."""
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    return (h * 360, s * 100, l * 100)


def hsl_to_rgb(h, s, l):
    """Convert HSL (0-360, 0-100, 0-100) to RGB (0-255)."""
    r, g, b = colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
    return (int(r * 255), int(g * 255), int(b * 255))


def group_into_ramps(colors, hue_tolerance=30.0):
    """
    Group colors into color ramps based on hue similarity.
    Colors within hue_tolerance degrees are grouped together, then sorted
    by lightness (dark → light) to form a ramp.
    """
    if not colors:
        return []

    # Convert to HSL and sort by hue
    color_hsl = []
    for c in colors:
        h, s, l = rgb_to_hsl(*c)
        color_hsl.append((c, h, s, l))

    # Sort by hue
    color_hsl.sort(key=lambda x: x[1])

    # Group by hue proximity
    ramps = []
    current_ramp = [color_hsl[0]]

    for i in range(1, len(color_hsl)):
        curr = color_hsl[i]
        prev = current_ramp[-1]

        hue_diff = abs(curr[1] - prev[1])
        # Handle hue wraparound (e.g., 350° and 10°)
        if hue_diff > 180:
            hue_diff = 360 - hue_diff

        if hue_diff <= hue_tolerance:
            current_ramp.append(curr)
        else:
            ramps.append(current_ramp)
            current_ramp = [curr]

    ramps.append(current_ramp)

    # Sort each ramp by lightness (dark → light) and extract RGB
    sorted_ramps = []
    for ramp in ramps:
        if len(ramp) < 2:
            continue  # Skip single-color "ramps"
        ramp.sort(key=lambda x: x[3])  # Sort by lightness
        sorted_ramps.append([c[0] for c in ramp])

    return sorted_ramps


def get_dominant_colors(colors, image_path, top_n=10):
    """Get the most frequently occurring colors in a sprite."""
    img = Image.open(image_path).convert("RGBA")
    pixels = np.array(img)

    # Filter transparent
    mask = pixels[:, :, 3] >= 128
    opaque = pixels[mask][:, :3]

    counter = Counter()
    for pixel in opaque:
        counter[tuple(int(v) for v in pixel)] += 1

    return counter.most_common(top_n)


def analyze_sprite(image_path: Path) -> dict:
    """Analyze a single sprite and return its palette data."""
    colors = extract_colors(image_path)
    if not colors:
        return None

    ramps = group_into_ramps(colors)
    dominant = get_dominant_colors(colors, image_path)

    # Calculate average hue for type classification
    hsl_values = [rgb_to_hsl(*c) for c in colors]
    avg_hue = sum(h for h, s, l in hsl_values) / len(hsl_values) if hsl_values else 0
    avg_sat = sum(s for h, s, l in hsl_values) / len(hsl_values) if hsl_values else 0
    avg_light = sum(l for h, s, l in hsl_values) / len(hsl_values) if hsl_values else 0

    return {
        "file": str(image_path.name),
        "total_colors": len(colors),
        "color_ramps": [
            [list(c) for c in ramp]
            for ramp in ramps
        ],
        "dominant_colors": [
            {"color": list(c), "count": count}
            for c, count in dominant
        ],
        "avg_hue": round(avg_hue, 1),
        "avg_saturation": round(avg_sat, 1),
        "avg_lightness": round(avg_light, 1),
    }


def build_type_palettes(
    palette_entries: dict,
    pokemon_types: dict,
) -> dict:
    """
    Build aggregated palettes grouped by Pokémon type.
    This creates "type ramps" — characteristic color progressions for each type.
    """
    type_colors = defaultdict(list)

    for name, data in palette_entries.items():
        if name not in pokemon_types:
            continue
        types = pokemon_types[name].get("types", [])
        for t in types:
            for ramp in data.get("color_ramps", []):
                type_colors[t].extend(ramp)

    # For each type, re-group all collected colors into ramps
    type_palettes = {}
    for ptype, colors in type_colors.items():
        unique_colors = list(set(tuple(c) if isinstance(c, list) else c for c in colors))
        ramps = group_into_ramps(unique_colors, hue_tolerance=20)
        # Keep only the largest ramps (most representative)
        ramps.sort(key=len, reverse=True)
        type_palettes[ptype] = {
            "total_colors": len(unique_colors),
            "ramps": [
                [list(c) for c in ramp]
                for ramp in ramps[:5]  # Top 5 ramps per type
            ],
        }

    return type_palettes


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Pokémon sprite palettes"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Input directory of sprites to analyze",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of sprites to analyze",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file path",
    )

    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    input_dir = Path(args.input) if args.input else project_root / "Reference" / "pokemondb" / "black-white" / "normal"
    output_file = Path(args.output) if args.output else project_root / "Reference" / "palettes" / "palette_db.json"

    # Load Pokémon types
    types_file = project_root / "data" / "pokemon_types.json"
    pokemon_types = {}
    if types_file.exists():
        with open(types_file) as f:
            pokemon_types = json.load(f)

    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        print("Run the scraper first: python scripts/scrape_pokemondb.py --limit 10")
        sys.exit(1)

    # Find all sprite images
    sprite_files = sorted(input_dir.glob("*.png"))
    if args.limit:
        sprite_files = sprite_files[:args.limit]

    if not sprite_files:
        print(f"No .png files found in {input_dir}")
        sys.exit(1)

    print(f"Analyzing {len(sprite_files)} sprites from {input_dir}...\n")

    # Analyze each sprite
    palette_entries = {}
    for i, sprite_path in enumerate(sprite_files):
        name = sprite_path.stem  # Filename without extension
        data = analyze_sprite(sprite_path)
        if data:
            palette_entries[name] = data
            print(f"  [{i+1}/{len(sprite_files)}] {name}: {data['total_colors']} colors, {len(data['color_ramps'])} ramps")

    # Build type-aggregated palettes
    type_palettes = build_type_palettes(palette_entries, pokemon_types)

    # Save output
    output_data = {
        "metadata": {
            "source_dir": str(input_dir),
            "total_sprites": len(palette_entries),
        },
        "sprites": palette_entries,
        "type_palettes": type_palettes,
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n✓ Palette database saved to {output_file}")
    print(f"  {len(palette_entries)} sprite palettes")
    print(f"  {len(type_palettes)} type palettes: {', '.join(sorted(type_palettes.keys()))}")


if __name__ == "__main__":
    main()
