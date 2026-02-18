# GenGam 2016: Sprite Generator Overview

Based on the article [GenGam 2016](http://davideyork.com/articles/gengam-2016), this document outlines the algorithm and methodology used in the Sprite Generator project.

## Core Concept
The project aims to generate thousands of unique, coherent 2D character sprites by combining pre-cut sprite parts and applying procedurally selected color palettes.

## The Algorithm
1.  **Decomposition**: Source sprites (from Oryx Design Lab's 16-bit Sprite Set) are broken down into individual components.
2.  **Color Normalization**: source part colors are changed to "input colors" — standardized placeholders that map to specific material types.
3.  **Recombination**: The algorithm randomly selects one piece for each required layer (e.g., one head, one torso, one weapon).
4.  **Recoloring**: The algorithm randomly selects a "color ramp" for each material type from a master palette and replaces the input colors with the selected ramp's colors.
5.  **Rendering**: Parts are drawn sequentially on top of each other to form the final sprite.

## Inputs & Layers
Sprites are composed of the following layers drawn in order:
*   Feet
*   Torso
*   Head
*   Hair
*   Helmet
*   Weapon
*   Shield
*   Bow

## Palette System
The color replacement system is central to creating variety while maintaining aesthetic consistency.
*   **Color Ramps**: Groups of colors ranging from light to dark that replace the single flat "input color" of a source part.
*   **Materials**: Different materials require different ramp structures to look natural.
    *   *Metal*: High contrast/variance between shades.
    *   *Cloth*: Lower contrast/variance.
    *   *Skin*: Specific hues for natural skin tones.
*   **Material Types**: Primary Cloth, Secondary Cloth, Hair, Skin, Metal, Wood, Leather, Gemstone, Dark Accent.

## Logic Flow
1.  Enumerate all source files for each body part.
2.  Load the master palette file.
3.  Select a random set of body parts (e.g., specific head, specific armor).
4.  Select a random color composition (e.g., "Red Cloth" + "Steel Armor" + "Dark Skin").
5.  Composite the parts, applying the color swaps pixel-by-pixel or by palette indexing.
