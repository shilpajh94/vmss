## 1. Fonts

- [x] 1.1 Add `@fontsource/outfit` and `@fontsource/geist` to `package.json`
- [x] 1.2 Create `src/styles/fonts.css` importing the required weights (Outfit 400/600/700/800; Geist 400/500/700)
- [x] 1.3 Import `fonts.css` from `src/styles/index.css`, before the `theme.css` import

## 2. Color tokens

- [x] 2.1 Replace the placeholder `--color-*` tokens in `src/styles/theme.css` with the Figma-derived tokens: `primary`, `secondary-accent`, `success`, `warning`, `danger`, `info`, `vip`, `bg`/`surface`, `border`, `border-subtle`, `text`, `text-muted`, `text-faint` (see design.md for exact hex values)
- [x] 2.2 Add `--font-display` and `--font-body` font-family tokens referencing Outfit and Geist

## 3. Typography scale

- [x] 3.1 Add `@utility` classes for each type-scale step (`text-display`, `text-h1`, `text-h2`, `text-h3`, `text-body-lg`, `text-body`, `text-caption`, `text-overline`) with the font family, size, weight, and letter-spacing from the Figma sheet

## 4. Verification

- [x] 4.1 Run the app locally and confirm in devtools that computed `font-family` for headings/body resolves to Outfit/Geist (not a fallback)
- [x] 4.2 Confirm in devtools that each new color token resolves to its exact specified hex value
- [x] 4.3 Confirm no remaining references to the old placeholder token names anywhere in `src/`
