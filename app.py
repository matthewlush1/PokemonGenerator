#!/usr/bin/env python3
"""
Pokémon Sprite Generator — Web Frontend (Flask)

A sleek web interface for testing all sprite generation modes:
  - Browse downloaded sprites
  - Generate shiny variants
  - Palette swap between Pokémon
  - Type-swap with color palettes
  - Spritesheet assembly

Run: python3 app.py
Open: http://localhost:5001
"""

import base64
import io
import json
import os
import random
import sys
from pathlib import Path

from flask import Flask, render_template, jsonify, request, send_from_directory
from PIL import Image

# Add scripts to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from pokemon_sprite_generator import (
    PokemonPalette,
    PaletteSwapper,
    SpriteCompositor,
    SpritesheetBuilder,
    StatInfluencer,
    BodyStyleMatcher,
    generate_palette_swap,
    generate_shiny_variant,
    generate_type_swap,
    generate_stat_shiny,
    generate_smart_swap,
    build_spritesheet,
)

app = Flask(__name__, static_folder="web/static", template_folder="web/templates")

PROJECT_ROOT = Path(__file__).resolve().parent
SPRITES_DIR = PROJECT_ROOT / "Reference" / "pokemondb" / "black-white"
OUTPUT_DIR = PROJECT_ROOT / "output"
PALETTE_DB = PROJECT_ROOT / "Reference" / "palettes" / "palette_db.json"
TYPES_DB = PROJECT_ROOT / "data" / "pokemon_types.json"
POKEMON_DATA_FILE = PROJECT_ROOT / "data" / "pokemon_data.json"


def load_pokemon_data():
    """Load the rich pokemon data (V2) or fall back to types-only (V1)."""
    if POKEMON_DATA_FILE.exists():
        with open(POKEMON_DATA_FILE) as f:
            return json.load(f)
    if TYPES_DB.exists():
        with open(TYPES_DB) as f:
            return json.load(f)
    return {}

# Hand-crafted fallback palettes for every type (dark → mid → light ramps)
# Used when the palette DB doesn't yet have data for a given type.
SYNTHETIC_TYPE_PALETTES = {
    "fire":     [(101, 24, 10), (204, 60, 15), (245, 125, 30), (250, 185, 55), (255, 230, 140)],
    "water":    [(15, 40, 100), (30, 80, 180), (50, 130, 220), (100, 180, 240), (170, 220, 255)],
    "grass":    [(20, 75, 20), (40, 130, 40), (75, 185, 60), (130, 210, 90), (190, 240, 150)],
    "electric": [(120, 90, 0), (200, 160, 10), (240, 200, 30), (255, 225, 70), (255, 245, 160)],
    "psychic":  [(100, 15, 70), (180, 40, 120), (230, 80, 160), (245, 140, 200), (255, 200, 230)],
    "ice":      [(20, 70, 100), (50, 140, 180), (100, 190, 220), (160, 220, 240), (210, 240, 255)],
    "dragon":   [(40, 10, 100), (70, 30, 160), (100, 60, 210), (140, 100, 230), (190, 160, 250)],
    "ghost":    [(30, 15, 60), (60, 30, 110), (90, 50, 160), (130, 80, 200), (180, 140, 230)],
    "poison":   [(60, 10, 80), (110, 30, 140), (160, 55, 190), (200, 100, 220), (230, 170, 245)],
    "ground":   [(80, 50, 20), (150, 100, 40), (200, 150, 70), (220, 185, 110), (245, 220, 170)],
    "rock":     [(60, 50, 40), (110, 95, 70), (160, 140, 100), (195, 175, 140), (225, 215, 190)],
    "bug":      [(40, 70, 10), (80, 130, 20), (120, 180, 40), (170, 210, 80), (210, 235, 140)],
    "flying":   [(50, 50, 120), (90, 90, 180), (130, 130, 220), (170, 170, 240), (210, 210, 255)],
    "fighting": [(100, 15, 15), (170, 30, 30), (210, 60, 50), (230, 110, 80), (245, 170, 140)],
    "normal":   [(80, 80, 75), (130, 125, 115), (175, 170, 155), (210, 205, 190), (240, 235, 225)],
    "fairy":    [(130, 50, 90), (200, 90, 150), (230, 140, 190), (245, 185, 215), (255, 220, 240)],
    "steel":    [(70, 75, 85), (120, 130, 145), (160, 170, 185), (195, 200, 210), (225, 228, 235)],
    "dark":     [(25, 20, 15), (55, 45, 35), (90, 75, 60), (130, 115, 95), (175, 165, 145)],
}


def get_available_sprites():
    """Get list of all downloaded sprite names."""
    normal_dir = SPRITES_DIR / "normal"
    if not normal_dir.exists():
        return []
    return sorted([f.stem for f in normal_dir.glob("*.png")])


def get_pokemon_types():
    """Load Pokémon type database."""
    if TYPES_DB.exists():
        with open(TYPES_DB) as f:
            return json.load(f)
    return {}


def sprite_to_base64(img):
    """Convert a PIL Image to base64 data URI (upscaled for display)."""
    # Upscale for display (pixel art → crisp upscale)
    scale = 4
    w, h = img.size
    upscaled = img.resize((w * scale, h * scale), Image.NEAREST)

    buf = io.BytesIO()
    upscaled.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def load_sprite_image(name):
    """Load a sprite by name from the normal directory."""
    path = SPRITES_DIR / "normal" / f"{name}.png"
    if path.exists():
        return Image.open(path).convert("RGBA")
    return None


# ─── Routes ───────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    """Main page."""
    sprites = get_available_sprites()
    types_db = get_pokemon_types()

    # Get unique types
    all_types = set()
    for info in types_db.values():
        for t in info.get("types", []):
            all_types.add(t)
    all_types = sorted(all_types)

    return render_template("index.html", sprites=sprites, types=all_types)


@app.route("/api/sprites")
def api_sprites():
    """List all available sprites."""
    sprites = get_available_sprites()
    types_db = get_pokemon_types()

    result = []
    for name in sprites:
        info = types_db.get(name, {})
        sprite_img = load_sprite_image(name)
        thumb = sprite_to_base64(sprite_img) if sprite_img else None
        result.append({
            "name": name,
            "id": info.get("id", 0),
            "types": info.get("types", []),
            "thumbnail": thumb,
        })

    return jsonify(result)


@app.route("/api/sprite/<name>")
def api_sprite(name):
    """Get a single sprite image as base64."""
    img = load_sprite_image(name)
    if not img:
        return jsonify({"error": "Sprite not found"}), 404
    return jsonify({"name": name, "image": sprite_to_base64(img)})


@app.route("/api/generate/shiny", methods=["POST"])
def api_generate_shiny():
    """Generate a shiny variant."""
    data = request.json or {}
    name = data.get("source", "")
    count = min(int(data.get("count", 1)), 12)
    hue_shift = data.get("hue_shift")
    sat_shift = data.get("sat_shift")

    sprite = load_sprite_image(name)
    if not sprite:
        return jsonify({"error": f"Sprite '{name}' not found"}), 404

    results = []
    for i in range(count):
        hue = float(hue_shift) if hue_shift is not None else random.uniform(30, 330)
        sat = float(sat_shift) if sat_shift is not None else random.uniform(0.7, 1.4)

        result = SpriteCompositor.apply_hue_shift(sprite, hue)
        result = SpriteCompositor.apply_saturation_shift(result, sat)

        results.append({
            "image": sprite_to_base64(result),
            "hue_shift": round(hue, 1),
            "sat_shift": round(sat, 2),
            "label": f"Shiny #{i+1}",
        })

    return jsonify({"source": name, "variants": results})


@app.route("/api/generate/palette-swap", methods=["POST"])
def api_generate_palette_swap():
    """Palette swap: apply one Pokémon's colors to another."""
    data = request.json or {}
    source_name = data.get("source", "")
    target_name = data.get("target", "")

    source_img = load_sprite_image(source_name)
    target_img = load_sprite_image(target_name)

    if not source_img:
        return jsonify({"error": f"Source '{source_name}' not found"}), 404
    if not target_img:
        return jsonify({"error": f"Target '{target_name}' not found"}), 404

    source_path = SPRITES_DIR / "normal" / f"{source_name}.png"
    target_path = SPRITES_DIR / "normal" / f"{target_name}.png"

    source_palette = PokemonPalette(source_path)
    target_palette = PokemonPalette(target_path)

    swapper = PaletteSwapper(source_palette, target_palette)
    result = swapper.apply_to_image(source_img)

    return jsonify({
        "source": {"name": source_name, "image": sprite_to_base64(source_img)},
        "target": {"name": target_name, "image": sprite_to_base64(target_img)},
        "result": {"image": sprite_to_base64(result), "label": f"{source_name} → {target_name}"},
    })


@app.route("/api/generate/type-swap", methods=["POST"])
def api_generate_type_swap():
    """Type swap: recolor a sprite with a type's palette."""
    data = request.json or {}
    source_name = data.get("source", "")
    target_type = data.get("type", "")

    source_img = load_sprite_image(source_name)
    if not source_img:
        return jsonify({"error": f"Source '{source_name}' not found"}), 404

    # Try palette DB first, fall back to synthetic palettes
    all_colors = None

    if PALETTE_DB.exists():
        with open(PALETTE_DB) as f:
            db = json.load(f)
        type_data = db.get("type_palettes", {}).get(target_type)
        if type_data and type_data.get("ramps"):
            all_colors = []
            for ramp in type_data["ramps"]:
                all_colors.extend([tuple(c) for c in ramp])

    # Fallback to synthetic type palettes
    if not all_colors:
        if target_type in SYNTHETIC_TYPE_PALETTES:
            all_colors = list(SYNTHETIC_TYPE_PALETTES[target_type])
        else:
            return jsonify({"error": f"Unknown type: {target_type}"}), 400

    source_path = SPRITES_DIR / "normal" / f"{source_name}.png"
    source_palette = PokemonPalette(source_path)
    target_palette = PokemonPalette(colors=all_colors)

    swapper = PaletteSwapper(source_palette, target_palette)
    result = swapper.apply_to_image(source_img)

    return jsonify({
        "source": {"name": source_name, "image": sprite_to_base64(source_img)},
        "type": target_type,
        "result": {"image": sprite_to_base64(result), "label": f"{source_name} → {target_type}"},
    })


@app.route("/api/generate/spritesheet", methods=["POST"])
def api_generate_spritesheet():
    """Build a spritesheet from selected sprites."""
    data = request.json or {}
    names = data.get("sprites", [])
    cols = min(int(data.get("cols", 6)), 20)
    rows = min(int(data.get("rows", 4)), 20)

    if not names:
        names = get_available_sprites()

    builder = SpritesheetBuilder(cols=cols, rows=rows, padding=2)
    for name in names[:cols * rows]:
        img = load_sprite_image(name)
        if img:
            builder.add_sprite(img)

    sheet = builder.build()
    if not sheet:
        return jsonify({"error": "No sprites to assemble"}), 400

    # Convert sheet to base64 (don't upscale spritesheets as much)
    scale = 2
    w, h = sheet.size
    upscaled = sheet.resize((w * scale, h * scale), Image.NEAREST)
    buf = io.BytesIO()
    upscaled.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return jsonify({
        "image": f"data:image/png;base64,{b64}",
        "width": w,
        "height": h,
        "count": len(names),
    })


@app.route("/api/download-more", methods=["POST"])
def api_download_more():
    """Download more sprites (limited batch for safety)."""
    data = request.json or {}
    limit = min(int(data.get("limit", 10)), 30)

    # Import and run scraper
    from scrape_pokemondb import scrape_pokemon_list, filter_by_gen, scrape_sprites, load_pokemon_names

    pokemon_db = load_pokemon_names(PROJECT_ROOT / "data")
    names = scrape_pokemon_list()
    names = filter_by_gen(names, pokemon_db, 1)

    # Filter to only download ones we don't have
    existing = set(get_available_sprites())
    new_names = [n for n in names if n not in existing][:limit]

    if not new_names:
        return jsonify({"message": "All Gen 1 sprites already downloaded!", "downloaded": 0})

    scrape_sprites(
        names=new_names,
        style="black-white",
        types=["normal", "shiny"],
        output_dir=SPRITES_DIR.parent,
        limit=limit,
    )

    # Run palette analyzer on new sprites
    from palette_analyzer import analyze_sprite, build_type_palettes
    return jsonify({"message": f"Downloaded {len(new_names)} sprites!", "downloaded": len(new_names), "names": new_names})


# ─── V2 Characteristic-Aware Endpoints ────────────────────────────────────────


@app.route("/api/pokemon/<name>")
def api_pokemon_info(name):
    """Get full Pokédex data for a Pokémon."""
    db = load_pokemon_data()
    data = db.get(name)
    if not data:
        return jsonify({"error": f"Unknown Pokémon: {name}"}), 404

    # Add sprite image
    img = load_sprite_image(name)
    result = dict(data)
    result["name"] = name
    if img:
        result["image"] = sprite_to_base64(img)
    return jsonify(result)


@app.route("/api/pokemon/<name>/matches")
def api_body_style_matches(name):
    """Get compatible body-style matches for smart swap."""
    db = load_pokemon_data()
    matches = BodyStyleMatcher.find_matches(name, db)
    # Filter to only sprites we actually have downloaded
    available = set(get_available_sprites())
    matches = [m for m in matches if m in available]
    return jsonify({"source": name, "body_style": db.get(name, {}).get("body_style", "unknown"), "matches": matches})


@app.route("/api/generate/stat-shiny", methods=["POST"])
def api_generate_stat_shiny():
    """Generate a stat-influenced shiny variant."""
    data = request.json or {}
    source_name = data.get("source", "")

    source_img = load_sprite_image(source_name)
    if not source_img:
        return jsonify({"error": f"Source '{source_name}' not found"}), 404

    db = load_pokemon_data()
    poke_data = db.get(source_name, {})
    stats = poke_data.get("base_stats", {"hp": 50, "atk": 50, "def": 50, "spa": 50, "spd": 50, "spe": 50})

    hue_shift = StatInfluencer.get_hue_shift(stats)
    sat_shift = StatInfluencer.get_saturation(stats)
    dominant = StatInfluencer.get_dominant_stat(stats)

    result = SpriteCompositor.apply_hue_shift(source_img, hue_shift)
    result = SpriteCompositor.apply_saturation_shift(result, sat_shift)

    return jsonify({
        "source": {"name": source_name, "image": sprite_to_base64(source_img)},
        "result": {"image": sprite_to_base64(result), "label": f"{source_name} (stat shiny)"},
        "stats": stats,
        "dominant_stat": dominant,
        "hue_shift": round(hue_shift, 1),
        "saturation": round(sat_shift, 2),
    })


@app.route("/api/generate/smart-swap", methods=["POST"])
def api_generate_smart_swap():
    """Body-style-aware palette swap between two Pokémon."""
    data = request.json or {}
    source_name = data.get("source", "")
    target_name = data.get("target", "")

    source_img = load_sprite_image(source_name)
    target_img = load_sprite_image(target_name)
    if not source_img:
        return jsonify({"error": f"Source '{source_name}' not found"}), 404
    if not target_img:
        return jsonify({"error": f"Target '{target_name}' not found"}), 404

    target_path = SPRITES_DIR / "normal" / f"{target_name}.png"
    source_path = SPRITES_DIR / "normal" / f"{source_name}.png"

    source_palette = PokemonPalette(source_path)
    target_palette = PokemonPalette(target_path)
    swapper = PaletteSwapper(source_palette, target_palette)
    result = swapper.apply_to_image(source_img)

    return jsonify({
        "source": {"name": source_name, "image": sprite_to_base64(source_img)},
        "target": {"name": target_name, "image": sprite_to_base64(target_img)},
        "result": {"image": sprite_to_base64(result), "label": f"{source_name} × {target_name}"},
    })


# ─── V3 ML Generation Endpoints ──────────────────────────────────────────────

_ml_model = None
_ml_device = None


def _load_ml_model():
    """Lazy-load the trained CVAE model."""
    global _ml_model, _ml_device
    if _ml_model is not None:
        return _ml_model, _ml_device

    import torch
    checkpoint_path = PROJECT_ROOT / "ml" / "checkpoints" / "best.pt"
    if not checkpoint_path.exists():
        return None, None

    # Device auto-detect
    if torch.backends.mps.is_available():
        _ml_device = torch.device("mps")
    elif torch.cuda.is_available():
        _ml_device = torch.device("cuda")
    else:
        _ml_device = torch.device("cpu")

    from ml.cvae_model import ConditionalVAE, LATENT_DIM
    from ml.sprite_dataset import COND_DIM

    ckpt = torch.load(checkpoint_path, map_location=_ml_device, weights_only=False)
    _ml_model = ConditionalVAE(
        latent_dim=ckpt.get("latent_dim", LATENT_DIM),
        cond_dim=ckpt.get("cond_dim", COND_DIM),
    ).to(_ml_device)
    _ml_model.load_state_dict(ckpt["model"])
    _ml_model.eval()
    print(f"  🧠 ML model loaded (epoch {ckpt.get('epoch', '?')})")
    return _ml_model, _ml_device


@app.route("/api/ml/status")
def api_ml_status():
    """Check if ML model is available."""
    best_ckpt = PROJECT_ROOT / "ml" / "checkpoints" / "best.pt"
    final_ckpt = PROJECT_ROOT / "ml" / "checkpoints" / "final.pt"
    return jsonify({
        "available": best_ckpt.exists() or final_ckpt.exists(),
        "best_checkpoint": best_ckpt.exists(),
        "final_checkpoint": final_ckpt.exists(),
    })


@app.route("/api/generate/ml", methods=["POST"])
def api_generate_ml():
    """Generate a new sprite using the trained CVAE model."""
    import torch

    model, device = _load_ml_model()
    if model is None:
        return jsonify({"error": "ML model not trained yet. Run: python3 -m ml.train_cvae"}), 400

    data = request.json or {}
    type1 = data.get("type1", "fire")
    type2 = data.get("type2", None)
    body_style = data.get("body_style", "bipedal")
    stats = data.get("stats", {})
    height = data.get("height", 1.0)
    weight = data.get("weight", 20.0)
    count = min(int(data.get("count", 4)), 12)

    from ml.generate_new_pokemon import build_custom_condition, post_process_sprite

    cond = build_custom_condition(
        type1=type1, type2=type2, body_style=body_style,
        hp=stats.get("hp", 80), atk=stats.get("atk", 80),
        defense=stats.get("def", 80), spa=stats.get("spa", 80),
        spd=stats.get("spd", 80), spe=stats.get("spe", 80),
        height=height, weight=weight,
    )

    results = []
    with torch.no_grad():
        for i in range(count):
            z = torch.randn(1, model.latent_dim).to(device)
            c = cond.unsqueeze(0).to(device)
            raw = model.decoder(z, c)[0]
            processed = post_process_sprite(raw, num_colors=16, upscale=4)
            results.append({
                "image": sprite_to_base64(processed),
                "label": f"Variant {i + 1}",
            })

    return jsonify({
        "variants": results,
        "config": {
            "type1": type1,
            "type2": type2,
            "body_style": body_style,
            "count": count,
        },
    })


if __name__ == "__main__":
    # Ensure output dirs exist
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "web" / "static").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "web" / "templates").mkdir(parents=True, exist_ok=True)

    print("\n🎮 Pokémon Sprite Generator")
    print(f"   Sprites loaded: {len(get_available_sprites())}")
    print(f"   Open: http://localhost:5001\n")

    app.run(host="0.0.0.0", port=5001, debug=True)
