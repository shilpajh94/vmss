## Context

See `proposal.md` - Why / What Changes for the full list and motivation.
The codebase already has real shared infrastructure (`components/ui/*`,
`components/Pagination.tsx`, `hooks/use-paged-list.ts`,
`context/refresh-context.tsx`, `context/page-header-context.tsx`,
`domain/entities/pagination-meta-schema.ts`) and one deliberate,
documented decision to *not* build a fully generic fetch-owning
`<PagedTable>` (`openspec/changes/improve-listing-ux/design.md`). This
design respects that boundary: nothing here changes how a page fetches or
holds its list data, only how much JSX/logic is copy-pasted around that
boundary.

## Goals / Non-Goals

**Goals:**
- Every extracted component/helper is a pure composition of markup or
  logic that already exists in each duplicate — no new visual design, no
  new interaction pattern.
- Each of the 11 items lands independently: adopting `AdminListPageShell`
  on `admin-buildings` doesn't require also touching
  `admin-departments` in the same commit.
- Where duplicates have small inconsistencies today (the two
  `#475569`-related class strings — one `font-semibold`, one
  `font-bold uppercase`), preserve the visible distinction as a variant
  prop rather than silently collapsing to one look — collapsing font
  weight/casing is a visual change this proposal is not authorized to
  make sight-unseen.

**Non-Goals:**
- No change to `use-paged-list.ts`, to any page's data-fetching hook
  signature, or to the fetch/state boundary `improve-listing-ux`
  established.
- No visual redesign — `ErrorState`/`StatusBadge`/`FormPageHeader`/
  `AdminListPageShell` reproduce today's exact markup and Tailwind classes
  from the most common existing instance, not a new design.
- No new routing/guard *behavior* — the auth-guard consolidation
  (`sessionStorage.getItem('token')` check) preserves the exact redirect
  target (`/admin/login`, `replace: true`) and timing (before render of
  protected content), only moves *where* the check runs.

## Decisions

**1. `ErrorState`** — new `components/ui/ErrorState.tsx`, props
`{ message: string; onRetry: () => void }`, reproducing the exact class
string (`"flex flex-1 flex-col items-center justify-center gap-4
rounded-xl border border-border bg-surface p-12 text-center"`) and retry
button markup shared by all 17 current call sites. Sibling to
`LoadingState`/`EmptyState` (same directory, same prop-naming convention:
checked against `LoadingState`'s existing prop names before finalizing).

**2. `StatusBadge`** — new `components/ui/StatusBadge.tsx`, props
`{ active: boolean; activeLabel?: string; inactiveLabel?: string }`
defaulting to `"Active"`/`"Inactive"`, reproducing the
`bg-success/15 text-success` / `bg-border-subtle text-text-muted` + dot
markup. The two table components with a differently-shaped local map
(`SecurityGatesTable.tsx`, `ReceptionDesksTable.tsx`) are checked
individually during implementation to confirm they map to the same two
visual states before switching — if either encodes a third state, it is
left as-is and noted in that task rather than forced into this component.

**3. `FormPageHeader`** — new component, props
`{ title: string; onBack: () => void }`, reproducing the
`"flex size-9 items-center justify-center rounded-full border
border-border bg-surface"` back-button markup. Location: alongside the
other page-level layout primitives (checked against where
`PageContentLayout` lives, since this is the same category of "page
chrome" component).

**4. `AdminListPageShell`** — takes the page's already-computed state
(`{ isLoading, error, isEmpty, onRetry }`) plus `header`, `filters`, and
`children` (the table) as props/slots; it owns only the
loading/error/empty branching and the outer flex layout, not the fetch
itself — this is the key distinction from the rejected `<PagedTable>`
design (`improve-listing-ux/design.md`), which would have owned fetching
too. Each of the 8 admin list pages keeps its own `use-admin-*` hook
call and passes the hook's `{ isLoading, error, ... }` into the shell.
Adopted per-page, not all 8 in one commit, so a subtle per-page
difference (if one exists) surfaces as a single-page diff, not buried in
a mass change.

**5. Auth guard consolidation** — the check moves into
`AdminLayoutContent` (`AdminLayout.tsx`, which already wraps every
`/admin/*` route per `App.tsx:64-100` and already fetches the current
user) as a `useEffect` that runs before rendering `children`/`<Outlet>`.
Alternative considered: a dedicated `<RequireAdminAuth>` wrapper route
component. Rejected only because `AdminLayoutContent` already runs
exactly once per protected-route render and already does the equivalent
current-user fetch — adding the guard there is zero new render passes,
versus introducing a second wrapper layer for no behavioral gain.

**6. Current-user context** — `AdminLayoutContent`'s existing
`getCurrentStaffUserUseCase.execute()` result is exposed via a new
`CurrentUserContext` (same pattern as `RefreshContext`/
`PageHeaderContext`, per the audit's own note that this is "the
idiomatic way to share cross-cutting state in this codebase"). The 12
hooks with a dead fetch drop the call entirely; `admin-dashboard` (the
one hook that legitimately uses the value) reads it from context instead
of fetching its own copy. This also removes the redundant `/auth/me`
call firing on every 15-second poll tick the audit flagged.

**7. `moveItem` helper** — a small
`moveItem<T>(items: T[], activeId: string, overId: string, getId: (t: T)
=> string): T[]` in a shared location (checked against where other small
array/DOM helpers already live, e.g. a `utils/` module, rather than
introducing a new one), replacing the three duplicated
`findIndex`/`splice`/`splice` bodies in `admin-form-builder`. Alternative
considered: dnd-kit's own `arrayMove` utility — used if it's already a
transitive dependency (dnd-kit ships one), avoiding a hand-rolled
version entirely; confirmed during implementation before writing new
code.

**8. Visitor form entry unification** — hoist the shared field list and
factory into one module (e.g. `visitor-form-entry.ts`) generic over the
`customFieldValues` type, imported by both `visitor-request/types.ts` and
`staff-visitor-registration/types.ts`, replacing
`VisitorFormEntry`/`StaffVisitorFormEntry` and their two factories with
one parametrized pair.

**9. Pagination schema dedup** — each of the 13 `*-out-schema.ts` files
replaces its inline `pagination: z.object({ page: ..., pageSize: ...,
total: ..., totalPages: ... })` with `pagination: PaginationMetaSchema`.
Verified field-for-field identical to the inline shape before replacing
each one (already confirmed identical across all 13 by the audit).

**10. `text-field-label` token** — added to `theme.css`. The two
existing variants (`font-semibold text-[#475569]` used by
`admin-buildings`/most pages, vs. `font-bold uppercase text-[#475569]`
used by 6 pages) are preserved as two distinct utility combinations built
on the one new color token — the token replaces only the duplicated hex
value, not the weight/casing difference, per the Goals section above.

**11. `DepartmentsTable` memoization** — wrap the existing
`new Map(employees.map(...))` in `useMemo(() => ..., [employees])`; no
behavior change, since the map's contents are already a pure function of
`employees`.

## Risks / Trade-offs

- [Reproducing 17 error-block instances into one `ErrorState` could miss
  a subtle per-page difference (a slightly different message string or
  an extra action button) that looks identical at a glance] → Each of
  the 17 call sites is diffed individually against the extracted
  component's rendered output during implementation (task list requires
  a visual check per page, not just "compiles"), and any site with a
  genuine extra element is left un-migrated rather than forcing a lossy
  fit.
- [Moving the auth guard from per-hook to `AdminLayoutContent` changes
  *when* the check runs relative to each hook's first fetch — if any
  hook's fetch could fire before `AdminLayoutContent`'s effect runs, an
  unauthenticated request could go out that previously wouldn't have] →
  `AdminLayoutContent` wraps every `/admin/*` route as their common
  parent (confirmed in `App.tsx`), so its effect runs on mount before any
  child route's own hooks run their effects (React parent-before-child
  effect timing) — the check is strictly earlier, not later, than today.
- [`CurrentUserContext` introduces a new dependency for the 12 pages
  that stop fetching their own copy — if `AdminLayoutContent`'s fetch is
  ever slower than a page previously assumed, a page reading from
  context before the fetch resolves gets `null`/`undefined` instead of
  its own resolved value] → None of the 12 target hooks currently read
  the value at all (confirmed dead in the audit), so there is no existing
  read to regress; only `admin-dashboard`'s migration needs a loading-state
  check added if it doesn't already guard against an unresolved user.
- [Collapsing the two `#475569` variants' underlying color to one token
  while keeping weight/casing as separate utilities could still visually
  drift if a future page mixes the token with an unexpected weight] →
  Documented in the token's usage comment in `theme.css`; not otherwise
  preventable by this change and not a regression versus today.

## Migration Plan

No deploy/rollback complexity — a static-site rebuild, no backend
coupling, no data migration, no feature flag needed. Land as independent
commits/PRs, verifying each visually (dev server, both light/dark theme
if applicable) and via any existing tests before moving to the next:

1. `ErrorState` + adopt across the 17 call sites (one commit per page or
   small batches, reviewer's preference — no cross-page dependency).
2. `StatusBadge` + adopt across the 8 table components.
3. `FormPageHeader` + adopt across the 8 form pages.
4. `text-field-label` token + replace the 7 local constants.
5. `moveItem` helper (or dnd-kit's `arrayMove`) + adopt in
   `admin-form-builder`'s three handlers.
6. Visitor form entry unification.
7. Pagination schema dedup across the 13 `*-out-schema.ts` files.
8. `DepartmentsTable` memoization (trivial, standalone).
9. `CurrentUserContext` + auth-guard consolidation into
   `AdminLayoutContent` + drop the 12 dead fetches (grouped together
   since the guard and the context both live in the same
   `AdminLayoutContent` edit).
10. `AdminListPageShell`, adopted one admin list page at a time (8 small
    PRs), last because it's the highest-surface-area item and benefits
    from `ErrorState`/`StatusBadge` already being in place.

Each item is independently revertible.

## Open Questions

None — every item has a concrete decision, and the two places genuine
ambiguity could hide (the two `SecurityGatesTable`/`ReceptionDesksTable`
badge shapes, and the two label-color weight variants) are resolved above
by checking rather than guessing, with an explicit fallback (leave
un-migrated / preserve as a variant) if the check fails.
