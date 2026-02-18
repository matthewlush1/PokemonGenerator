"""
Pokémon Sprite Dataset — loads sprites + characteristic conditioning vectors.

Handles data augmentation for small datasets and builds one-hot/normalized
conditioning vectors from pokemon_data.json.
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
from torch.utils.data import Dataset
from PIL import Image, ImageEnhance, ImageFilter
import torchvision.transforms.functional as TF


# ─── Constants ────────────────────────────────────────────────────────────────

ALL_TYPES = [
    "normal", "fire", "water", "grass", "electric", "ice",
    "fighting", "poison", "ground", "flying", "psychic", "bug",
    "rock", "ghost", "dragon", "dark", "steel", "fairy",
]
TYPE_TO_IDX = {t: i for i, t in enumerate(ALL_TYPES)}

ALL_BODY_STYLES = [
    "quadruped", "bipedal", "humanoid", "serpentine", "winged",
    "fish", "blob", "ball", "tentacles", "multi-head", "armored",
]
BODY_TO_IDX = {b: i for i, b in enumerate(ALL_BODY_STYLES)}

STAT_KEYS = ["hp", "atk", "def", "spa", "spd", "spe"]
MAX_STAT = 255.0
MAX_HEIGHT = 15.0  # log scale
MAX_WEIGHT = 1000.0  # log scale

COND_DIM = len(ALL_TYPES) * 2 + len(ALL_BODY_STYLES) + len(STAT_KEYS) + 2  # 56


# ─── Conditioning Vector Builder ─────────────────────────────────────────────


def build_condition_vector(pokemon_data: dict) -> np.ndarray:
    """Build a 56-dim conditioning vector from Pokémon characteristics."""
    vec = np.zeros(COND_DIM, dtype=np.float32)
    offset = 0

    # Type 1 one-hot (18 dims)
    types = pokemon_data.get("types", [])
    if len(types) >= 1:
        idx = TYPE_TO_IDX.get(types[0], 0)
        vec[offset + idx] = 1.0
    offset += len(ALL_TYPES)

    # Type 2 one-hot (18 dims) — zeros if single-type
    if len(types) >= 2:
        idx = TYPE_TO_IDX.get(types[1], 0)
        vec[offset + idx] = 1.0
    offset += len(ALL_TYPES)

    # Body style one-hot (11 dims)
    body = pokemon_data.get("body_style", "bipedal")
    idx = BODY_TO_IDX.get(body, 0)
    vec[offset + idx] = 1.0
    offset += len(ALL_BODY_STYLES)

    # Base stats normalized (6 dims)
    stats = pokemon_data.get("base_stats", {})
    for key in STAT_KEYS:
        vec[offset] = stats.get(key, 50) / MAX_STAT
        offset += 1

    # Height (log-normalized)
    height = pokemon_data.get("height", 1.0)
    vec[offset] = np.log1p(height) / np.log1p(MAX_HEIGHT)
    offset += 1

    # Weight (log-normalized)
    weight = pokemon_data.get("weight", 10.0)
    vec[offset] = np.log1p(weight) / np.log1p(MAX_WEIGHT)
    offset += 1

    return vec


# ─── Dataset ─────────────────────────────────────────────────────────────────


class SpriteDataset(Dataset):
    """Pokémon sprite dataset with conditioning vectors and augmentation."""

    def __init__(
        self,
        sprite_dir: Path,
        pokemon_data_path: Path,
        img_size: int = 64,
        augment: bool = True,
        augment_factor: int = 20,
    ):
        self.img_size = img_size
        self.augment = augment
        self.augment_factor = augment_factor

        # Load Pokémon data
        with open(pokemon_data_path) as f:
            self.pokemon_db = json.load(f)

        # Find matching sprites
        self.samples: List[Tuple[Path, str]] = []
        sprite_dir = Path(sprite_dir)

        for sprite_path in sorted(sprite_dir.glob("*.png")):
            name = sprite_path.stem.lower().replace("-", "")
            # Try exact match, then fuzzy match
            matched_name = None
            if name in self.pokemon_db:
                matched_name = name
            else:
                # Try without hyphens in DB keys too
                for db_name in self.pokemon_db:
                    if db_name.replace("-", "") == name:
                        matched_name = db_name
                        break

            if matched_name:
                self.samples.append((sprite_path, matched_name))

        print(f"  Dataset: {len(self.samples)} sprites matched to data"
              f" (augment ×{augment_factor if augment else 1}"
              f" → {len(self)} effective samples)")

    def __len__(self):
        if self.augment:
            return len(self.samples) * self.augment_factor
        return len(self.samples)

    def _load_sprite(self, path: Path) -> Image.Image:
        """Load and resize a sprite to target size."""
        img = Image.open(path).convert("RGBA")
        # Resize with nearest-neighbor to preserve pixel art
        img = img.resize((self.img_size, self.img_size), Image.NEAREST)
        return img

    def _augment_sprite(self, img: Image.Image) -> Image.Image:
        """Apply random augmentation to a sprite."""
        # Random horizontal flip
        if random.random() > 0.5:
            img = TF.hflip(img)

        # Small random rotation (±8°)
        angle = random.uniform(-8, 8)
        img = img.rotate(angle, resample=Image.NEAREST, expand=False,
                         fillcolor=(0, 0, 0, 0))

        # Small random translation (±4 px)
        dx = random.randint(-4, 4)
        dy = random.randint(-4, 4)
        if dx != 0 or dy != 0:
            from PIL import ImageChops
            # Split into channels, shift, merge
            channels = list(img.split())
            shifted = [ImageChops.offset(c, dx, dy) for c in channels]
            img = Image.merge("RGBA", shifted)

        # Random color jitter on RGB channels only
        if random.random() > 0.3:
            r, g, b, a = img.split()
            rgb = Image.merge("RGB", (r, g, b))

            # Brightness
            rgb = ImageEnhance.Brightness(rgb).enhance(random.uniform(0.85, 1.15))
            # Saturation
            rgb = ImageEnhance.Color(rgb).enhance(random.uniform(0.8, 1.3))
            # Contrast
            rgb = ImageEnhance.Contrast(rgb).enhance(random.uniform(0.9, 1.1))

            r, g, b = rgb.split()
            img = Image.merge("RGBA", (r, g, b, a))

        return img

    def _img_to_tensor(self, img: Image.Image) -> torch.Tensor:
        """Convert RGBA image to float tensor [4, H, W] in range [0, 1]."""
        arr = np.array(img, dtype=np.float32) / 255.0  # [H, W, 4]
        tensor = torch.from_numpy(arr).permute(2, 0, 1)  # [4, H, W]
        return tensor

    def __getitem__(self, idx):
        # Map augmented index back to base sample
        base_idx = idx % len(self.samples)
        path, name = self.samples[base_idx]

        # Load sprite
        img = self._load_sprite(path)

        # Augment if not the first copy (keep one clean)
        if self.augment and (idx // len(self.samples)) > 0:
            img = self._augment_sprite(img)

        # Convert to tensor
        img_tensor = self._img_to_tensor(img)

        # Build conditioning vector
        poke_data = self.pokemon_db[name]
        cond_vec = build_condition_vector(poke_data)
        cond_tensor = torch.from_numpy(cond_vec)

        return img_tensor, cond_tensor, name
