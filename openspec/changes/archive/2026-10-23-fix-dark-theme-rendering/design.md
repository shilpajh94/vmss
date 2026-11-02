## Context

The dark theme is a pure token override: `:root[data-theme="dark"]` in
`src/styles/theme.css` redefines `--color-*`, and every utility reads those
variables (add-calendar-colours-and-theme-modes). `check-theme-colors.mjs`
already blocks hex classes and `bg-white`/`bg-black` in staff/admin code, and
no raw Tailwind palette classes (`bg-slate-50`…) remain. So the leftover
defects are **token misuse and native-control behaviour**, not hard-coded
colours.

Evidence comes from a scripted audit run on 2026-10-23 against the dev server:
23 staff/admin routes in dark at 1440×900, with a computed-style contrast scan
and a check for transparent `<select>`s. A second run loaded each route in
light, switched to Dark through the top-bar control, and diffed every
element's computed colours against a fresh dark load. That diff was **0 on all
9 routes tested**, so `switchTheme` / `useApplyTheme` are not at fault, and
this change does not touch them.

Findings it produced, which define the scope:

1. `DropdownFilter` renders `<select class="bg-transparent text-text">`.
   Chromium's option popup falls back to a white canvas but inherits the light
   `text-text` colour, so the options are unreadable. Flagged on
   `/staff/invitations` and `/admin/invitations` (4 each), `/admin/audit-trail`
   (2), and the branch pickers on `/admin/dashboard`, `/staff/calendar` and
   `/reception/dashboard`.
2. `bg-bg` is used for both the page canvas and for things sitting *on*
   cards. Light: both `#FFFFFF`, so it looks fine. Dark: `#020617` inside a
   `#0F172A` card, which reads as a hole (Form Builder buttons, for example).
3. The Register Visitor footer is `bg-surface` while the page canvas behind it
   is `bg-bg`, which shows as a lighter band in dark.
4. The dark `primary` (`#E2E8F0`) turns the wizard's Next into a glaring
   near-white slab, and `border-primary` gives Cancel a near-white outline.
5. `bg-border text-text-muted` (StepMarker, the bell's zero badge) is about
   4.0:1 in both themes.

## Goals / Non-Goals

**Goals:**
- Fix each finding above at its root (token or shared component), not with
  per-page `dark:` patches.
- Keep the light theme pixel-identical except the two contrast fixes.
- Make findings 1 and 2 hard to reintroduce.

**Non-Goals:**
- Theme-switch mechanics (proven sound, see Context).
- The sidebar active item's 4.17:1 contrast. The sidebar is fixed in both
  themes and its accent is a brand decision.
- Replacing native `<select>` with a custom listbox.
- Public (always-light) pages.

## Decisions

### D1. Theme the option popup with a base rule, and give the select a real background
Add to `@layer base` in `index.css`:
`option, optgroup { background-color: var(--color-surface); color: var(--color-text); }`.
In addition, change `DropdownFilter`'s `<select>` from `bg-transparent` to
`bg-surface`, which is the same colour as its wrapper, so nothing changes
visually.

- *Why both:* Chromium on Windows takes popup colours from `option` styles.
  Firefox and some Chromium builds derive them from the `<select>`'s own
  background. The base rule fixes every select in the app at once, including
  the form-builder and modal selects that weren't flagged. The `bg-surface`
  change removes the transparent background that causes the mismatch.
- *Alternative rejected:* fixing only `DropdownFilter`. That leaves the
  correctness of every other select dependent on its classes.
- Public pages force light, so the rule resolves to white/navy there, which is
  unchanged.

### D2. New `surface-inset` token; `bg-bg` is reserved for the page canvas
Add `--color-surface-inset`: `#FFFFFF` in light (what those call sites render
today) and `#1E293B` in dark (slate-800, one step above the card, the same as
`surface-muted`). The two tokens are kept separate because `surface-muted` is
`#F8FAFC` in light, and swapping to it would tint every inset in the light
theme.

Each `bg-bg` call site is classified as follows:

| Keep `bg-bg` (page canvas) | Move to `bg-surface-inset` | Move to `bg-surface` (bordered button on a card) |
|---|---|---|
| `AppShell.tsx` shell, `PublicLayout.tsx` fallback, `not-found.tsx`, `route-error.tsx`, `ResponsiveBoard.tsx` sticky tab strip (sits on the canvas) | `EmptyState` icon circle; `RepeatableFieldGroup` thead, sticky Actions `th`, and item panel; `ExportInvitationsModal` summary; `VisitorInfoModal` panels (×2); `StepCard` icon tile; `GroupCard` / `SortableFieldRow` pills; step-editor locked rows | `StepCard` "Edit Fields"; `FieldPropertiesPanel` secondary button |

`ExportInvitationsButton`'s `hover:bg-bg` becomes `hover:bg-surface-muted`. In
dark the hover must lighten, not darken. In light this is a near-invisible
`#F8FAFC` tint where today there is none, which is acceptable for a hover
state.

### D3. Register Visitor footer uses the canvas colour
Change the footer's `bg-surface` to `bg-bg`. Below `lg` the bar is sticky over
scrolling content, and the canvas colour stays opaque, so content still can't
show through. At `lg`+ it is static on the canvas, so the band disappears.
Light is unchanged (both `#FFFFFF`).

### D4. Dark `primary` = brand cyan `#22D3EE`; Cancel gets a quieter dark outline
Change only the dark override of `--color-primary`, to `#22D3EE` (the dark
`secondary-accent`, the cyan already used by the wizard's step marker and
Individual pill). `on-primary` stays `#0F172A`, about 10:1 on cyan. This
changes every `bg-primary` user in dark at once: the wizard's Next, the
`ConfirmDialog` primary variant, the active `ResponsiveBoard` tab and the
not-found actions. The `text-primary` checkbox tint also turns cyan, which
fits.

- *Why cyan, not admin teal:* the wizard and board are staff surfaces, where
  cyan is the established accent. `ConfirmDialog` appears in admin too, but
  cyan next to teal reads as one accent family. Splitting `primary` per portal
  is not worth a second token.
- Cancel adds `dark:border-border-strong dark:text-text` (the `dark:` variant
  is sanctioned for "the rare class that genuinely differs"). Light keeps its
  navy outline. A cyan outlined Cancel beside a cyan filled Next would compete
  with it.

### D5. Contrast: `text-muted` → `text-secondary` on `bg-border` chips
`StepMarker` (unreached step) and `NotificationBell` (zero count). Light:
`#475569` on `#E2E8F0` ≈ 6.9:1. Dark: `#CBD5E1` on `#334155` ≈ 7.6:1.
`StepMarker` is shared with the always-light visitor wizard, which gets the
same improvement.

### D6. Guards
- **Lint.** `check-theme-colors.mjs` gains a `bg-bg` rule. It is allowed in a
  `CANVAS_FILES` allowlist (`AppShell`, `PublicLayout`, `not-found`,
  `route-error`, `ResponsiveBoard`) or on a line carrying a `page-canvas`
  marker (a `/* page-canvas */` JSX comment, used for the wizard footer).
  Elsewhere it fails with "use surface-inset / surface". A file-level
  allowlist alone would also have exempted the whole registration page.
- **Unit test.** `tests/unit/theme-tokens.test.ts` parses `theme.css` and
  asserts that `on-primary` on `primary` and `text-secondary` on `border` meet
  4.5:1 in both themes, and that dark `surface-inset` is lighter than dark
  `surface`. The token contracts in the spec become executable.
- **Audit script.** `scripts/dark-theme-audit.py` (plus an npm script
  `audit:dark`, same Docker/Playwright pattern as `npm run screenshots`):
  1. Logs in and forces dark mode.
  2. Screenshots the route list.
  3. Reports sub-AA text and `<select>`s whose computed background is
     transparent.
  4. Exits non-zero on any transparent select.
  It also has an optional `--switch` mode that diffs a live switch against a
  fresh dark load. It needs a running dev server, so it is a manual
  pre-release check like `screenshots`, not part of `npm run lint`. It
  formalises the scratch audit that produced this change.

## Risks / Trade-offs

- [A native popup's look varies by OS/browser] → D1 covers both the
  `option`-styled and the `select`-derived engines. Manual check on
  Chrome/Edge (Windows, the reported environment) and Firefox in tasks.
- [The dark primary now reuses the accent hue, so "primary" and "accent" look
  alike in dark] → Accepted. The user chose a brand-accent primary. The two
  rarely sit side by side, and where they do (the wizard), the step marker is
  a status indicator, not a button.
- [The audit's contrast scan has false positives] → For example, the
  Individual pill: text over an absolutely positioned sibling. The script
  reports these for review. It only *fails* on transparent selects, which
  have no false positives.
- [Lint allowlist drift] → The allowlist is short and lives next to the
  existing `EXEMPT_DIRS`. A new canvas page either joins it or uses the
  marker, consciously.

## Migration Plan

Frontend-only. No API, storage or config change. Ship as one PR, and roll
back with a revert. Users' stored theme choice is untouched.
