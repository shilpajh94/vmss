## Why

After switching the staff or admin portal to the dark theme, several surfaces
are broken or jarring. The worst is the invitation board's filter dropdowns:
their option list opens as a white panel with near-white text, so it can't be
read. Other problems are near-black "holes" inside dark cards, a mismatched
footer band on Register Visitor, a glaring near-white primary button, and a
few small-text contrast misses.

A dark-mode audit of 23 staff/admin routes (2026-10-23) showed the live switch
itself is sound: a page switched light → dark matches a fresh dark load on
every element. The defects are in how particular components render in the
dark theme, not in the switching mechanism.

## What Changes

- **Native dropdown option lists follow the theme.** Every `<select>` option
  list (filter bars, form selects, the branch pickers) opens with a dark
  surface and readable text. The root cause is `DropdownFilter`'s transparent
  `<select>`: Chromium paints the option popup on white but keeps the light
  text colour. It affects the invitations boards (staff + admin), the audit
  trail, and the dashboard, calendar and reception branch pickers.
- **No near-black insets inside cards.** Controls, pills, icon tiles and inset
  panels that sit *on* a card used the page-canvas colour (`bg-bg`). That
  colour is white in light (invisible there) but near-black in dark: the Form
  Builder "Edit Fields" buttons and step icons, field-type pills, the Visitor
  Info modal panels, the Export modal summary, repeatable-field tables, the
  empty-state icon circle and the Export button's hover. They move to a
  surface token that stays white in light and lifts above the card in dark.
- **Register Visitor footer matches the page.** The Cancel/Next bar no longer
  shows a lighter band against the page canvas in dark.
- **Primary buttons use the brand accent in dark.** The dark `primary` token
  changes from light grey `#E2E8F0` to the cyan brand accent, keeping dark
  text on it. This covers the wizard's Next, confirm dialogs, the active board
  tab and the not-found actions. The outlined Cancel next to it gets a quieter
  `border-strong` edge in dark. The light theme is unchanged.
- **Small-text contrast fixes.** The inactive step numbers in the stepper and
  the zero count on the notification bell move from `text-muted` on `border`
  (≈4.0:1, below AA in both themes) to `text-secondary`.
- **Regression guard.** `check-theme-colors.mjs` also rejects `bg-bg` outside
  the page-canvas layouts. A committed dark-theme audit script screenshots the
  main routes in dark and flags sub-AA text and transparent selects.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `theme-mode`: "Every staff and admin surface follows the theme" gains
  explicit requirements for native dropdown option lists, card insets and
  sticky action bars in the dark theme.
- `design-theme`: the dark `primary` token value changes to the brand accent,
  and a new `surface-inset` token is added for controls placed on a card.

## Impact

- **Code (VMMS_WEB only):** `src/styles/theme.css` (dark `primary`, new
  `surface-inset` token), `src/styles/index.css` (base `option`/`optgroup`
  rule), `components/ui/DropdownFilter.tsx`, the ~13 `bg-bg` call sites listed
  in design.md, `staff-visitor-registration.tsx` (footer and Cancel),
  `StepMarker.tsx`, `NotificationBell.tsx`, `scripts/check-theme-colors.mjs`,
  plus a new `scripts/dark-theme-audit.py`.
- **Light theme:** visually unchanged, except the stepper numbers and the
  bell's zero count, whose text darkens slightly from slate-500 to slate-600
  for contrast.
- **Public pages** (visitor portal, logins) always render light and are not
  affected.
- **API:** none. No paired VMSS_API change.
- **Out of scope:** the sidebar's active item (white on `#0B8B84`, 4.17:1).
  It is fixed in both themes, unrelated to the switch, and deserves its own
  brand-colour decision.
