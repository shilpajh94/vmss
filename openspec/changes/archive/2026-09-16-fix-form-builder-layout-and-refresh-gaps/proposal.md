## Why

The `improve-listing-ux` change (already implemented) built shared
infrastructure — `PageContentLayout` (pins a page's heading/filter/primary-
action row while only its data region scrolls), `RefreshContext` (one shared
refresh control in `AdminTopBar`, replacing per-page refresh buttons), and a
spacing token scale — and rolled it out to eleven admin list pages. The Form
Builder page (`/admin/form-builder`, and its step-editor sub-route) was built
after that rollout and never migrated: its heading, tenant selector, "Form
Preview"/"Publish Changes" controls, and full-width "Create Registration
Step" button all scroll away with the step cards, because the whole page is
one fragment inside `AppShell`'s single scrolling `<main>` — the exact
per-page problem `improve-listing-ux` fixed everywhere else. A screenshot of
a step card row cut off mid-scroll (icons visible, labels not) reads as
"steps are missing," but is a symptom of the same unpinned-header gap: with
no fixed heading to anchor against and no bounded scroll region of its own
for the card grid, the browser's default scrollbar gives no orientation cue.
Separately, an audit of `RefreshContext` registration found three more admin
pages that fetch on mount but never registered: Form Builder, its step
editor, and Organisation Configs; a fourth, the Dashboard, has its own
hand-rolled refresh button that bypasses the shared control entirely,
producing a visibly inconsistent (and, on the Dashboard, duplicated) refresh
affordance across the admin portal.

## What Changes

- Migrate `admin-form-builder` (list page) to `PageContentLayout`: pin the
  title/description, tenant selector, "Form Preview"/"Publish Changes"
  controls, and the "Registration Steps" heading into the fixed region; only
  the step-card grid scrolls beneath it.
- Shrink "Create Registration Step" from a full-width banner button to a
  compact button placed in the fixed heading row, to the left of "Form
  Preview"/"Publish Changes" — the same row-of-actions placement every other
  migrated admin list page uses for its primary "Add" action, not a separate
  full-width row competing with the cards for space.
- Give the step-card grid its own bounded, independently scrollable region
  and add a reusable thin/near-invisible scrollbar utility (extending
  `theme.css`) for it, since the only existing scrollbar-styling precedent
  (`.sidebar-nav-scroll`) is hardcoded for the dark sidebar and not reusable
  on a light card surface.
- Migrate the Form Builder step-editor page to `PageContentLayout` the same
  way, for the same reason (its own fetch-on-mount data with no pinned
  heading).
- Register `admin-form-builder`, the step editor, and
  `admin-organisation-configs` with `RefreshContext` (`usePageRefresh`), and
  replace the Dashboard's hand-rolled refresh button with the shared
  `AdminTopBar` control so every admin page uses one consistent refresh
  affordance. **BREAKING** (internal only): the Dashboard's local refresh
  button element is removed in favor of the shared control, matching the
  precedent already set for the eleven `improve-listing-ux` pages.

## Capabilities

### New Capabilities
- `admin-form-builder`: the Form Builder admin page's layout and behavior
  (registration-step list, step editor, publish workflow) — no spec exists
  for this capability today even though the page has shipped; this change
  establishes its baseline spec alongside the layout fixes.

### Modified Capabilities
- `live-data-refresh`: extend the "manual refresh control" requirement's
  coverage to explicitly include every admin page that fetches on mount
  (Form Builder, its step editor, Organisation Configs, and the Dashboard),
  and require that coverage be met via the one shared `RefreshContext`
  control rather than a page-local, hand-rolled button — `admin-dashboard`'s
  spec has never documented a refresh requirement of its own, so this is
  where the Dashboard's refresh behavior becomes specified for the first
  time.

## Impact

- `src/presentation/pages/admin-form-builder/admin-form-builder.tsx` and its
  `Components/` (step cards, create-step modal) and `hooks/` files.
- `src/presentation/pages/admin-form-builder/admin-form-builder-step-editor.tsx`
  and its hook.
- `src/presentation/pages/admin-dashboard/admin-dashboard.tsx` (remove
  hand-rolled refresh button).
- `src/presentation/pages/admin-organisation-configs/` hook (register with
  `RefreshContext`).
- `src/styles/theme.css` (new thin-scrollbar utility).
- No backend/API changes. A separate, unrelated backend issue (a 500 on
  visitor-registration submission, traced to `VMSS_API`'s default-host-role
  resolution, not to form-builder rendering) is addressed by the paired
  change `fix-registration-host-role-crash` in `VMSS_API`.
