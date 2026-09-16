## Context

See `proposal.md` - Why for the root-cause analysis (every page owns its own `AppShell` instance; `RouteTransition` keys the whole `<Routes>` tree on `location.pathname`, so every navigation remounts sidebar + top bar + content together).

Relevant current state:
- `src/App.tsx` is one flat `<Routes>` list — every leaf route (`/admin/branches`, `/staff/dashboard`, `/`, etc.) is a direct child of the single top-level `<Routes>`, wrapped once in `<RouteTransition>`.
- Every admin page renders `<AppShell sidebar={<AdminSidebar activeItem="...">} topBar={<AdminTopBar description="..."/ breadcrumb={...}>}>`. The `activeItem` string and the `description`/`breadcrumb` are hardcoded per page.
- `AdminTopBar` takes `description?`, `breadcrumb?`, `currentUser`. Two usage shapes exist: static `description` text (list pages), and a `breadcrumb` array (create/edit forms; one case — `admin-role-permissions-form.tsx` — has a *dynamic* breadcrumb label that depends on data loaded after mount, `role?.name ?? '...'`).
- Every admin page's own hook independently fetches `currentUser` (via `getCurrentStaffUserUseCase`) alongside its domain data, purely to hand it to its own `<AdminTopBar>`. `admin-dashboard.tsx` is the one exception that also uses `currentUser?.name` directly in its own content (a greeting), not just for the top bar.
- Staff pages have **no shared top bar component** — `staff-dashboard.tsx` has its own `WorkspaceHeader` (rendered as the first item *inside* `<main>`, not as an `AppShell` `topBar`), while `staff-audit-trail.tsx` and `staff-visitor-registration.tsx` each hoisted their own different header component (`WorkspaceHeader`, `RegistrationWorkspaceHeader`) into the `topBar` slot during the `fix-app-shell-ux-polish` migration. Per the resolved scope, this change does not unify them — only `DashboardSidebar` is hoisted for staff.
- React Router is v8 (`react-router` package, not `react-router-dom`), which supports nested layout routes and `<Outlet>` the same way v6 does.

## Goals / Non-Goals

**Goals:**
- Sidebar (admin + staff) and admin top bar are mounted once per section and never unmount/re-render when navigating between pages within that section.
- The route transition animation still plays, but only around the swapped content, not the sidebar/top bar.
- No behavior change to what each page shows or how `AppShell`/`AdminSidebar`/`DashboardSidebar`/`AdminTopBar` render — only *where* they're instantiated changes.
- Every route keeps its existing transition-on-navigate behavior (including the public/unauthenticated routes, which have no sidebar at all).

**Non-Goals:**
- Not unifying the three different staff header components into one shared, hoistable top bar (resolved scope decision — tracked as a possible future change, not this one).
- Not centralizing or de-duplicating each page's own `currentUser` fetch inside its domain-data hook — those keep fetching it themselves exactly as today (see Decisions for why removing it isn't free, and why leaving it is an acceptable, non-regressive trade-off).
- Not changing route paths, permissions/auth guards, or what component renders for any given URL — this is a structural regrouping of the same routes under layout parents, not a URL or access-control change.

## Decisions

**1. Three layout-route parents in `App.tsx`: `PublicLayout`, `AdminLayout`, `StaffLayout`.**
Every existing leaf route becomes a child of exactly one of these three, using React Router's nested-route `element`/`<Outlet>` pattern:
```tsx
<Routes>
  <Route element={<PublicLayout />}>
    <Route path="/" element={<VisitorPortalLandingPage />} />
    <Route path="/visitor/request" element={<VisitorRequestPage />} />
    <Route path="/visitor/track" element={<VisitorTrackPage />} />
    <Route path="/admin/login" element={<StaffLoginPage />} />
    <Route path="/staff/login" element={<StaffSsoLoginPage />} />
  </Route>
  <Route element={<AdminLayout />}>
    <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
    {/* ...every other /admin/* route... */}
  </Route>
  <Route element={<StaffLayout />}>
    <Route path="/staff/dashboard" element={<StaffDashboardPage />} />
    <Route path="/staff/visitors/new" element={<StaffVisitorRegistrationPage />} />
    <Route path="/staff/audit-trail" element={<StaffAuditTrailPage />} />
  </Route>
</Routes>
```
`PublicLayout` exists purely so the ungrouped routes keep exactly the transition behavior they have today (`<RouteTransition><Outlet /></RouteTransition>`, no chrome) — without it, removing the current app-wide `RouteTransition` wrapper would silently regress those 5 routes' navigation animation.
*Alternative considered*: keep the public routes directly under the root `<Routes>`, outside any layout, and only introduce `AdminLayout`/`StaffLayout`. Rejected — it would need `RouteTransition` in two different places (once wrapping the leftover public routes, once per authenticated layout) with different code shapes for what should be the same mechanism; one `PublicLayout` keeps the pattern uniform.

**2. `RouteTransition` moves from wrapping all of `<Routes>` to wrapping each layout's `<Outlet>`.**
```tsx
// AdminLayout
<AppShell sidebar={<AdminSidebar activeItem={activeItem} />} topBar={<AdminTopBar {...header} currentUser={currentUser} />}>
  <RouteTransition><Outlet /></RouteTransition>
</AppShell>
```
This is *why* the sidebar/top bar stop remounting: `RouteTransition`'s `key={location.pathname}` now only forces a remount of the `<Outlet>`'s subtree (the matched child page), because `AdminLayout` itself is the thing React Router keeps mounted across navigations within `/admin/*` — the key change no longer reaches up to the layout's own JSX, only to what's nested inside it.

**3. `usePageHeader` context replaces pages directly instantiating `<AdminTopBar description=.../>`.**
A small context provider (`PageHeaderProvider`) wraps `AdminLayout`'s subtree; `AdminLayout` reads the current header value and passes it to the one `<AdminTopBar>` it owns, while each admin page calls a hook to publish its own header:
```tsx
// inside a page component, replacing the old <AdminTopBar description="..."/> JSX:
usePageHeader({ description: 'Manage core geographical branches, regional offices, and regional heads' })

// a form page with a dynamic breadcrumb (e.g. admin-role-permissions-form.tsx):
usePageHeader({ breadcrumb: [{ label: 'Roles & Permissions' }, { label: role?.name ?? '...', isActive: true }] })
```
`usePageHeader` is a thin wrapper around `useEffect(() => setHeader(header), [header.description, /* breadcrumb elements */])` — it re-publishes whenever the page's own header inputs change (e.g. once `role.name` loads), so the dynamic-breadcrumb case still updates the visible top bar once data arrives, exactly as it does today.
*Trade-off accepted*: because the new page's header effect runs after its first render/commit, the outgoing page's header can remain visible for one paint before the incoming page's `usePageHeader` call updates it. This is the same class of transient every "portal a value up to a persistent parent" pattern has (e.g. document-title-in-layout patterns); not visually significant given the content transition is already in flight at that moment.
*Alternative considered*: pass header content down as route `handle` metadata (React Router's `useMatches()`/`handle` feature) instead of a custom context. Rejected — `handle` values must be static per route definition, which doesn't support the dynamic-breadcrumb case (`role?.name` loaded async) without still layering a context or ref-based update on top; a plain context is simpler and already covers both the static and dynamic cases uniformly.

**4. `activeItem` is derived from the URL inside each layout, not passed in per page.**
```ts
const ADMIN_ROUTE_ACTIVE_ITEMS: ReadonlyArray<readonly [prefix: string, item: AdminSidebarActiveItem]> = [
  ['/admin/dashboard', 'dashboard'],
  ['/admin/branches', 'branches'],
  // ...one entry per top-level admin route prefix...
]
function resolveAdminActiveItem(pathname: string): AdminSidebarActiveItem {
  return ADMIN_ROUTE_ACTIVE_ITEMS.find(([prefix]) => pathname.startsWith(prefix))?.[1] ?? 'dashboard'
}
```
`AdminLayout` calls `resolveAdminActiveItem(useLocation().pathname)` once and passes the result to its single `<AdminSidebar>` instance. This removes the need for every page to know and hardcode its own sidebar key, and is impossible to get out of sync with the route table the way a hand-copied prop on 25 separate files could.
*Alternative considered*: keep `activeItem` as a per-page prop, threaded down through route `handle` metadata. Rejected — it's strictly more moving parts than a small lookup table for information that's already 1:1 with the URL.

**5. `AdminLayout` fetches its own `currentUser` for the top bar; pages keep their own existing fetch untouched.**
Pages that used `currentUser` only to hand to their own `<AdminTopBar>` no longer need it for that purpose, but their hooks still fetch it (unchanged) since some pages (`admin-dashboard.tsx`) use it directly in their own content, and auditing all 25 hooks to determine which fetches are now provably dead is more risk than this change needs to take on. `AdminLayout` performs its own, independent `getCurrentStaffUserUseCase.execute()` once when the admin section mounts (not on every page navigation, since the layout itself doesn't remount between admin pages) and exposes it to its own `<AdminTopBar>`.
*Trade-off accepted*: this adds exactly one extra "get current user" call per admin-section entry (not per page-view) on top of the fetch every page's own hook was already doing. Given that call is cheap, cached for the section's lifetime, and does not scale with how many pages the user visits, this is judged acceptable rather than worth the larger, riskier refactor of also removing it from all 25 page hooks. Flagged as a reasonable future cleanup, not required here.

**6. `mainClassName` per-page customization is dropped; centered forms self-center instead.**
`AppShell.mainClassName` let each page customize its own `<main>` (e.g. 8 admin form pages pass `"flex flex-1 flex-col items-center overflow-y-auto overflow-x-hidden p-8"` to center their content, versus the default left-stretched list-page layout). Once `<main>` is owned once by `AdminLayout`/`StaffLayout` and shared across every page in that section, per-page `mainClassName` is no longer possible — this was missed in the original plan and surfaced while migrating `staff-visitor-registration.tsx`.
Fix: `AdminLayout`/`StaffLayout` always use `AppShell`'s default `mainClassName`. The 8 admin form pages that relied on `items-center` to center their `<div className="flex w-full max-w-[1160px] flex-col gap-6">` content block instead add `mx-auto` directly to that div — self-centering within a non-centering `<main>`, with the identical visual result (verified: all 8 use the exact same `max-w-[1160px]` wrapper pattern, so the fix is uniform, not bespoke per page).
For pages that only used `mainClassName` for slightly different *padding* (not centering) — `staff-audit-trail.tsx` (`px-8 py-6` vs. default `p-8`), `staff-visitor-registration.tsx` (`px-10 py-8` vs. default `p-8`) — the padding difference is dropped in favor of the shared default. This is a minor, accepted visual regression (a few pixels of padding), not a layout-breaking one, and consistent with the already-resolved "sidebar-only hoisting, staff pages lose some per-page customization" scope decision.

## Risks / Trade-offs

- **[Risk] Removing `<AppShell>` from all 28 page files is a large, repetitive, error-prone edit (same shape of risk as the original `fix-app-shell-ux-polish` migration)** → Mitigation: same approach as that change — do it mechanically, file by file, verify with a full `tsc -b --noEmit` + `oxlint` + production build after each batch, and spot-check a representative sample (a list page, a create form, a dynamic-breadcrumb edit form, and all 3 staff pages) by reading the final file.
- **[Risk] Sibling modals/dialogs that used to render outside `<AppShell>` (as fragment siblings) now render inside `<main>` via the `<Outlet>`, since the page itself no longer wraps anything in `AppShell`** → Mitigation: not a new risk — this was already true after `fix-app-shell-ux-polish` moved every page's content inside `AppShell`'s `<main>`, and was already verified safe then: every modal in this codebase (`Modal.tsx` and its consumers) uses `fixed inset-0`, which escapes any ancestor's `overflow` clipping regardless of DOM nesting depth (barring a `transform`/`filter` ancestor, which `AppShell`/layouts don't introduce).
- **[Risk] `usePageHeader`'s one-paint stale-header transient (Decision 3)** → Mitigation: accepted as a minor, non-blocking cosmetic trade-off; revisit only if it turns out to be visually noticeable once checked in a real browser.
- **[Risk] A page forgets to call `usePageHeader` after this migration, leaving the top bar showing the previous page's stale description** → Mitigation: tasks.md's per-page checklist makes this an explicit, individually-checked step for every admin page (not a bulk find-replace assumed to be correct); the final manual/verification pass in tasks.md specifically checks the top bar text updates correctly on every admin route.
- **[Risk] The 8 admin form pages that relied on `mainClassName="...items-center..."` to center their content lose that centering if the `mx-auto` fix (Decision 6) is forgotten for even one of them** → Mitigation: tasks.md names all 8 files explicitly for this fix rather than leaving it to a bulk find-replace; the final verification pass includes checking a centered form page renders centered, not stretched full-width.

## Migration Plan

- Build the new pieces first (layouts, context, active-item resolvers) without touching any existing page, so nothing is broken mid-migration.
- Wire `App.tsx`'s route tree to the three layouts.
- Migrate pages one file at a time (admin list pages, admin forms, then the 3 staff pages), each individually verified compilable before moving to the next — same pattern `fix-app-shell-ux-polish` used successfully for a similarly-sized batch.
- Rollback is a plain revert (frontend-only, no schema/data migration, no API contract change).
