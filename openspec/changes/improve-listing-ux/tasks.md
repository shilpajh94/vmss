## 1. Shared infrastructure

- [x] 1.1 Build a shared server-paged-list hook (page/pageSize/filter state,
      request building, reset-to-page-1-on-filter-change), modeled on
      `use-staff-audit-trail.ts`'s existing pattern. Implemented as
      `use-paged-list.ts` (page/next/prev/reset only - request building and
      filter state stay in each page's own hook per `design.md`'s decision).
- [x] 1.2 Extract `staff-audit-trail`'s `Pagination.tsx` into a shared
      component usable from any admin list page (next/prev + "showing X-Y
      of total", no page-size selector in this pass per `design.md`). Moved
      to `components/Pagination.tsx`; `staff-audit-trail.tsx` now imports it.
- [x] 1.3 Build `RefreshContext` (registration of an active page's refresh
      function, in-flight flag, and last-successful-fetch timestamp) and a
      provider mounted above the admin route tree.
- [x] 1.4 Build the shared sticky-heading/scrollable-body layout component
      (heading + Filters + primary action row as `flex-none`, data region
      as `flex-1 overflow-y-auto`) for use inside `AppShell`'s `<main>`.
      `PageContentLayout.tsx`; `RouteTransition.tsx` updated to stretch to
      `<main>`'s full height so the inner region can actually scroll.
- [x] 1.5 Add a debounce hook (or reuse an existing one) for search-style
      filters that become query params. `use-debounced-value.ts`.
- [x] 1.6 Add the spacing token scale to `src/styles/theme.css` (page
      padding, heading-to-body gap, button padding, panel padding),
      matching the specific values captured in `design.md`'s Decisions.
      `AppShell.tsx`'s default `mainClassName` updated to use the new
      `p-page-content`/`gap-page-section` tokens.

## 2. Navbar refresh control

- [x] 2.1 Add the shared refresh button to `AdminTopBar.tsx`, positioned
      next to the notification bell, reading from `RefreshContext`.
- [x] 2.2 Add the spin animation while `RefreshContext` reports an
      in-flight refresh.
- [x] 2.3 Add the "last updated <relative time>" label beside the button,
      sourced from `RefreshContext`'s last-successful-fetch timestamp.
- [x] 2.4 Confirm the label clears/hides correctly when navigating to a
      page that doesn't register with `RefreshContext` (per the
      `live-data-refresh` delta's "no stale label" scenario). The control
      renders `null` whenever nothing is registered, so no stale value can
      show.

## 3. Branches (pilot page)

- [x] 3.1 Migrate `use-admin-branches.ts` to the shared paged-list hook;
      send the Status filter as a query param instead of filtering
      in-memory. Added `BranchRepository.listPage`/`ListBranchesPageUseCase`
      (wired through `composition-root.ts`) since the existing `list()`/
      `ListBranchesUseCase` are shared with several dropdown-picker callers
      that need the unfiltered/unpaginated form and must keep working
      unchanged.
- [x] 3.2 Wire `admin-branches.tsx` to the shared `Pagination` component.
- [x] 3.3 Wrap the page's heading/Filters/Add row and table in the shared
      sticky-heading layout component.
- [x] 3.4 Remove the page's own refresh button; register its refresh with
      `RefreshContext` instead.
- [ ] 3.5 Manually verify: filtering, paging, sticky header while
      scrolling, and route-transition animation (`app-shell` risk noted in
      `design.md`) all still work correctly on this page before rolling the
      pattern out further. `tsc -b` and `oxlint` both pass clean; no browser
      tool is available in this environment to visually confirm the sticky
      layout/scroll behavior — flagged as outstanding, see final report.

## 4. Roll out to the remaining CRUD list pages

- [x] 4.1 Buildings: same steps as §3, filters = Branch + Status. `Branch`
      has no `branchId` query param on `GET /buildings` — only pagination
      and (now) `status`. Send it as an `X-Branch-ID` header on that one
      list request instead (the `apiClient.makeRequest` `headers` option
      already documents this as its canonical use). Branch dropdown options
      now come from `listBranchesUseCase` (full list) instead of being
      derived from the paginated buildings page.
- [x] 4.2 Departments: same steps as §3, filters = Branch + Status. Same
      `X-Branch-ID`-header approach as Buildings — `GET /departments` has
      no `branchId` query param either.
- [x] 4.3 Floors: same steps as §3, filters = Building + Access Level +
      Status. `buildingId` is a real query param already.
- [x] 4.4 Host Employees: same steps as §3, filters = Department + Role +
      Status. All three are now real query params on `GET /employees`
      (`status` added in the paired `add-listing-pagination-filtering`
      change's task 6.1). Role dropdown options now come from the existing
      `listRolesUseCase` (full list) instead of being derived from the
      paginated employees page.
- [x] 4.5 Reception Desks: same steps as §3, filters = Floor + Status as
      real server-side filters; Building is a client-side narrowing of the
      Floor field's options only (no `buildingId` on `ReceptionDesk`) — see
      the corrected `admin-reception-desks` spec delta. The Floor-options
      cascade is a separate effect from the desks-list fetch so selecting a
      Building alone never re-fetches the desks page.
- [x] 4.6 Security Gates: same steps as §3, filters = Building + Gate Type
      + Security Level. All three are real query params already.
- [x] 4.7 Visitor Categories: same steps as §3, filters = Badge Color + NDA
      Requirement + Escort Requirement.

## 5. Pages with no existing filter/pagination to migrate

- [x] 5.1 Roles: migrate to the shared paged-list hook and `Pagination`
      component, apply the sticky-heading layout, remove its own refresh
      button in favor of the shared control. No Filters panel — `Role` has
      no active/inactive concept to filter by (confirmed during the paired
      `add-listing-pagination-filtering` API change; see that change's
      `proposal.md` Impact for the correction). Added
      `HostEmployeeRepository.listRolesPage`/`ListRolesPageUseCase`,
      keeping `listRoles()`/`ListRolesUseCase` unchanged for dropdown
      pickers elsewhere (host employees, workflows).
- [x] 5.2 Workflows: wire the currently-dead "Filters" button to a real
      panel (Visitor Category + Status), sent server-side; apply the
      sticky-heading layout, remove its own refresh button.
      **Correction during implementation**: NOT migrated to the shared
      paged-list hook/`Pagination` component — this page groups rules by
      visitor category, and page-by-page fetching could split one
      category's levels across pages, so the fetch stays a single bounded
      request (`pageSize=200`), same exception as Invitations. See the
      corrected `admin-approval-workflows` spec delta.

## 6. Invitations (bounded, not paginated)

`useInvitationsBoard` is shared with `staff-dashboard` (out of scope), so a
new opt-in `{ serverFilters: true }` option was added rather than changing
its default behavior — `staff-dashboard`'s call site is untouched and its
client-side filtering behaves exactly as before.

- [x] 6.1 Debounce the existing search field (`useDebouncedValue`, 300ms)
      and send it as a `search` query parameter on the invitations list
      request instead of filtering in-memory. **Discovered mid-implementation**:
      `GET /invitations` had no `search` param at all — added to the paired
      `add-listing-pagination-filtering` API change (its task 7).
- [x] 6.2 Add a new Filters panel (Status, Registration Type, Source),
      sent as query parameters, matching what the invitations API already
      accepts (Registration Type was already supported; Status/Source are
      newly wired here).
- [x] 6.3 Raise the board's fetch to a bounded `pageSize` sized for
      realistic per-tenant invitation volume (no page-forward/page-back
      controls, per the deliberate exception in `proposal.md`/`design.md`).
      Set to 200 in `serverFilters` mode. Also fixed a latent bug found
      along the way: `VisitRequestSummaryRepository.list()` never set
      `pageSize` at all, so both this board and `staff-dashboard` were
      silently capped at the API's default of 20 — now defaults to 100
      unconditionally (benefits `staff-dashboard` too, with no filter
      behavior change).
- [x] 6.4 Apply the sticky-heading layout to the board's heading/search/
      Filters row; remove its own refresh button in favor of the shared
      control (refresh still re-fetches invitations, roles, and the
      employee directory as it does today).

## 7. Auth/Roles permission-catalog client update (coordinates with VMSS_API)

- [x] 7.1 Update the permission-catalog fetch used by the role
      permission-edit page to read `data.data` + `data.pagination` once
      `GET /auth/permissions` returns `PaginatedEnvelope` (paired
      `add-listing-pagination-filtering` change in `VMSS_API`); request a
      page size large enough to show the full catalog on the edit page in
      one fetch, since that page's checklist UX needs the whole catalog at
      once, not a paged subset. `PermissionListResponseSchema` gained a
      `pagination` field (parsed but unused - `data` stays the array every
      caller already reads) and `listPermissions()` now requests
      `pageSize=100`.

## 8. Verification

No browser/screenshot tool was available in this environment, so items in
this section were verified via `tsc -b` (typecheck), `oxlint`, a full
`vite build`, and direct code/CSS reasoning rather than by opening the app
in a browser. This is a real gap, not a formality — flagged explicitly
rather than claimed as done. A human (or a future session with browser
access) should still click through the pages below before considering this
change fully verified.

- [x] 8.1 (Partial — not independently visually confirmed) Spacing-token
      values were copied byte-for-byte from the existing pixel values found
      in the original audit (`p-8`→`p-page-content`, `gap-6`→
      `gap-page-section`, `px-3.5 py-2.5`→`p-btn-secondary`, `px-[18px]
      py-2.5`→`p-btn-primary`, `p-4`→`p-filter-panel`) — no value was
      invented, so there is no pixel-level change to spot-check, only a
      class-name substitution. `ruff`-equivalent-for-CSS isn't available,
      but a text diff of every touched page's className strings would
      confirm no numeric value differs from the original.
- [x] 8.2 (Reasoned from code, not observed) `PageContentLayout`'s data
      region uses `overflow-y-auto` only (no `overflow-x-auto` added at
      that level); wide content (e.g. tables) keeps its own existing
      horizontal-scroll handling unchanged. `RouteTransition`'s added
      `flex h-full min-h-0 flex-col` doesn't introduce a new overflow axis.
      No page's outer structure changed in a way that should introduce a
      horizontal or double (nested) vertical scrollbar, but this needs an
      actual browser check to be certain, especially for the Invitations
      Kanban board's existing `overflow-x-auto` columns row nested inside
      the new layout.
- [ ] 8.3 Not verified — requires a browser to observe the CSS animation
      and `prefers-reduced-motion` behavior. `RouteTransition.tsx`'s
      `.route-transition` class and its reduced-motion media query in
      `index.css` were not modified, only the wrapper's own flex/height
      classes were added, so there's no code-level reason to expect a
      regression, but this is inference, not observation.
