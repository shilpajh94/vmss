## Context

`PageContentLayout`, `RefreshContext`/`usePageRefresh`, `Pagination`, and the
`theme.css` spacing tokens (`p-page-content`, `gap-page-section`,
`p-btn-secondary`, `p-btn-primary`, `p-filter-panel`) already exist from
`improve-listing-ux` and are wired into eleven admin list pages plus
`AdminTopBar.tsx`. Form Builder (`admin-form-builder.tsx`,
`admin-form-builder-step-editor.tsx`) and Organisation Configs were built
outside that rollout and never adopted them; the Dashboard predates it and
has its own inline `RefreshCcwIcon` button (`admin-dashboard.tsx`) wired
directly to its own `retry` function instead of `RefreshContext`. See
proposal.md for why this matters to users.

## Goals / Non-Goals

**Goals:**
- Bring Form Builder (list + step editor) onto the same fixed-heading/
  scrollable-body pattern as every other admin page, with no new pattern
  invented for it.
- Close every remaining `RefreshContext` registration gap under
  `AdminLayout` in one pass, rather than fixing Form Builder alone and
  leaving Organisation Configs/Dashboard for a future report.
- Add a single, reusable thin-scrollbar utility rather than a one-off style
  scoped to the Form Builder grid.

**Non-Goals:**
- Migrating Form Builder to the shared paged-list hook (`use-paged-list.ts`)
  or adding server-side pagination/filtering to its steps list — registration
  steps per branch are a small, bounded set (today: single digits), unlike
  the large collections `improve-listing-ux` paginated. No pagination
  controls are added here.
- Changing anything about `StaffLayout` pages (`staff-audit-trail`,
  `staff-dashboard`, `staff-visitor-registration`) — they have no
  `RefreshProvider` at all, which is a separate, larger gap out of scope for
  this change.
- Any backend change. The visitor-registration 500 error from the third
  screenshot is a `VMSS_API` bug (default-host-role resolution), addressed
  by the paired `fix-registration-host-role-crash` change in that repo, not
  by anything in this change.

## Decisions

- **Reuse `PageContentLayout` as-is, no new layout component.** Form
  Builder's heading is more complex than a typical list page's (title +
  description + tenant `<select>` + two action buttons, then a second
  "Registration Steps" sub-heading + a third action button), but
  `PageContentLayout`'s contract is "whatever you put in its heading slot
  stays fixed" — it doesn't need to know the heading's internal structure.
  Alternative considered: a bespoke sticky-header wrapper for this one page.
  Rejected — it would duplicate `PageContentLayout`'s flex/height mechanics
  for no behavioral difference, which is exactly the kind of per-page drift
  `improve-listing-ux` eliminated.
- **"Create Registration Step" moves into the fixed heading row, sized like
  `p-btn-secondary`/`p-btn-primary`, instead of staying a full-width banner.**
  This mirrors where every migrated list page puts its own primary "Add"
  action (next to Filters, in the fixed row) — Form Builder becomes
  consistent with that placement instead of being the one page with a
  full-width action button between the heading and its cards.
- **New scrollbar utility, not reuse of `.sidebar-nav-scroll`.** That class
  is a component-scoped, dark-surface-only style (`index.css:33-53`) with
  colors hardcoded for the sidebar's background. Add a new `@utility
  scrollbar-thin` (or similarly named) block to `theme.css` next to the
  existing spacing utilities, using `theme.css`'s light-surface tokens so it
  is reusable anywhere a bounded scroll region needs a low-contrast
  scrollbar — the step-card grid today, and any future bounded-scroll region
  without redefining colors per call site.
- **Dashboard's refresh button is deleted, not kept as a fallback.** Once
  `admin-dashboard.tsx` registers with `usePageRefresh`, keeping its own
  button too would show two refresh controls for one page. This matches how
  every `improve-listing-ux` page's own button was removed in favor of the
  shared control, not kept alongside it.
- **Organisation Configs gets `usePageRefresh` only — no layout change.**
  It's a single settings record, not a list; nothing in the bug report or
  audit found a scroll/heading problem there, only the missing refresh
  registration.

## Risks / Trade-offs

- [Risk] Moving "Create Registration Step" into a denser heading row could
  make it easy to misclick against "Form Preview"/"Publish Changes" on
  narrow viewports → Mitigation: apply the same responsive wrapping
  `improve-listing-ux` already uses for other pages' heading action rows
  (wrap to a second line under the title on narrow widths) rather than
  forcing all controls onto one row unconditionally.
- [Risk] A bounded scroll region for the step-card grid, sized to the
  viewport, could make a tenant with very few steps look like it has empty
  wasted space below a short card grid → Mitigation: size the scroll
  region's max-height to the available viewport space (`flex-1`, as
  `PageContentLayout` already does elsewhere), so it naturally shrinks to
  fit fewer cards rather than reserving a fixed tall region.
- [Trade-off] No automated visual/browser verification is available in this
  environment for the sticky-layout and scrollbar-appearance requirements
  (same limitation `improve-listing-ux`'s tasks.md flagged for its own
  rollout) → tasks.md calls this out explicitly as a manual verification
  step rather than claiming it done from code review alone.
