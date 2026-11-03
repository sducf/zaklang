# Zak brand assets

The Zak logo is a rounded green tile with a lowercase `zak` set in JetBrains Mono Medium in the bottom-right corner. All text is converted to outlines, so the files render without any font loaded.

## Files

| File | Use |
| --- | --- |
| `zak-mark.svg` | Primary mark. Green tile, white `zak`. Use at 40 px and up. |
| `zak-mark-small.svg` | Small cut with only `z`. Use below 40 px (favicon, sidebar). Same art as `../favicon.svg`. |
| `zak-mark-mono-dark.svg` | One-color fallback for dark surfaces (`#FAFAFA` frame and text). |
| `zak-mark-mono-light.svg` | One-color fallback for light surfaces (`#171717` frame and text). |
| `zak-wordmark-dark.svg` | `zaklang` wordmark for dark surfaces (`#FAFAFA`). |
| `zak-wordmark-light.svg` | `zaklang` wordmark for light surfaces (`#171717`). |

In the app, use `ZakMark` and `ZakWordmark` from `src/components/Logo.tsx` instead of these files. The wordmark there draws in `currentColor`, so it follows the theme's text color.

## Color

- Tile: `#007355`. Text on the tile: `#FFFFFF` (5.9:1).
- The tile reads at 3.1:1 on the dark page (`#171717`) and 5.9:1 on white.
- `#007355` is the logo color only. Do not use it for UI elements; the rest of the interface stays neutral.
- Use the mono fallback where color is not available (single-color print, embossing, or a surface the green does not clear 3:1 on).

## Clear space and sizes

- Keep clear space around the mark equal to 25% of its width on every side.
- Pair the mark and wordmark side by side with a gap of 25% of the mark's width, wordmark cap height centered on the mark.
- Minimum sizes: `zak-mark.svg` 40 px, `zak-mark-small.svg` 16 px, wordmark 12 px tall.

## Don't

- Don't recolor the tile, put the white `zak` on another color, or add effects (shadows, gradients, outlines).
- Don't move `zak` out of the bottom-right corner or reset it in another font.
- Don't stretch or rotate the mark.
