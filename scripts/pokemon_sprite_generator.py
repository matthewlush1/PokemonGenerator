#!/usr/bin/env python3
"""
Pokémon Sprite Generator — Core engine for generating new Pokémon-style sprites.

Provides three generation modes:
1. Palette Swap — Apply one Pokémon's colors onto another's shape
2. Shiny Generation — Create custom "shiny" variants with randomized hue shifts
3. Spritesheet Assembly — Arrange sprites into organized grid sheets

Inspired by David York's GenGam 2016 sprite generator algorithm, adapted for Pokémon.

Usage (via generate.py CLI):
    python generate.py --mode palette-swap --source bulbasaur --palette fire
    python generate.py --mode shiny-gen --source pikachu --count 5
    python generate.py --mode spritesheet --input output/ --cols 12 --rows 8
"""

import colorsys
import json
import os
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image


# ─── Palette Classes ──────────────────────────────────────────────────────────


class PokemonPalette:
    """
    Extracts and stores a color palette from a Pokémon sprite.
    Mirrors the original PaletteSet from the C# codebase but adapted
    for Pokémon-style sprites.
    """

    def __init__(self, image_path: Path = None, colors: list = None):
        self.colors = []  # List of (R, G, B) tuples
        self.ramps = []   # List of color ramps (sorted light→dark groups)

        if image_path:
            self._extract_from_image(image_path)
        elif colors:
            self.colors = [tuple(c) for c in colors]
            self._build_ramps()

    def _extract_from_image(self, image_path: Path):
        """Extract unique non-transparent colors from a sprite."""
        img = Image.open(image_path).convert("RGBA")
        pixels = np.array(img)

        mask = pixels[:, :, 3] >= 128
        opaque = pixels[mask][:, :3]

        seen = set()
        for px in opaque:
            c = tuple(px)
            if c not in seen:
                seen.add(c)
                self.colors.append(c)

        self._build_ramps()

    def _build_ramps(self):
        """Group colors into ramps by hue similarity, sorted by lightness."""
        if not self.colors:
            return

        # Convert to HSL
        color_hsl = []
        for c in self.colors:
            h, l, s = colorsys.rgb_to_hls(c[0]/255, c[1]/255, c[2]/255)
            color_hsl.append((c, h * 360, s * 100, l * 100))

        # Sort by hue
        color_hsl.sort(key=lambda x: x[1])

        # Group by hue proximity (30° tolerance)
        ramps = []
        current = [color_hsl[0]]
        for i in range(1, len(color_hsl)):
            hue_diff = abs(color_hsl[i][1] - current[-1][1])
            if hue_diff > 180:
                hue_diff = 360 - hue_diff
            if hue_diff <= 30:
                current.append(color_hsl[i])
            else:
                ramps.append(current)
                current = [color_hsl[i]]
        ramps.append(current)

        # Sort each ramp by lightness and store
        self.ramps = []
        for ramp in ramps:
            if len(ramp) >= 2:
                ramp.sort(key=lambda x: x[3])  # Sort by lightness
                self.ramps.append([c[0] for c in ramp])


class PaletteSwapper:
    """
    Maps colors from a source palette to a target palette.
    Mirrors the original ImageMerger palette-swap behavior.
    """

    def __init__(self, source_palette: PokemonPalette, target_palette: PokemonPalette):
        self.mapping = {}  # source_color → target_color
        self._build_mapping(source_palette, target_palette)

    def _build_mapping(self, source: PokemonPalette, target: PokemonPalette):
        """Build a color mapping between source and target palettes."""
        # Map ramp-to-ramp: each source ramp maps to a target ramp
        src_ramps = source.ramps
        tgt_ramps = target.ramps

        if not src_ramps or not tgt_ramps:
            return

        # Sort ramps by size (largest first) and pair them
        src_sorted = sorted(src_ramps, key=len, reverse=True)
        tgt_sorted = sorted(tgt_ramps, key=len, reverse=True)

        for i, src_ramp in enumerate(src_sorted):
            tgt_ramp = tgt_sorted[i % len(tgt_sorted)]
            self._map_ramp(src_ramp, tgt_ramp)

    def _map_ramp(self, src_ramp: list, tgt_ramp: list):
        """Map colors from one ramp to another, interpolating if sizes differ."""
        for i, src_color in enumerate(src_ramp):
            # Proportional mapping
            tgt_idx = int(i * (len(tgt_ramp) - 1) / max(len(src_ramp) - 1, 1))
            tgt_idx = min(tgt_idx, len(tgt_ramp) - 1)
            self.mapping[src_color] = tgt_ramp[tgt_idx]

    def swap(self, color: tuple) -> tuple:
        """Get the swapped color, or return original if no mapping exists."""
        return self.mapping.get(color, color)

    def apply_to_image(self, image: Image.Image) -> Image.Image:
        """Apply the palette swap to an entire image."""
        img = image.convert("RGBA")
        pixels = np.array(img)
        result = pixels.copy()

        for src_color, tgt_color in self.mapping.items():
            mask = np.all(pixels[:, :, :3] == src_color, axis=2) & (pixels[:, :, 3] >= 128)
            result[mask, 0] = tgt_color[0]
            result[mask, 1] = tgt_color[1]
            result[mask, 2] = tgt_color[2]

        return Image.fromarray(result)


# ─── Sprite Compositor ────────────────────────────────────────────────────────


class SpriteCompositor:
    """
    Composites sprite layers or applies transformations.
    Mirrors the original ImageMerger for layer compositing.
    """

    @staticmethod
    def merge_layers(layers):
        """Merge multiple sprite layers into one, respecting transparency."""
        if not layers:
            return None

        base = layers[0].copy().convert("RGBA")
        for layer in layers[1:]:
            layer = layer.convert("RGBA")
            base = Image.alpha_composite(base, layer)
        return base

    @staticmethod
    def apply_hue_shift(image: Image.Image, hue_shift: float) -> Image.Image:
        """
        Shift all hues in the image by a given amount (0-360 degrees).
        Used for generating shiny variants.
        """
        img = image.convert("RGBA")
        pixels = np.array(img, dtype=np.float64)

        # Process only non-transparent pixels
        mask = pixels[:, :, 3] >= 128

        for y in range(pixels.shape[0]):
            for x in range(pixels.shape[1]):
                if not mask[y, x]:
                    continue
                r, g, b = pixels[y, x, :3] / 255.0
                h, l, s = colorsys.rgb_to_hls(r, g, b)
                h = (h + hue_shift / 360.0) % 1.0
                r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
                pixels[y, x, 0] = r2 * 255
                pixels[y, x, 1] = g2 * 255
                pixels[y, x, 2] = b2 * 255

        return Image.fromarray(pixels.astype(np.uint8))

    @staticmethod
    def apply_saturation_shift(image: Image.Image, amount: float) -> Image.Image:
        """Shift saturation by a multiplier (e.g., 1.2 = 20% more saturated)."""
        img = image.convert("RGBA")
        pixels = np.array(img, dtype=np.float64)
        mask = pixels[:, :, 3] >= 128

        for y in range(pixels.shape[0]):
            for x in range(pixels.shape[1]):
                if not mask[y, x]:
                    continue
                r, g, b = pixels[y, x, :3] / 255.0
                h, l, s = colorsys.rgb_to_hls(r, g, b)
                s = min(1.0, max(0.0, s * amount))
                r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
                pixels[y, x, 0] = r2 * 255
                pixels[y, x, 1] = g2 * 255
                pixels[y, x, 2] = b2 * 255

        return Image.fromarray(pixels.astype(np.uint8))


# ─── Spritesheet Builder ─────────────────────────────────────────────────────


class SpritesheetBuilder:
    """
    Assembles individual sprites into an organized grid spritesheet.
    Mirrors the original SpritesheetGen from the C# codebase.
    """

    def __init__(self, cols: int = 12, rows: int = 8, padding: int = 3, bg_color=None):
        self.cols = cols
        self.rows = rows
        self.padding = padding
        self.bg_color = bg_color  # None = transparent
        self.sprites = []

    def add_sprite(self, sprite: Image.Image):
        """Add a sprite to the sheet."""
        self.sprites.append(sprite.convert("RGBA"))

    def build(self) -> Image.Image:
        """Build the spritesheet from added sprites."""
        if not self.sprites:
            return None

        # Determine sprite size from first sprite
        sprite_w, sprite_h = self.sprites[0].size

        # Calculate sheet dimensions
        sheet_w = (self.cols * sprite_w) + self.padding * (self.cols + 1)
        sheet_h = (self.rows * sprite_h) + self.padding * (self.rows + 1)

        # Create sheet
        if self.bg_color:
            sheet = Image.new("RGBA", (sheet_w, sheet_h), self.bg_color)
        else:
            sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))

        # Place sprites
        for idx, sprite in enumerate(self.sprites):
            if idx >= self.cols * self.rows:
                break  # Sheet is full

            col = idx % self.cols
            row = idx // self.cols

            x = self.padding + col * (sprite_w + self.padding)
            y = self.padding + row * (sprite_h + self.padding)

            # Resize sprite if needed
            if sprite.size != (sprite_w, sprite_h):
                sprite = sprite.resize((sprite_w, sprite_h), Image.NEAREST)

            sheet.paste(sprite, (x, y), sprite)

        return sheet

    def save(self, output_path: Path):
        """Build and save the spritesheet."""
        sheet = self.build()
        if sheet:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sheet.save(str(output_path))
            print(f"  Spritesheet saved: {output_path} ({sheet.size[0]}×{sheet.size[1]})")


# ─── Generation Modes ─────────────────────────────────────────────────────────


def generate_palette_swap(
    source_path: Path,
    target_palette: PokemonPalette,
    output_path: Path,
) -> Image.Image:
    """Generate a palette-swapped version of a sprite."""
    source_img = Image.open(source_path).convert("RGBA")
    source_palette = PokemonPalette(source_path)

    swapper = PaletteSwapper(source_palette, target_palette)
    result = swapper.apply_to_image(source_img)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(str(output_path))
    return result


def generate_shiny_variant(
    source_path: Path,
    output_path: Path,
    hue_shift: float = None,
    sat_shift: float = None,
) -> Image.Image:
    """Generate a custom 'shiny' variant with randomized color shifts."""
    source_img = Image.open(source_path).convert("RGBA")

    if hue_shift is None:
        hue_shift = random.uniform(30, 330)  # Avoid tiny shifts
    if sat_shift is None:
        sat_shift = random.uniform(0.7, 1.4)

    result = SpriteCompositor.apply_hue_shift(source_img, hue_shift)
    result = SpriteCompositor.apply_saturation_shift(result, sat_shift)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(str(output_path))
    return result


def generate_type_swap(
    source_path: Path,
    target_type: str,
    palette_db_path: Path,
    output_path: Path,
) -> Image.Image:
    """Swap a Pokémon's colors to match a different type's palette."""
    # Load palette database
    with open(palette_db_path) as f:
        db = json.load(f)

    type_data = db.get("type_palettes", {}).get(target_type)
    if not type_data or not type_data.get("ramps"):
        print(f"No palette data for type: {target_type}")
        return None

    # Build target palette from type ramps
    all_colors = []
    for ramp in type_data["ramps"]:
        all_colors.extend([tuple(c) for c in ramp])

    target_palette = PokemonPalette(colors=all_colors)
    return generate_palette_swap(source_path, target_palette, output_path)


def build_spritesheet(
    input_dir: Path,
    output_path: Path,
    cols: int = 12,
    rows: int = 8,
    padding: int = 3,
) -> Image.Image:
    """Build a spritesheet from all PNG sprites in a directory."""
    sprite_files = sorted(input_dir.glob("*.png"))
    if not sprite_files:
        print(f"No sprites found in {input_dir}")
        return None

    builder = SpritesheetBuilder(cols=cols, rows=rows, padding=padding)
    for f in sprite_files[:cols * rows]:
        sprite = Image.open(f)
        builder.add_sprite(sprite)

    builder.save(output_path)
    return builder.build()
