# Pokémon SpriteGenerator

Generate unique Pokémon sprites through **palette swapping**, **shiny variant generation**, and **spritesheet assembly** — inspired by [David York's GenGam 2016](http://davideyork.com/articles/gengam-2016) algorithm for procedural sprite generation.

## Features

- 🎨 **Palette Swap** — Apply one Pokémon's color palette onto another's sprite shape
- 🔥 **Type Swap** — Recolor any Pokémon to match a type's characteristic colors (fire, water, grass, etc.)
- ✨ **Shiny Generation** — Create custom shiny variants with randomized hue/saturation shifts
- 📋 **Spritesheet Assembly** — Arrange generated sprites into organized grid sheets
- 🕷️ **Sprite Scrapers** — Download reference sprites from [pokemondb.net](https://pokemondb.net/sprites) and [PMDCollab](https://sprites.pmdcollab.org/)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Download Reference Sprites

```bash
# Download Gen 1 sprites from pokemondb.net (standard pixel art)
python scripts/scrape_pokemondb.py --style black-white --gen 1

# Download PMD-style animated sprites (optional)
python scripts/scrape_pmdcollab.py --limit 50
```

### 3. Analyze Palettes

```bash
python scripts/palette_analyzer.py
```

### 4. Generate Sprites

```bash
# Palette swap: Bulbasaur with Charmander's colors
python generate.py --mode palette-swap --source bulbasaur --target charmander

# Type swap: Pikachu with water-type colors
python generate.py --mode type-swap --source pikachu --type water

# Generate 10 shiny variants of Eevee
python generate.py --mode shiny-gen --source eevee --count 10

# Batch generate shinies for all downloaded sprites
python generate.py --mode batch-shiny --count 3

# Build a spritesheet from generated sprites
python generate.py --mode spritesheet --input output/shinies/ --cols 12 --rows 8
```

## Project Structure

```
SpriteGenerator/
├── scripts/
│   ├── scrape_pokemondb.py          # Scraper for pokemondb.net sprites
│   ├── scrape_pmdcollab.py          # Scraper for PMDCollab animated sprites
│   ├── palette_analyzer.py          # Color palette extraction utility
│   └── pokemon_sprite_generator.py  # Core generator engine
├── data/
│   └── pokemon_types.json           # Pokémon name → type mapping (Gen 1)
├── Reference/                       # Downloaded sprites (gitignored)
│   ├── pokemondb/                   # Standard sprites
│   ├── pmdcollab/                   # PMD animated sprites
│   └── palettes/                    # Extracted palette database
├── output/                          # Generated sprites (gitignored)
├── docs/
│   └── gengam_overview.md           # Original algorithm overview
├── generate.py                      # CLI entry point
├── requirements.txt                 # Python dependencies
├── SpriteGenerator/                 # Original C# code (preserved)
└── README.md
```

## How It Works

### Algorithm (adapted from GenGam 2016)

1. **Download** reference sprites (pokemondb.net for standard pixel art, PMDCollab for animations)
2. **Analyze** each sprite's color palette — extract unique colors, group into HSL-sorted "color ramps"
3. **Categorize** palettes by Pokémon type (fire=reds/oranges, water=blues, etc.)
4. **Generate** new sprites by:
   - Mapping source color ramps → target color ramps proportionally
   - Applying hue/saturation shifts for shiny variants
   - Compositing multiple sprite layers if mixing parts
5. **Assemble** into spritesheets with configurable grid layout

### Palette System

| Material Type | Color Characteristics |
|---------------|----------------------|
| Fire          | Warm reds, oranges, yellows |
| Water         | Cool blues, teals, cyan |
| Grass         | Greens, leaf tones |
| Electric      | Bright yellows, ambers |
| Psychic       | Pinks, purples, magentas |
| Ghost         | Deep purples, dark blues |
| Ice           | Light blues, whites, cyan |
| Dragon        | Deep blues, violets |

## Scraper Details

### pokemondb.net Scraper

Downloads standard pixel-art sprites organized by game style:
- **Styles**: red-blue, gold, crystal, ruby-sapphire, emerald, diamond-pearl, black-white
- **Types**: normal, shiny, animated (Gen 5 only)
- Rate limited at 0.5s between requests with retry logic

### PMDCollab Scraper

Downloads PMD-style animated sprite sheets from the open-source SpriteCollab repo:
- **Animations**: Walk, Idle, Attack, Sleep, Hurt, Charge, Hop, etc.
- Multi-directional animation frames in sprite sheet format
- Includes portrait images

## Original C# Code

The original C# SpriteGenerator by [David York](https://github.com/DavidYork/SpriteGenerator) is preserved in the `SpriteGenerator/` directory. It was built with Visual Studio for Mac and generates human character sprites from body part layers and color palettes. See [docs/gengam_overview.md](docs/gengam_overview.md) for details.

## License

See [LICENSE](LICENSE) for details.