# Zak brand assets

The Zak logo is a rounded green tile with a white lowercase `zk` in the bottom-right corner. The lockup pairs it with the `zaklang` wordmark. All text is converted to outlines, so the files render without any font loaded.

## Files

| File | Use |
| --- | --- |
| `zak-mark.svg` | Primary mark. Green tile (corner radius 10%), white `zk`. Use at every size, 16 px and up. Same art as `../favicon.svg`. |
| `zak-icon.svg` | App icon (1024 px, corner radius 22%, `zk` inset further). Source for `../apple-touch-icon.png`. |
| `zak-lockup-dark.svg` | Mark plus `zaklang` wordmark for dark surfaces (`#FAFAFA` text). |
| `zak-lockup-light.svg` | Mark plus `zaklang` wordmark for light surfaces (`#0A0A0A` text). |
| `zak-wordmark-dark.svg` | `zaklang` wordmark alone for dark surfaces (`#FAFAFA`). |
| `zak-wordmark-light.svg` | `zaklang` wordmark alone for light surfaces (`#0A0A0A`). |

`../favicon-16.png`, `../favicon-32.png` and `../apple-touch-icon.png` are rendered from `zak-mark.svg` and `zak-icon.svg` at their exact pixel sizes. Re-render them if the SVGs change.

In the app, use `ZakMark` and `ZakWordmark` from `src/components/Logo.tsx` instead of these files. The wordmark there draws in `currentColor`, so it follows the theme's text color.

## Color

- Tile: `#007355`. Text on the tile: `#FFFFFF` (5.9:1).
- The tile reads at 3.1:1 on the dark page (`#171717`) and 5.9:1 on white.
- `#007355` is also the interface accent. In the app it comes from the semantic tokens in `src/style.css` (`--color-surface-action`, `--color-surface-brand`), with lighter tints for focus rings and green text so they stay readable on dark surfaces. Everything else stays neutral.

## Clear space and sizes

- Keep clear space around the mark equal to 25% of its width on every side.
- In the lockup, the gap between mark and wordmark is fixed. Use the lockup files rather than placing the two by hand.
- Minimum sizes: mark 16 px, wordmark 12 px tall.

## Don't

- Don't recolor the tile, put the white `zk` on another color, or add effects (shadows, gradients, outlines).
- Don't move `zk` out of the bottom-right corner or reset it in another font.
- Don't stretch or rotate the mark.
