# EYEWAZ brand assets

## Logo
- `eyewaz-mark.svg` — the ear+eye logo mark, recreated as a scalable, themeable
  SVG (uses `currentColor`, so CSS controls its colour). Used in the header and
  as the favicon.

**To use your original raster artwork instead**, drop the files here:
- `eyewaz-mark.png` — the square icon (the standalone ear/eye mark)
- `eyewaz-wordmark.png` — the full "eyewaz — SEE BETTER. LIVE BETTER." banner

…then in `webapp/index.html` swap the header `<img>` `src` from
`/app/assets/eyewaz-mark.svg` to `/app/assets/eyewaz-mark.png`.

## Font — GoodDogNew
The brand wordmark and headings use **GoodDogNew**. Drop the font file(s) here:
- `fonts/GoodDogNew.woff2`  (preferred — smallest)
- `fonts/GoodDogNew.woff`   (fallback)
- `fonts/GoodDogNew.ttf`    (fallback)

The `@font-face` in `styles.css` already points at these paths. Until a file is
present, the app falls back to a friendly rounded system font so nothing breaks.

## Colours
- `#7BB2BE` — EYEWAZ blue (brand / accents)
- `#F7F6E9` — EYEWAZ cream (page background)
Darker/lighter shades for buttons, focus rings and hover states are derived from
`#7BB2BE` in `styles.css` to keep text legible for low-vision users (WCAG AA).
