## 1. Shared scrollbar utility

- [x] 1.1 Add a new `@utility scrollbar-thin` (or equivalently named) block
      to `src/styles/theme.css`, using the theme's light-surface tokens
      (not `.sidebar-nav-scroll`'s hardcoded dark colors), covering
      `scrollbar-width: thin`/`scrollbar-color` plus the `::-webkit-
      scrollbar*` equivalents.

## 2. Form Builder list page

- [x] 2.1 Wrap `admin-form-builder.tsx`'s heading region (title/description,
      tenant `<select>`, "Form Preview", "Publish Changes", "Registration
      Steps" sub-heading) in `PageContentLayout`'s fixed-heading slot.
- [x] 2.2 Shrink "Create Registration Step" from its current full-width
      banner button to a compact button (matching `p-btn-secondary`/
      `p-btn-primary` sizing) placed in the fixed heading row alongside
      "Form Preview"/"Publish Changes".
- [x] 2.3 Move the step-card grid into `PageContentLayout`'s scrollable
      body slot; apply the new `scrollbar-thin` utility to that region.
- [x] 2.4 Apply the same responsive wrapping pattern other migrated pages
      use for their heading action rows, so the denser Form Builder heading
      (more controls than a typical list page) still wraps cleanly on
      narrow viewports instead of overflowing or overlapping.
- [x] 2.5 Register `admin-form-builder`'s data fetch with `usePageRefresh`.

## 3. Form Builder step editor page

- [x] 3.1 Wrap `admin-form-builder-step-editor.tsx`'s heading in
      `PageContentLayout`'s fixed-heading slot, field-configuration content
      in the scrollable body slot.
- [x] 3.2 Register the step editor's data fetch with `usePageRefresh`.

## 4. Dashboard refresh consolidation

- [x] 4.1 Register `admin-dashboard.tsx`'s data fetch (`use-admin-
      dashboard.ts`) with `usePageRefresh`.
- [x] 4.2 Remove the Dashboard's own hand-rolled `RefreshCcwIcon` button and
      its `onClick={retry}` wiring, leaving refresh solely to the shared
      `AdminTopBar` control.

## 5. Organisation Configs refresh registration

- [x] 5.1 Register `admin-organisation-configs`'s data fetch
      (`use-admin-organisation-configs.ts`) with `usePageRefresh`.

## 6. Verification

- [x] 6.1 `tsc -b` and `oxlint` pass clean.
- [x] 6.2 Manually verify in a browser: Form Builder's heading (tenant
      selector, Form Preview, Publish Changes, Create Registration Step)
      stays fixed while the step-card grid scrolls independently, with a
      thin/low-contrast scrollbar; step cards are fully visible (no
      icon-without-label clipping) when scrolled to any position.
      Confirmed working by user.
- [x] 6.3 Manually verify: Form Builder, its step editor, Organisation
      Configs, and the Dashboard each show exactly one refresh control (the
      shared `AdminTopBar` one), it spins while in flight, and its "last
      updated" label updates after a manual refresh on each of those pages.
      Confirmed working by user.
- [x] 6.4 Manually verify narrow-viewport behavior for the Form Builder
      heading row (no overlapping/clipped controls).
      Confirmed working by user.

**Note on 6.2-6.4**: no browser/screenshot tool was available in this
implementation environment, the same limitation `improve-listing-ux`'s own
tasks.md flagged for its equivalent items. All code-level work for these
(layout structure, `scrollbar-thin` application, single shared refresh
control wiring, responsive `flex-wrap` on the heading rows) is done and
`tsc -b`/`oxlint`/`vite build` all pass clean; the rendered result was then
manually confirmed by the user directly.
access, to visually confirm before checking these off.
