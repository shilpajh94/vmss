## Why

The app currently ships with a placeholder Tailwind theme (`src/styles/theme.css`) that has no relationship to the product's actual visual identity. The Figma file "VMS" (node `4:4`, "visitor-management-design-system") defines the approved color palette and typography scale for the Visitor Management System. Adopting it now, while only the app-shell exists, means every page and component built from this point on starts from the real brand tokens instead of being retrofitted later.

## What Changes

- Replace the placeholder `--color-*` tokens in `src/styles/theme.css` with the Figma palette: `primary` (#0F172A), `secondary-accent` (#06B6D4), `success` (#10B981), `warning` (#F59E0B), `danger` (#EF4444), `info` (#3B82F6), and `vip` (#D97706), plus the neutral surface/border/text scale used throughout the sheet (white surface, `#E2E8F0` border, `#F1F5F9` divider, `#64748B` muted text, `#94A3B8` faint text).
- Add font tokens for the two Figma typefaces — **Outfit** (display/headings) and **Geist** (body/UI text) — and the type-scale steps documented in the sheet (Display, H1, H2, H3, Body Large, Body, Caption, Overline), expressed as Tailwind `@theme` tokens (font family, size, weight, letter-spacing) rather than one-off utility classes.
- Load the two webfonts (self-hosted or via `@font-face`) so `font-['Outfit']` / `font-['Geist']` are actually available; no external CDN font script tags.
- **BREAKING**: rename/remove the existing placeholder tokens (`--color-bg`, `--color-surface`, `--color-border`, `--color-text`, `--color-text-muted`, `--color-primary`, `--color-primary-hover`, `--color-danger`) in favor of the new Figma-derived token names. Anything referencing the old names must be updated (currently nothing in `src/` consumes them yet, since no pages/components exist beyond the app-shell).
- Out of scope for this change: styling individual components (buttons, form inputs, badges, visitor cards, nav/chrome, tables, modals, misc widgets) shown elsewhere in the same Figma file. Those get built against these tokens when the corresponding features/pages are actually implemented, per user decision to scope this change to tokens only.

## Capabilities

### New Capabilities
- `design-theme`: the color, typography, and font-loading tokens that make up the application's visual theme, sourced from the Figma design system file.

### Modified Capabilities
(none — no existing capability's requirements change; `app-shell` is unaffected since it does not currently specify visual tokens)

## Impact

- `src/styles/theme.css`: token definitions replaced.
- `src/styles/index.css` (or a new `src/styles/fonts.css` imported from it): `@font-face` declarations / font loading for Outfit and Geist.
- No changes to `src/data/`, `src/infrastructure/`, `src/domain/`, or `composition-root.ts` — this is a presentation-layer/styling-only change.
- No new npm dependencies expected unless self-hosting font files requires adding font asset files under `public/` or `src/assets/`.
