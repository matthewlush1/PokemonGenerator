#!/usr/bin/env python3
"""
Scrape Pokémon Mystery Dungeon sprites from PMDCollab's SpriteCollab GitHub repo.

Downloads animated sprite sheets (Walk, Attack, Idle, etc.) from the open-source
PMDCollab repository. These sprites include multi-directional animation frames.

Usage:
    python scripts/scrape_pmdcollab.py --limit 10
    python scripts/scrape_pmdcollab.py --animations Walk Idle Attack --limit 50
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

# PMDCollab GitHub raw URLs
TRACKER_URL = "https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/tracker.json"
SPRITE_BASE_URL = "https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/sprite"
PORTRAIT_BASE_URL = "https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/portrait"

# Common animation types available in PMD sprites
ALL_ANIMATIONS = [
    "Walk", "Idle", "Attack", "Shoot", "Strike", "Swing",
    "Sleep", "Hurt", "Charge", "Hop", "Double", "Rotate",
    "Twirl",
]

# Default animations to download (most useful)
DEFAULT_ANIMATIONS = ["Walk", "Idle", "Attack", "Sleep", "Hurt"]

HEADERS = {
    "User-Agent": "SpriteGenerator-Research/1.0 (educational project)",
}

REQUEST_DELAY = 0.3  # seconds between requests


def fetch_tracker() -> dict:
    """Fetch the PMDCollab tracker.json which indexes all available sprites."""
    print(f"Fetching tracker from {TRACKER_URL}...")
    resp = requests.get(TRACKER_URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    tracker = resp.json()
    print(f"Tracker loaded: {len(tracker)} entries")
    return tracker


def get_available_pokemon(tracker, limit=None):
    """Extract Pokémon entries that have available sprite files."""
    pokemon_list = []

    for poke_id, data in tracker.items():
        # Skip entries without sprite files
        sprite_files = data.get("sprite_files", {})
        if not sprite_files:
            continue

        # Skip if not complete enough
        sprite_complete = data.get("sprite_complete", 0)
        if sprite_complete < 1:
            continue

        name = data.get("name", f"unknown_{poke_id}")

        pokemon_list.append({
            "id": poke_id,
            "name": name,
            "sprite_files": sprite_files,
            "portrait_files": data.get("portrait_files", {}),
        })

    # Sort by ID (padded string sort works for zero-padded IDs)
    pokemon_list.sort(key=lambda x: x["id"])

    if limit:
        pokemon_list = pokemon_list[:limit]

    print(f"Found {len(pokemon_list)} Pokémon with available sprites")
    return pokemon_list


def download_file(url: str, output_path: Path, retries: int = 3) -> bool:
    """Download a file with retry logic."""
    if output_path.exists():
        return True

    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(resp.content)
                return True
            elif resp.status_code == 404:
                return False
            else:
                print(f"  HTTP {resp.status_code} for {url}")
        except requests.RequestException as e:
            print(f"  Error: {e}, retry {attempt + 1}")
        time.sleep(REQUEST_DELAY)

    return False


def download_sprites(
    pokemon_list,
    animations,
    output_dir,
    include_portraits=True,
):
    """Download sprite animation sheets and portraits for each Pokémon."""
    total = len(pokemon_list)
    total_downloaded = 0
    total_skipped = 0
    total_failed = 0

    print(f"\nDownloading sprites for {total} Pokémon")
    print(f"Animations: {', '.join(animations)}")
    print(f"Output: {output_dir}\n")

    for i, poke in enumerate(pokemon_list):
        poke_id = poke["id"]
        name = poke["name"]
        sprite_files = poke["sprite_files"]
        safe_name = name.replace(" ", "_").replace("/", "_")
        poke_dir = output_dir / f"{poke_id}_{safe_name}"

        # Download animation sprite sheets
        for anim in animations:
            if anim not in sprite_files:
                continue

            # Animation sheets are named like {Animation}-Anim.png
            url = f"{SPRITE_BASE_URL}/{poke_id}/{anim}-Anim.png"
            out_path = poke_dir / "sprites" / f"{anim}-Anim.png"

            if out_path.exists():
                total_skipped += 1
                continue

            success = download_file(url, out_path)
            if success:
                total_downloaded += 1
            else:
                # Try without -Anim suffix
                url_alt = f"{SPRITE_BASE_URL}/{poke_id}/{anim}.png"
                success = download_file(url_alt, out_path)
                if success:
                    total_downloaded += 1
                else:
                    total_failed += 1

            time.sleep(REQUEST_DELAY)

        # Download portrait (Normal expression)
        if include_portraits:
            portrait_files = poke.get("portrait_files", {})
            if "Normal" in portrait_files:
                url = f"{PORTRAIT_BASE_URL}/{poke_id}/Normal.png"
                out_path = poke_dir / "portraits" / "Normal.png"

                if out_path.exists():
                    total_skipped += 1
                else:
                    success = download_file(url, out_path)
                    if success:
                        total_downloaded += 1
                    else:
                        total_failed += 1
                    time.sleep(REQUEST_DELAY)

        # Progress
        pct = ((i + 1) / total) * 100
        print(f"  [{i+1}/{total}] {pct:.0f}% — {name} (↓{total_downloaded} ⊘{total_skipped} ✗{total_failed})")

    print(f"\n✓ Done! Downloaded: {total_downloaded}, Skipped: {total_skipped}, Failed: {total_failed}")
    print(f"  Sprites saved to: {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Download PMD-style sprites from PMDCollab GitHub"
    )
    parser.add_argument(
        "--animations",
        nargs="+",
        default=DEFAULT_ANIMATIONS,
        choices=ALL_ANIMATIONS,
        help=f"Animation types to download (default: {' '.join(DEFAULT_ANIMATIONS)})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of Pokémon to download",
    )
    parser.add_argument(
        "--no-portraits",
        action="store_true",
        help="Skip downloading portrait images",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory (default: Reference/pmdcollab/)",
    )

    args = parser.parse_args()

    # Resolve paths
    project_root = Path(__file__).resolve().parent.parent
    output_dir = Path(args.output) if args.output else project_root / "Reference" / "pmdcollab"

    # Fetch tracker
    tracker = fetch_tracker()

    # Get available Pokémon
    pokemon_list = get_available_pokemon(tracker, limit=args.limit)

    if not pokemon_list:
        print("No Pokémon with sprites found!")
        sys.exit(1)

    # Download
    download_sprites(
        pokemon_list=pokemon_list,
        animations=args.animations,
        output_dir=output_dir,
        include_portraits=not args.no_portraits,
    )


if __name__ == "__main__":
    main()
