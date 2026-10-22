> **Superseded by `audit-and-harden-api-and-web`** (2026-10-20). Its still-valid items moved into that change's web tasks §8 (design D15). Do not apply this change. It will be deleted, not archived.

## Why

A full audit of `src/` found that the 11 admin CRUD pages (buildings,
departments, branches, floors, security gates, reception desks, workflows,
visitor categories, roles, host employees, plus the audit-trail/dashboard
pages) each copy-paste the same page shell, error-retry block, status
badge, and auth-guard/current-user-fetch logic rather than reusing shared
primitives that already exist one layer up (`components/ui/*`,
`AdminLayout`). The team's own `openspec/changes/improve-listing-ux/`
change deliberately kept each page's data-fetch hook separate — this
proposal does not revisit that decision. It targets only the duplication
that decision left on the table: the JSX chrome around each page, a
handful of small hooks/utils, and one redundant network call every admin
page fires needlessly. Fixing it now, before an 12th admin page is added,
keeps future pages a few lines of composition instead of another 90-line
copy.

## What Changes

- Add an `ErrorState` component to `components/ui/` (alongside the
  existing `LoadingState`/`EmptyState`) and replace the 17 duplicated
  error-retry JSX blocks with it.
- Add a `StatusBadge` component and replace the 8 duplicated
  Active/Inactive badge implementations with it.
- Add a `FormPageHeader` component (back button + title) and replace the
  8 duplicated header blocks in the admin `*-form.tsx` pages with it.
- Extract an `AdminListPageShell` composition component (header row,
  filter-panel slot, error/loading/empty branching, table + `Pagination`
  wiring) and adopt it in the 8 admin list pages that share this exact
  shell shape today — as page-shell composition only, not a change to any
  page's data-fetching hook or the `usePagedList`/fetch boundary
  `improve-listing-ux` deliberately preserved.
- Move the `sessionStorage.getItem('token')` admin auth-guard check out of
  28 individual page hooks and into one route-level guard (in
  `AdminLayout` or a dedicated guard wrapping the `/admin/*` routes in
  `App.tsx`), executed once per navigation instead of once per hook.
- Remove the redundant `getCurrentStaffUserUseCase.execute()` call from
  the 12 hooks whose page component never reads the result; where a page
  does need the current user (e.g. `admin-dashboard`), read it from
  `AdminLayout`'s already-fetched value via context instead of
  re-fetching.
- Extract the duplicated dnd-kit reorder logic (`admin-form-builder`'s
  three near-identical `handle*DragEnd` functions) into one `moveItem`
  helper.
- Unify `VisitorFormEntry`/`createEmptyVisitorFormEntry` and
  `StaffVisitorFormEntry`/`createEmptyStaffVisitorFormEntry` into one
  shared shape parametrized on the field-value type.
- Replace the 13 inline-duplicated pagination envelope shapes in
  `domain/entities/*-schema.ts` with the existing shared
  `PaginationMetaSchema`.
- Add a `text-field-label` design token to `theme.css` and replace the 7
  locally-duplicated (and slightly inconsistent) `#475569` label-color
  constants with it.
- Memoize `DepartmentsTable`'s per-render `Map` construction with
  `useMemo`.
- No visible UI change, no route change, no changed prop contracts on any
  page-level component, no changed API request/response shape — every
  item is a structural/internal refactor behind the current rendered
  output and behavior.

## Capabilities

No spec-level behavior changes: every item is an internal
component-extraction, hook-consolidation, or duplication-removal change
that preserves current rendered markup, styling, navigation, and API
interaction for every page touched. `skip_specs: true` is set in this
change's `.openspec.yaml` accordingly — see `design.md` for how visual and
behavioral equivalence is verified per item.

### New Capabilities
(none)

### Modified Capabilities
(none — see above)

## Impact

- **Code**: `components/ui/` (new `ErrorState`, `StatusBadge`), a new
  `AdminListPageShell` and `FormPageHeader` (location per `design.md`),
  `AdminLayout.tsx`/`App.tsx` (auth guard consolidation, current-user
  context), the 8 `admin-*` list-page + hook pairs, the 8 `admin-*-form.tsx`
  pages, `admin-form-builder`'s three drag-end handlers,
  `visitor-request/types.ts` + `staff-visitor-registration/types.ts`, the
  13 `*-out-schema.ts` files under `domain/entities/`, `theme.css`, and
  `DepartmentsTable.tsx`.
- **Tests**: existing component/page tests (if present) must keep
  asserting the same rendered output and interaction behavior; any test
  that asserted on now-removed duplicated markup verbatim gets updated to
  assert through the new shared component instead, without changing what
  it verifies.
- **No** backend/API contract changes, no new dependency, no routing
  changes, no visual/design change beyond consolidating the already
  slightly-inconsistent label color onto one token value (see
  `design.md` for which of the two prior variants becomes canonical).
