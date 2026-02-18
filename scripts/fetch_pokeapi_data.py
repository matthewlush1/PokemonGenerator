#!/usr/bin/env python3
"""
Fetch rich Pokémon data from PokéAPI and write data/pokemon_data.json.

Usage:
    python3 scripts/fetch_pokeapi_data.py              # All Gen 1 (151)
    python3 scripts/fetch_pokeapi_data.py --limit 10   # First 10 only
"""

import argparse
import json
import time
from pathlib import Path
from typing import Dict, Any

import requests

API_BASE = "https://pokeapi.co/api/v2"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "data" / "pokemon_data.json"

# Body shapes PokéAPI returns → our normalized names
SHAPE_MAP = {
    "ball": "ball",
    "squiggle": "serpentine",
    "fish": "fish",
    "arms": "humanoid",
    "blob": "blob",
    "upright": "bipedal",
    "legs": "bipedal",
    "quadruped": "quadruped",
    "wings": "winged",
    "tentacles": "tentacles",
    "heads": "multi-head",
    "humanoid": "humanoid",
    "bug-wings": "winged",
    "armor": "armored",
}

# Abilities/types that imply movement capabilities
FLY_INDICATORS = {"flying"}
SWIM_INDICATORS = {"water"}
DIG_INDICATORS = {"ground"}
LEVITATE_ABILITIES = {"levitate"}


def fetch_json(url: str, retries: int = 3) -> Dict[str, Any]:
    """Fetch JSON from URL with retries and rate limiting."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as e:
            if attempt < retries - 1:
                time.sleep(1.0 * (attempt + 1))
            else:
                raise RuntimeError(f"Failed to fetch {url}: {e}")


def derive_movement(types: list, abilities: list) -> Dict[str, Any]:
    """Derive movement capabilities from type and ability data."""
    type_set = set(types)
    ability_set = set(a.lower() for a in abilities)

    can_fly = bool(type_set & FLY_INDICATORS)
    can_swim = bool(type_set & SWIM_INDICATORS)
    can_dig = bool(type_set & DIG_INDICATORS)
    grounded = not (can_fly or bool(ability_set & LEVITATE_ABILITIES))

    return {
        "grounded": grounded,
        "can_fly": can_fly,
        "can_swim": can_swim,
        "can_dig": can_dig,
    }


def fetch_pokemon(pokemon_id: int) -> Dict[str, Any]:
    """Fetch all characteristic data for a single Pokémon."""
    # Main pokemon endpoint: stats, abilities, height, weight
    poke = fetch_json(f"{API_BASE}/pokemon/{pokemon_id}")
    # Species endpoint: shape, egg groups, genus, habitat
    species = fetch_json(f"{API_BASE}/pokemon-species/{pokemon_id}")

    # Extract name
    name = poke["name"]

    # Extract types
    types = [t["type"]["name"] for t in sorted(poke["types"], key=lambda t: t["slot"])]

    # Extract base stats
    stat_map = {}
    STAT_KEYS = {"hp": "hp", "attack": "atk", "defense": "def",
                 "special-attack": "spa", "special-defense": "spd", "speed": "spe"}
    for s in poke["stats"]:
        key = STAT_KEYS.get(s["stat"]["name"])
        if key:
            stat_map[key] = s["base_stat"]

    # Extract abilities
    abilities = []
    hidden_ability = None
    for a in poke["abilities"]:
        aname = a["ability"]["name"]
        if a["is_hidden"]:
            hidden_ability = aname
        else:
            abilities.append(aname)

    # Extract body shape
    shape_raw = species.get("shape", {})
    shape_name = shape_raw.get("name", "unknown") if shape_raw else "unknown"
    body_style = SHAPE_MAP.get(shape_name, shape_name)

    # Extract species category (genus)
    species_category = ""
    for g in species.get("genera", []):
        if g["language"]["name"] == "en":
            species_category = g["genus"]
            break

    # Extract egg groups
    egg_groups = [eg["name"] for eg in species.get("egg_groups", [])]

    # Height (dm → m) and weight (hg → kg)
    height = poke["height"] / 10.0
    weight = poke["weight"] / 10.0

    # Generation — PokéAPI returns e.g. "generation-i", "generation-ii"
    gen_name = species.get("generation", {}).get("name", "")
    gen_roman = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
                 "vi": 6, "vii": 7, "viii": 8, "ix": 9}
    gen_suffix = gen_name.split("-")[-1] if gen_name else ""
    gen = gen_roman.get(gen_suffix, 1)

    # Derive movement
    all_abilities = abilities + ([hidden_ability] if hidden_ability else [])
    movement = derive_movement(types, all_abilities)

    return {
        name: {
            "id": pokemon_id,
            "types": types,
            "gen": gen,
            "species": species_category,
            "body_style": body_style,
            "height": height,
            "weight": weight,
            "base_stats": stat_map,
            "abilities": abilities,
            "hidden_ability": hidden_ability,
            "egg_groups": egg_groups,
            "movement": movement,
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch Pokémon data from PokéAPI")
    parser.add_argument("--limit", type=int, default=151,
                        help="Number of Pokémon to fetch (default: 151 for Gen 1)")
    parser.add_argument("--start", type=int, default=1,
                        help="Starting Pokémon ID (default: 1)")
    args = parser.parse_args()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data if present
    existing = {}
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            existing = json.load(f)

    end_id = args.start + args.limit
    total = args.limit
    print(f"🔄 Fetching Pokémon #{args.start}–#{end_id - 1} from PokéAPI...")

    for i, pid in enumerate(range(args.start, end_id), 1):
        try:
            data = fetch_pokemon(pid)
            existing.update(data)
            name = list(data.keys())[0]
            print(f"  [{i}/{total}] ✓ {name}")
            # Rate limit: ~1 request per 0.5s (2 reqs per mon)
            time.sleep(0.3)
        except Exception as e:
            print(f"  [{i}/{total}] ✗ ID {pid}: {e}")

    # Write output
    with open(OUTPUT_FILE, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {len(existing)} Pokémon → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
