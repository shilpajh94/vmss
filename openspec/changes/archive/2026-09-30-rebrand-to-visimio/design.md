## Context

- The brand name is hard-coded as text in 11 components. The visitor
  header and footer draw a "V" tile in a `div`. The sidebars and staff
  headers import `src/assets/logo-mark.svg`, the old gradient mark.
  `src/assets/logo.svg` is unused.
- `index.html` has `<title>VMSS</title>` and Vite's default purple
  `favicon.svg`.
- The only source asset is a raster PNG (`assets/visimio-logo-source.png`,
  2172×724, transparent background): a cyan `#01A9CF` mark, and the
  wordmark in `#0E1527`, which is unreadable on the navy `#0f172a` surfaces.
- The API change `refine-email-templates-and-visimio-brand` adds
  `VMSS_API/scripts/build_brand_assets.py` (Pillow), which already needs the
  same trim and recolour for the email header.

## Goals / Non-Goals

**Goals:** one brand module; crisp logos at 1× and 2×; correct variant per
background; no hard-coded name left.

**Non-Goals:** redrawing the logo as SVG (only a PNG exists), or changing
theme colours. The current cyan accent already matches the mark.

## Decisions

### 1. Assets generated from the source by the API repo's Pillow script
`build_brand_assets.py --web-out ../VMMS_WEB/src/assets/brand` writes:
- `logo-visimio.png` and `@2x`: trimmed lockup, dark wordmark;
- `logo-visimio-on-dark.png` and `@2x`: wordmark pixels near `#0E1527`
  recoloured to white, alpha kept;
- `logo-visimio-mark.png` and `@2x`: cropped to the mark's bounding box.
  *As built:* the push notification icon also moved from the deleted
  `/favicon.svg` to `/apple-touch-icon.png`.
  The mark is the connected cyan region at the left, found by column
  scan up to the first fully transparent gap;
- `public/favicon.png` (48 px), `public/favicon-32.png` and
  `public/apple-touch-icon.png` (180 px, on a white rounded square).

The 1× heights are 32 px for the lockups and 28 px for the mark.

This reuses one implementation of the recolour and trim, so email and
portal can't drift, and it adds no Node image dependency. The outputs are
committed, so building the web app never needs Python. The alternative,
`sharp` in the web repo, would duplicate the logic and add a native
dependency.

### 2. `brand.ts` + `<BrandLogo>`
```ts
// src/presentation/brand.ts
export const BRAND_NAME = 'Visimio'
export const copyrightLine = () => `© ${new Date().getFullYear()} ${BRAND_NAME}. All rights reserved.`
```
`BrandLogo({ variant: 'light' | 'on-dark' | 'mark', className })` renders
`<img src srcSet="…@2x.png 2x" alt={BRAND_NAME} class="h-8 w-auto">`, and
`height` is overridable via `className`. Every place that currently shows
the "V" tile or text, or `logoMark` plus "VisitorPass" text, becomes one
`<BrandLogo>`.

The service worker can't import TS modules, so it keeps a literal
`'Visimio'` with a comment pointing to `brand.ts`.

### 3. Sizing on small screens
Sidebars use `on-dark` at `h-8`. The phone nav bar has a white
background, so it uses `light` at `h-7`. Staff login headers
use `on-dark` at `h-7 md:h-8`. The visitor header uses `light` at `h-7
md:h-8`. The footer uses `light` at `h-7`. This fits the responsive work
already in place (the header is `h-16` on phone).

### 4. Guardrail
A tiny check, `scripts/check-brand.mjs`, runs in `npm run lint`. It fails
if `VisitorPass` appears in `src/`, `index.html` or `public/`. That's
cheap, and stops the old name from being reintroduced by copy-paste.

## Risks / Trade-offs

- [Raster logo edges look soft on high-DPI screens] → `@2x` assets are
  used. Replace them with SVG-derived PNGs if a vector file arrives (open
  question).
- [The recolour threshold misses antialiased pixels, leaving a dark halo
  on navy] → The threshold is a colour distance on RGB with alpha kept.
  Outputs are reviewed visually before committing (tasks 1.2).
- [The web change depends on the API repo's script] → It's only needed to
  regenerate assets. The committed PNGs make the web repo self-contained
  at build time.

## Migration Plan

Frontend-only, and ships independently of the API change. Rollback is a
revert.

## Open Questions

- The support address in the footer, `support@visitorpass.co`: what is the
  Visimio support address? It stays unchanged until one is provided. It
  isn't a brand mark, and inventing a domain would send mail nowhere.
- Is there a vector (SVG) version of the logo? If so, regenerate the PNGs
  from it. The approach is unchanged.
