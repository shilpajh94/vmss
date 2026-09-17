## Why

A structural audit of every admin list page (branches, buildings, departments,
floors, host-employees, reception-desks, security-gates, visitor-categories,
invitations, roles, workflows) found the same four problems repeated across
the whole admin portal, not just on the Branches screen shown in the report:

1. Every "Filters" control (where one exists) narrows an already-fetched,
   full result set client-side instead of sending `page`/`pageSize`/filter
   query params to the API — so a page never actually pages, and a branch
   with thousands of rows would be fetched in one response. The Workflows
   page's "Filters" button is worse: it has no `onClick` at all. Roles has no
   filter control. The VMSS_API side already exposes typed filters and
   `page`/`page_size` on every one of these list endpoints (see the paired
   `add-listing-pagination-filtering` change in `VMSS_API` for the one
   remaining API-side gap) — the web layer is the part not using them.
2. The manual refresh control is duplicated once per page (`AdminTopBar.tsx`
   has no refresh control at all), each a hand-rolled `RefreshCcwIcon` button
   next to Filters/Add, with no shared "when did this last update" indicator
   and no in-progress feedback beyond a static icon.
3. Each list page's section-heading row (title, Filters button, Add button)
   scrolls away with the table body, because both live in the same scroll
   container (`AppShell.tsx`'s single `<main className="overflow-y-auto">`)
   — confirmed structurally identical across all nine CRUD list pages, not
   just Branches.
4. There is no defined spacing/padding scale — `theme.css` defines color and
   type tokens but no `--space-*` scale — so padding is consistent today only
   because every page was copy-pasted from the same template, with nothing
   to catch a future page that drifts from it.

## What Changes

- Wire every admin list page's existing (or, for Workflows/Roles, newly
  added) filter controls to send their selected values as query params to
  the API, replacing in-memory `.filter()` narrowing.
- Add real pagination (page controls + page size) to every admin list page,
  driven by the API's `pagination.page`/`pageSize`/`total`/`totalPages`
  response block, replacing "fetch everything, render it all."
- Add a Filters panel to the Workflows page (Visitor Category, Status) and
  the Roles page (Status), and wire the Invitations page's existing
  free-text search to the server plus a new Filters panel (Status,
  Registration Type, Source) — mirroring what the API already accepts.
- Remove the per-page manual refresh button; add one shared manual refresh
  control to `AdminTopBar.tsx`, positioned next to the notification bell,
  that spins while a refresh is in flight and shows a "Last updated
  <relative time>" label beside it. **BREAKING** (internal only): pages that
  today render their own refresh button lose it; they must adopt the shared
  top-bar control instead of hand-rolling one.
- Introduce a shared page-content layout so a page's own heading/Filters/Add
  row stays pinned while only the table/list body beneath it scrolls,
  extending the existing sidebar/top-bar-fixed behavior one level deeper.
- Define a spacing/padding token scale in `theme.css` and apply it across
  list-page layouts, replacing the current copy-pasted, unnamed pixel values.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `admin-branches`: filtering sends the selected status to the server instead
  of narrowing an in-memory list; the list becomes paginated.
- `admin-buildings`: filtering (Branch, Status) becomes server-driven; the
  list becomes paginated.
- `admin-departments`: filtering (Branch, Status) becomes server-driven; the
  list becomes paginated.
- `admin-floors`: filtering (Building, Access Level, Status) becomes
  server-driven; the list becomes paginated.
- `admin-host-employees`: filtering (Department, Role, Status) becomes
  server-driven; the list becomes paginated.
- `admin-reception-desks`: Floor and Status filtering becomes server-driven;
  the list becomes paginated. Building stays a client-side narrowing of the
  Floor field's options only — a reception desk has no `buildingId` on the
  API, only `floorId` — never sent to the server by itself.
- `admin-security-gates`: filtering (Building, Gate Type, Security Level)
  becomes server-driven; the list becomes paginated.
- `admin-visitor-categories`: filtering (Badge Color, NDA Requirement, Escort
  Requirement) becomes server-driven; the list becomes paginated.
- `admin-invitations`: search becomes server-driven; a new Filters panel
  (Status, Registration Type, Source) is added. The board's underlying fetch
  is NOT paginated in the page-controls sense — see Impact below for why a
  Kanban-style status board is a deliberate exception to the "add
  pagination to every listing" rule.
- `admin-roles`: the list becomes paginated. **Correction during
  implementation**: the originally planned Status filter panel was dropped
  — `Role` has no active/inactive concept in the API (only a computed
  Standard/Custom distinction based on name), so there is no field to
  filter on. See the paired `add-listing-pagination-filtering` change in
  `VMSS_API` for where this was confirmed.
- `admin-approval-workflows`: the previously non-functional "Filters" button
  gains a real filter panel (Visitor Category, Status), sent server-side.
  **Correction during implementation**: NOT given page-forward/page-back
  pagination — like the Invitations board, this page groups rows (approval
  levels) by visitor category, and a page-by-page fetch could split one
  category's levels across two pages. The underlying fetch is bounded (a
  generous `pageSize`) instead, matching the Invitations exception.
- `live-data-refresh`: the manual refresh control moves from a per-page
  button to one shared control in the admin top bar, gains an in-progress
  spin animation, and gains a "last updated" timestamp shown beside it.
- `app-shell`: adds a requirement that a page's own heading/Filters/Add row
  stays fixed while only that page's data region scrolls beneath it,
  alongside the existing sidebar/top-bar-fixed requirement.
- `design-theme`: adds a defined spacing/padding token scale that page
  layouts and components use instead of ad hoc pixel values.

## Impact

- **Code**: every `src/presentation/pages/admin-*` list page and its
  `hooks/use-admin-*.ts` companion (branches, buildings, departments,
  floors, host-employees, reception-desks, security-gates,
  visitor-categories, invitations, roles, workflows);
  `src/presentation/components/AdminTopBar.tsx` (new shared refresh
  control); `src/presentation/components/AppShell.tsx` and a new shared
  page-content-layout component (sticky heading row / scrollable body split);
  `src/styles/theme.css` (new spacing tokens); `src/presentation/hooks/
  use-polling.ts` (already fires the 15s auto-refresh — the shared control
  reads its last-fetched timestamp rather than replacing it).
- **API usage**: each page's use-case call changes from "fetch everything"
  to passing `page`, `pageSize`, and its typed filter fields, matching what
  `VMSS_API`'s `org_structure`, `visitors`, `invitations`, and `audit_trail`
  routers already accept (per the audit backing this proposal). No API
  contract change is required from the web side except for `GET
  /auth/permissions`, covered by the paired `add-listing-pagination-filtering`
  change in `VMSS_API`.
- **Reference implementation**: `staff-audit-trail` already does
  server-side pagination and filtering correctly (`use-staff-audit-trail.ts`,
  `Components/Pagination.tsx`) and is the pattern the other list pages adopt
  — it is not itself modified by this change.
- **Out of scope**: `admin-dashboard` and `staff-dashboard` (widget/summary
  views, not paged listings) and `admin-organisation-configs` (a settings
  form, not a list) are unaffected.
- **Deliberate exception — Invitations Kanban board is not paginated**: its
  four status columns (Requested/Approved/Checked-in/Denied) each need an
  accurate total count and full membership to render correctly; fetching
  only "page 1" of the combined list would show some columns
  under-populated until an admin pages further, which is worse than today's
  behavior. This page keeps a single bounded fetch (raised to a page size
  generous enough for realistic invitation volumes) with real server-side
  filtering, rather than page-by-page controls. If invitation volume ever
  outgrows a single bounded fetch, a per-column paged/virtualized board is
  a follow-up change, not this one.
