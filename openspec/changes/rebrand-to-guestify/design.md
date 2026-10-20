## Context

- All logo rendering already goes through `src/presentation/brand.ts` and
  `<BrandLogo variant="light|on-dark|mark">`. That was set up by the
  archived `rebrand-to-visimio` change for exactly this kind of rename.
  Literals that can't import `brand.ts` are `index.html`,
  `public/firebase-messaging-sw.js`, and two hard-coded `aria-label`s.
- The assets come from the paired API change, which rebuilds the supplied
  raster as an approved SVG master (`VMSS_API/brand/`, API `design.md`
  Decisions 1–4). `build_brand_assets.py --web-out` writes the outputs
  here. This change consumes them, and doesn't start until the user has
  approved the master (API task 2.7).
- `BrandLogo` currently renders `src` plus a `srcSet` with a 2× PNG.
- Logo slots and their heights:
  - `PortalHeader`: `h-7 md:h-8`, light;
  - `PortalFooter`: `h-7`, light;
  - `AppShell` mobile bar: `h-7`, light;
  - `SidebarHeader`: on-dark, or the mark when collapsed;
  - `StaffGatewayHeader` and `StaffPortalHeader`: `h-7 md:h-8`, on-dark.
- The Guestify lockup is about 3.1:1, wider than Visimio's at the same
  height. `BrandLogo`'s `w-auto max-w-fit object-contain` already keeps the
  ratio.

## Goals / Non-Goals

**Goals:**
- Swap the name and assets with edits confined to `brand.ts` plus the
  four literal sites.
- Make the old name impossible to reintroduce silently.

**Non-Goals:**
- Changing the portal theme colours or `theme-color` (`#0f172a` already
  matches the logo's navy closely).
- Inlining the SVG as React components. An `<img src>` of the SVG URL is
  enough: the logo needs no CSS recolouring, and it stays cacheable.

## Decisions

### 1. Keep the variant API, switch the files to SVG
`BRAND_LOGOS` keeps its keys (`light`, `on-dark`, `mark`), so no
component changes its props. Each entry becomes a single `{ src }`
pointing at an imported `.svg`; the `src2x` field goes away. `BrandLogo`
drops `srcSet`, because a vector is already sharp at every density. Its
`w-auto max-w-fit object-contain` sizing works the same for an SVG with
a `viewBox` and intrinsic `width`/`height`, which the API build step
guarantees.

The alternative was to keep PNG pairs rendered from the SVG. That was
rejected: it's more files, and it's still blurry under browser zoom or on
3× phones, when the vector is available anyway.

### 2. Derive the aria-labels from `BRAND_NAME`
`PortalHeader` and `SidebarHeader` hard-code `aria-label="Visimio home"`,
which is exactly the drift `brand.ts` was meant to prevent. They switch to
`` `${BRAND_NAME} home` ``. The service worker can't import ES modules from
`src/`, so it keeps a literal, with the existing comment in `brand.ts`
noting the duplication.

### 3. Widen the lint guard to a retired-names list
`scripts/check-brand.mjs` replaces `RETIRED_NAME = /VisitorPass/` with
`/VisitorPass|Visimio/i`. It runs on `src`, `public` and `index.html`.
Asset filenames are checked too: the walker already visits every file,
and a leftover `logo-visimio.png` import would show up in `brand.ts`
anyway. `openspec/` and `e2e/` are outside its roots, so archived changes
keep their history.

### 4. Size slots stay as they are unless the check fails
Heights aren't pre-emptively shrunk. The wider wordmark is checked at
375 / 768 / 1440px in each slot, and only a slot that clips or crowds
gets a height adjustment. The likely candidate is the expanded sidebar
header next to its collapse button. Changing heights blindly would alter
the visual weight the previous change tuned.

## Risks / Trade-offs

- **[Assets not regenerated yet]** If the web change is applied before the
  API script runs, `brand.ts` imports files that don't exist, and the
  Vite build fails. → Task 1.1 checks the files exist first. This is a
  loud failure, not a silent one.
- **[Favicon cache]** Browsers cache favicons aggressively, so testers may
  keep seeing the Visimio "V". → Use a hard refresh or a private window
  when verifying. The new `favicon.svg` link is listed first, so modern
  browsers pick up a fresh URL. Older ones fall back to the PNGs.
- **[Uncommitted local edits]** `index.html` already carries unrelated
  uncommitted edits on this branch. → Change only the `<title>` and
  favicon `<link>` lines, and stage with `git add -p`.
