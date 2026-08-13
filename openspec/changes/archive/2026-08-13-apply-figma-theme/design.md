## Context

`src/styles/theme.css` currently defines a placeholder Tailwind v4 `@theme` block (see `.claude/rules/clean-architecture.md` — theme tokens live here, pulled into `src/styles/index.css` via `@import`). Nothing in `src/` outside `theme.css` itself references any of the current `--color-*` names (confirmed by repo-wide grep), so there are no call sites to migrate. See `proposal.md` for why we're adopting the Figma palette now. Source: Figma file `jXdJ0LuzcPY9YxgrnqXle6`, node `4:4` ("visitor-management-design-system"), sections 01 (Color Palette) and 02 (Typography Scale).

## Goals / Non-Goals

**Goals:**
- Token names and values in `theme.css` match the Figma color palette and type scale exactly.
- Outfit and Geist are available to every page with no runtime request to a third-party font host.
- Typography steps (Display/H1/H2/H3/Body Large/Body/Caption/Overline) are reusable as named classes, not re-typed as ad-hoc utility strings in every component.

**Non-Goals:**
- Styling buttons, inputs, badges, cards, nav, tables, or modals from the same Figma file (deferred to when those features are built, per scope decision).
- Dark mode / theme switching — the Figma sheet defines one light theme; no toggle exists today.
- Pixel-porting every neutral gray Tailwind ships by default — only the specific neutral stops the sheet actually uses (surface, border, divider, muted text, faint text) are added.

## Decisions

### Token layer: extend the existing `@theme` block in `theme.css`, don't restructure it
Keep the single-file `@theme { --color-*: ... }` pattern already established. Replace the placeholder color tokens with the Figma set and add font-family tokens (`--font-display: "Outfit", ...`, `--font-body: "Geist", ...`). This matches the project's existing convention (`.claude/rules/clean-architecture.md`) rather than introducing a second config surface (e.g. `tailwind.config.ts`), which this Tailwind v4 / CSS-first setup doesn't use.

Token names (semantic, matching Figma swatch labels):
- `--color-primary: #0F172A`
- `--color-secondary-accent: #06B6D4`
- `--color-success: #10B981`
- `--color-warning: #F59E0B`
- `--color-danger: #EF4444`
- `--color-info: #3B82F6`
- `--color-vip: #D97706`
- `--color-bg: #FFFFFF` / `--color-surface: #FFFFFF` (page/card background, per sheet's white swatch cards)
- `--color-border: #E2E8F0` (card/swatch border)
- `--color-border-subtle: #F1F5F9` (row dividers, e.g. type-scale rows)
- `--color-text: #0F172A` (primary text, same value as brand primary per the sheet)
- `--color-text-muted: #64748B`
- `--color-text-faint: #94A3B8`

### Typography: raw tokens in `@theme`, named steps as `@utility` classes
Define font family / base sizes as `@theme` tokens, then use Tailwind v4's `@utility` directive to create one class per type-scale step (`.text-display`, `.text-h1`, `.text-h2`, `.text-h3`, `.text-body-lg`, `.text-body`, `.text-caption`, `.text-overline`), each setting font-family + size + weight + letter-spacing in one place.

**Alternative considered**: compose each usage from Tailwind arbitrary-value utilities directly (`text-[40px] font-['Outfit'] font-extrabold tracking-[-1px]`), matching the Figma-exported code verbatim. Rejected — it repeats the same four magic values at every call site and lets the scale drift out of sync with the design system over time; a named step is the actual reusable "typography token" the proposal asks for.

### Font loading: self-hosted via `@fontsource/outfit` and `@fontsource/geist`, not a Google Fonts `<link>`
Add `@fontsource/outfit` (weights 400/600/700/800) and `@fontsource/geist` (weights 400/500/700) as dependencies, imported from a new `src/styles/fonts.css` (`@import "@fontsource/outfit/700.css";` etc.), which `index.css` imports before `theme.css`. This satisfies the spec's "no third-party runtime dependency" requirement (files are bundled by Vite, no request to `fonts.googleapis.com`) while avoiding hand-managing font binaries and licensing metadata.

**Alternative considered**: download the woff2 files by hand into `public/fonts/` with manual `@font-face` rules. Rejected — `@fontsource` gives the same self-hosted, no-CDN result with versioned updates and correct `font-display`/unicode-range metadata, for less maintenance.

### Neutral scale: only the stops the sheet actually uses
Rather than generating a full gray-50…gray-900 ramp, only the exact stops appearing in the Figma sheet are added (`border`, `border-subtle`, `text-muted`, `text-faint`, plus white surface/bg). Anything needing a shade not in this list should be added when a real component in the source-of-truth Figma design (not the reference sheet) calls for it.

## Risks / Trade-offs

- **Breaking rename with no current consumers** → Low risk today (grep confirms nothing references the old tokens), but any in-flight branch that already started building a page against the placeholder names will break. Mitigation: this change ships early, before any presentation code exists beyond the app-shell.
- **New npm dependencies** (`@fontsource/outfit`, `@fontsource/geist`) → adds two small packages. Mitigation: both are static font-file packages with no runtime JS, so no bundle-size surprise beyond the font files themselves, and only the weights actually used are imported.
- **Tailwind v4 `@utility` usage for typography steps** is a slightly less common pattern than plain `@theme` tokens → Mitigation: keep the `@utility` block colocated in `theme.css` (or a clearly-named `src/styles/typography.css` imported next to it) with a one-line comment mapping each class back to its Figma step name.

## Migration Plan

1. Add font packages, `src/styles/fonts.css`, and import it from `index.css` ahead of `theme.css`.
2. Replace the `@theme` color tokens in `theme.css` with the Figma set; add font-family tokens.
3. Add the typography `@utility` classes for the eight type-scale steps.
4. Manually verify in the browser: load the app, confirm computed styles show Outfit/Geist (not a fallback), and confirm color tokens resolve to the exact hex values via devtools.
5. No data migration, no feature flag — this is a static CSS/token swap with no runtime consumers yet, so it ships in one step with no rollback complexity beyond reverting the commit.
