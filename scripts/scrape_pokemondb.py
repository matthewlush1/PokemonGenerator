#!/usr/bin/env python3
"""
Scrape Pokémon sprites from pokemondb.net.

Downloads standard pixel-art sprites organized by game style and variant type.
Uses polite scraping with delays between requests.

Requires Python 3.9+.

Usage:
    python scripts/scrape_pokemondb.py --style black-white --gen 1 --limit 10
    python scripts/scrape_pokemondb.py --style black-white --types normal shiny
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Base URLs
SPRITE_INDEX_URL = "https://pokemondb.net/sprites"
IMG_BASE_URL = "https://img.pokemondb.net/sprites"

# Available game styles (pixel-art focused)
GAME_STYLES = [
    "red-blue", "yellow", "gold", "silver", "crystal",
    "ruby-sapphire", "emerald", "firered-leafgreen",
    "diamond-pearl", "platinum", "heartgold-soulsilver",
    "black-white",  # Best pixel art, 96x96, recommended default
]

# Sprite variant types
VARIANT_TYPES = ["normal", "shiny"]

# Animated variants (Gen 5 Black/White only)
ANIM_TYPES = ["anim/normal", "anim/shiny"]

# Generation ranges (Pokédex numbers)
GEN_RANGES = {
    1: (1, 151),
    2: (152, 251),
    3: (252, 386),
    4: (387, 493),
    5: (494, 649),
}

# Headers for polite scraping
HEADERS = {
    "User-Agent": "SpriteGenerator-Research/1.0 (educational project)",
    "Accept": "image/png, image/gif, */*",
}

REQUEST_DELAY = 0.5  # seconds between requests


def load_pokemon_names(data_dir: Path) -> dict:
    """Load Pokémon data from pokemon_data.json."""
    data_file = data_dir / "pokemon_data.json"
    if data_file.exists():
        with open(data_file) as f:
            try:
                debug_data = json.load(f)
                # Map name -> info
                # The json is {name: {id: 1, ...}}
                return debug_data
            except:
                pass
    return {}


def scrape_pokemon_list(gen=None):
    """Scrape the list of Pokémon names from pokemondb.net/sprites."""
    print(f"Fetching Pokémon list from {SPRITE_INDEX_URL}...")
    resp = requests.get(SPRITE_INDEX_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    names = []

    # Find all Pokémon links in the sprite index
    for link in soup.select("a[href^='/sprites/']"):
        href = link.get("href", "")
        # Extract name from /sprites/{name}
        parts = href.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "sprites":
            name = parts[1]
            if name and name not in names:
                names.append(name)

    print(f"Found {len(names)} Pokémon")
    return names


def filter_by_gen(names, pokemon_db, gen):
    """Filter Pokémon names by generation using the type database."""
    if not gen:
        return names

    filtered = []
    for name in names:
        info = pokemon_db.get(name, {})
        if info.get("gen") == gen:
            filtered.append(name)

    # If we didn't match many from the DB, fall back to Pokédex range
    if len(filtered) < 10 and gen in GEN_RANGES:
        start, end = GEN_RANGES[gen]
        filtered = []
        for name in names:
            info = pokemon_db.get(name, {})
            pid = info.get("id", 0)
            if start <= pid <= end:
                filtered.append(name)

    print(f"Filtered to {len(filtered)} Pokémon for Gen {gen}")
    return filtered


def download_sprite(url: str, output_path: Path, retries: int = 3) -> bool:
    """Download a single sprite image with retry logic."""
    if output_path.exists():
        return True  # Already downloaded

    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(resp.content)
                return True
            elif resp.status_code == 404:
                return False  # Not available
            else:
                print(f"  HTTP {resp.status_code} for {url}, retry {attempt + 1}")
        except requests.RequestException as e:
            print(f"  Error: {e}, retry {attempt + 1}")
        time.sleep(REQUEST_DELAY)

    return False


def scrape_sprites(
    names,
    style,
    types,
    output_dir,
    include_anim=False,
    limit=None,
):
    """Download sprites for all specified Pokémon."""
    if limit:
        names = names[:limit]

    total = len(names)
    downloaded = 0
    skipped = 0
    failed = 0

    all_types = list(types)
    if include_anim and style == "black-white":
        all_types.extend(ANIM_TYPES)

    print(f"\nDownloading {total} Pokémon × {len(all_types)} variants = {total * len(all_types)} sprites")
    print(f"Style: {style}")
    print(f"Output: {output_dir}\n")

    for i, name in enumerate(names):
        for variant in all_types:
            # Build URL and output path
            ext = ".gif" if "anim" in variant else ".png"
            url = f"{IMG_BASE_URL}/{style}/{variant}/{name}{ext}"
            out_path = output_dir / style / variant / f"{name}{ext}"

            if out_path.exists():
                skipped += 1
                continue

            success = download_sprite(url, out_path)
            if success:
                downloaded += 1
            else:
                failed += 1

            time.sleep(REQUEST_DELAY)

        # Progress update
        pct = ((i + 1) / total) * 100
        print(f"  [{i+1}/{total}] {pct:.0f}% — {name} (↓{downloaded} ⊘{skipped} ✗{failed})")

    print(f"\n✓ Done! Downloaded: {downloaded}, Skipped: {skipped}, Failed: {failed}")
    print(f"  Sprites saved to: {output_dir / style}")


def main():
    parser = argparse.ArgumentParser(
        description="Download Pokémon sprites from pokemondb.net"
    )
    parser.add_argument(
        "--style",
        default="black-white",
        choices=GAME_STYLES,
        help="Game style for sprites (default: black-white)",
    )
    parser.add_argument(
        "--gen",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Limit to a specific generation",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        default=["normal", "shiny"],
        help="Sprite variant types to download (default: normal shiny)",
    )
    parser.add_argument(
        "--anim",
        action="store_true",
        help="Also download animated sprites (Black/White only)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of Pokémon to download",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory (default: Reference/pokemondb/)",
    )

    args = parser.parse_args()

    # Resolve paths
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"
    output_dir = Path(args.output) if args.output else project_root / "Reference" / "pokemondb"

    # Load Pokémon database
    pokemon_db = load_pokemon_names(data_dir)

    # Get list of Pokémon
    names = scrape_pokemon_list(args.gen)

    # Filter by generation if specified
    if args.gen:
        names = filter_by_gen(names, pokemon_db, args.gen)

    if not names:
        print("No Pokémon found to download!")
        sys.exit(1)

    # Download sprites
    scrape_sprites(
        names=names,
        style=args.style,
        types=args.types,
        output_dir=output_dir,
        include_anim=args.anim,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
