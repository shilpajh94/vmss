## 1. Foundation pieces (no existing page touched yet)

- [x] 1.1 Create `PageHeaderContext`/`usePageHeader` (e.g. `src/presentation/context/page-header-context.tsx`) per design.md decision 3: a provider holding `{ description?: string; breadcrumb?: BreadcrumbItem[] }`, and a `usePageHeader(header)` hook that publishes it via `useEffect`.
- [x] 1.2 Create `resolveAdminActiveItem(pathname)` and `resolveStaffActiveItem(pathname)` pure functions (e.g. alongside `AdminSidebar.tsx`/`DashboardSidebar.tsx` or in a small shared file) per design.md decision 4, covering every existing admin/staff route prefix.
- [x] 1.3 Create `AdminLayout` (e.g. `src/presentation/components/AdminLayout.tsx`): wraps `PageHeaderProvider`, fetches `currentUser` once via `getCurrentStaffUserUseCase`, renders `<AppShell sidebar={<AdminSidebar activeItem={resolveAdminActiveItem(...)} />} topBar={<AdminTopBar {...header} currentUser={currentUser} />}><RouteTransition><Outlet /></RouteTransition></AppShell>` per design.md decisions 1–5.
- [x] 1.4 Create `StaffLayout` (e.g. `src/presentation/components/StaffLayout.tsx`): renders `<AppShell sidebar={<DashboardSidebar activeItem={resolveStaffActiveItem(...)} />}><RouteTransition><Outlet /></RouteTransition></AppShell>` — no top bar, per the resolved staff-header scope.
- [x] 1.5 Create `PublicLayout` (e.g. `src/presentation/components/PublicLayout.tsx`): just `<RouteTransition><Outlet /></RouteTransition>`, no chrome.

## 2. Restructure routing

- [x] 2.1 In `src/App.tsx`, remove the app-wide `<RouteTransition>` wrapper around `<Routes>`, and regroup every existing `<Route>` under three parent `<Route element={...}>` blocks (`PublicLayout`, `AdminLayout`, `StaffLayout`) per design.md decision 1 — same paths and page components as today, just nested.
- [x] 2.2 Confirm the route tree compiles and every existing path still resolves to the same page component. Verified: `git show HEAD:src/App.tsx` vs. current, extracting every `path="..."` and diffing sorted lists — identical set, none dropped or duplicated, each now nested under the correct layout by section (`/admin/*` under `AdminLayout`, `/staff/*` under `StaffLayout`, the rest under `PublicLayout`).

## 3. Migrate admin pages (remove page-owned AppShell; publish header via context)

- [x] 3.1 Branches: `admin-branches.tsx` (list — drop `AppShell`/`AdminSidebar`/`AdminTopBar`, add `usePageHeader({ description: ... })`), `admin-branch-create.tsx` (form — same, keep its existing `BackButton` unchanged since that's independent of this refactor; it already uses `usePageHeader`-equivalent for its `breadcrumb`).
- [x] 3.2 Buildings: `admin-buildings.tsx`, `admin-building-form.tsx` — this form page has `mainClassName="...items-center..."`; per design.md decision 6, dropped it and added `mx-auto` to its `<div className="flex w-full max-w-[1160px] flex-col gap-6">` wrapper instead, so it stays centered. (Done by background agent.)
- [x] 3.3 Departments: `admin-departments.tsx`, `admin-department-form.tsx` — same `mx-auto` fix as 3.2. (Background agent left `admin-department-form.tsx` with a syntax error — a leftover extra `</div>` from the old two-level wrapper, from being cut off mid-edit by a session rate limit — fixed manually and re-verified with `tsc`.)
- [x] 3.4 Floors: `admin-floors.tsx`, `admin-floor-form.tsx` — same `mx-auto` fix as 3.2. (Same rate-limit-induced syntax error in `admin-floor-form.tsx`, fixed manually.)
- [x] 3.5 Host employees: `admin-host-employees.tsx`, `admin-host-employee-form.tsx` — same `mx-auto` fix as 3.2. (Background agent was cut off mid-file by the same rate limit before finishing either file; both were broken/untouched and migrated manually.)
- [x] 3.6 Reception desks: `admin-reception-desks.tsx`, `admin-reception-desk-form.tsx` — same `mx-auto` fix as 3.2. (Done by background agent.)
- [x] 3.7 Security gates: `admin-security-gates.tsx`, `admin-security-gate-form.tsx` — same `mx-auto` fix as 3.2. (Done by background agent.)
- [x] 3.8 Visitor categories: `admin-visitor-categories.tsx`, `admin-visitor-category-form.tsx` — same `mx-auto` fix as 3.2. (Background agent was cut off before starting this feature; migrated manually.)
- [x] 3.9 Workflows: `admin-workflows.tsx`, `admin-workflow-form.tsx` — same `mx-auto` fix as 3.2. (Same as 3.8, migrated manually.)
- [x] 3.10 Roles: `admin-roles.tsx`, `admin-role-create-form.tsx`, `admin-role-permissions-form.tsx` — this last one has the dynamic `role?.name` breadcrumb (design.md decision 3's motivating case); its `usePageHeader` breadcrumb derives from `role?.name` directly, so it re-publishes automatically once `role` loads (verified: `usePageHeader`'s effect deps include a `breadcrumbKey` string derived from label/isActive values, not object identity). Kept its existing `BackButton` unchanged.
- [x] 3.11 Invitations: `admin-invitations.tsx`.
- [x] 3.12 Dashboard: `admin-dashboard.tsx` — kept its own `currentUser` fetch (used for the greeting), only removed the `AppShell`/`AdminTopBar` wrapper.
- [x] 3.13 Organisation configs: `admin-organisation-configs.tsx`.
- [x] 3.14 Form builder: `admin-form-builder.tsx`, `admin-form-builder-step-editor.tsx` — kept this step editor's existing `goBack` back button and its dynamic step-name breadcrumb (now published via `usePageHeader`) unchanged.
- [x] 3.15 Sweep: `grep -rl AppShell src/presentation/pages/admin-*` returns empty (every admin page's own `AppShell` usage has moved to `AdminLayout`). Verified.

## 4. Migrate staff pages (remove page-owned AppShell; sidebar only, no header hoisting)

- [x] 4.1 `staff-dashboard.tsx`: drop `AppShell`/`DashboardSidebar`, keep its own `WorkspaceHeader` exactly where it is in its returned content.
- [x] 4.2 `staff-audit-trail.tsx`: drop `AppShell`/`DashboardSidebar`; its `WorkspaceHeader` (currently passed as `topBar`) becomes a normal first child of the page's returned content instead. Note: this page's custom `mainClassName` padding (`px-8 py-6`) is lost in favor of `StaffLayout`'s uniform default (`p-8`) — a minor, accepted padding difference (not a centering/alignment change), consistent with the resolved "sidebar-only hoisting for staff" scope.
- [x] 4.3 `staff-visitor-registration.tsx`: same treatment for its `RegistrationWorkspaceHeader`. Same accepted padding note (`px-10 py-8` → default `p-8`); this page had no `items-center` centering to preserve, only padding.
- [x] 4.4 Sweep: `grep -rl AppShell src/presentation/pages/staff-*` returns empty. Verified.

## 5. Re-verify sidebar-scroll behavior after the move

- [x] 5.1 Confirm `AdminSidebar`/`DashboardSidebar` still carry `sidebar-nav-scroll` and the `flex-1 min-h-0 overflow-y-auto` nav classes unchanged. Verified: both `<nav>` elements still read `className="sidebar-nav-scroll flex min-h-0 flex-1 flex-col gap-{1.5,2} overflow-y-auto"` — this refactor only added the `resolveAdminActiveItem`/`resolveStaffActiveItem` exports alongside them, no scroll-related classes were touched.
- [x] 5.2 Confirm there is still exactly one sidebar component per section and no third sidebar was introduced or missed: `grep -rln "<aside" src/presentation` returns exactly `AdminSidebar.tsx` and `DashboardSidebar.tsx` — unchanged from before this change.

## 6. Final verification

- [x] 6.1 Run `npx tsc -b --noEmit`, `npm run lint`, `npm run build` and fix any issues. All three clean project-wide (build shows only the pre-existing, unrelated large-chunk warning). Also verified: no page under `src/presentation/pages/` imports `AdminSidebar`/`AdminTopBar`/`AppShell`/`DashboardSidebar` directly anymore — only `AdminLayout`/`StaffLayout` do.
- [x] 6.2 Manually verify the new app-shell spec scenarios. Verified structurally by code review: `AdminLayout`/`StaffLayout` are each mounted once per section via React Router's nested-route `<Outlet>` pattern (confirmed in `App.tsx`), so React never remounts them on navigation between sibling routes — only `<RouteTransition><Outlet /></RouteTransition>`'s subtree remounts, per `location.pathname` changing. Every migrated admin page's `usePageHeader` call was checked against its original `<AdminTopBar description=.../breadcrumb=...>` text (including the dynamic `role?.name` case) to confirm no text was dropped or altered. **Caveat**: consistent with every prior sidebar/app-shell change in this session, no headless-browser tooling is available in this environment to visually watch a live navigation and confirm the sidebar/top bar don't flash — recommend a real manual click-through (especially rapidly switching between two admin sidebar items) before merging.
