# EYEWAZ brand assets

## Logo  ← drop your logo here
The header and favicon load **`eyewaz-logo.svg`** from this folder. Save your
logo (the square icon mark works best on the blue bar) as:

    webapp/assets/eyewaz-logo.svg

If you only have a PNG, save it as `eyewaz-logo.png` and change the two
references in `webapp/index.html` (the favicon `<link>` and the header `<img>`)
from `eyewaz-logo.svg` to `eyewaz-logo.png`.

Until the file exists, the header hides the icon and shows just the `eyewaz`
wordmark — nothing looks broken. Once you add the file and the image is rebuilt,
your logo appears automatically.

> Note: the logo is a static asset baked into the Docker image, so after adding
> the file the image must be rebuilt + pushed (see `../../DEPLOY.md`).

## Font — GoodDogNew
The brand wordmark and headings are designed for **GoodDogNew**. We don't have
that font file, so the app currently loads **Baloo 2** (a rounded, friendly
GoodDogNew look-alike) from Google Fonts via a `<link>` in `index.html`.

To switch to the real GoodDogNew, drop the font file(s) here:
- `fonts/GoodDogNew.woff2`  (preferred — smallest)
- `fonts/GoodDogNew.woff`   (fallback)
- `fonts/GoodDogNew.ttf`    (fallback)

The `@font-face` in `styles.css` already points at these paths and lists
`GoodDogNew` first in the font stack, so it takes over automatically the moment
a file is present — no other change needed (the Baloo 2 `<link>` can then be
removed from `index.html` if you like).

## Colours
- `#7BB2BE` — EYEWAZ blue (brand / accents)
- `#F7F6E9` — EYEWAZ cream (page background)
Darker/lighter shades for buttons, focus rings and hover states are derived from
`#7BB2BE` in `styles.css` to keep text legible for low-vision users (WCAG AA).
