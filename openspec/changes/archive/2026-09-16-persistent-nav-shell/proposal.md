## Why

Reported directly from usage: switching between sidebar menu items makes "the whole page jump" instead of only the content changing smoothly. Root cause confirmed by code inspection: every admin/staff page independently builds its own `<AppShell sidebar={...} topBar={...}>` instance, and `RouteTransition` wraps the entire routed tree keyed on `location.pathname`. On every navigation React Router unmounts the whole matched element and mounts a brand-new one — sidebar, top bar, and content together — and the fade/slide transition plays across that whole freshly-mounted tree. The scroll-position fix (`h-screen`/`overflow-hidden`) keeps the sidebar visually anchored in place, but it does not stop the sidebar and top bar from being destroyed and rebuilt on every click, which is what actually produces the "jump."

Separately, a report that the sidebar-scroll fix (from `scrollable-sidebar-menu`/`theme-sidebar-scrollbar`) "isn't applied to all areas, not just admin" was checked against the code: `AdminSidebar` and `DashboardSidebar` are the only two sidebar components in the app, and both already carry the scroll fix identically — there is no third sidebar anywhere (all staff pages use `DashboardSidebar`, all admin pages use `AdminSidebar`). No code gap was found; this proposal includes an explicit re-verification step once the layout restructuring below lands, since that work touches how both sidebars are mounted.

## What Changes

- Restructure routing so the sidebar (and, for the admin area, the top bar) is a **persistent layout** that survives navigation between pages in the same section, instead of being rebuilt by every page. Concretely: introduce `AdminLayout` (renders `AdminSidebar` + `AdminTopBar` once, nests every `/admin/*` route inside it) and `StaffLayout` (renders `DashboardSidebar` once, nests every `/staff/*` route inside it), using React Router's nested "layout route" + `<Outlet>` pattern. A `PublicLayout` (no chrome) hosts the remaining ungrouped routes (`/`, `/visitor/request`, `/visitor/track`, `/admin/login`, `/staff/login`) purely so they keep the same route-transition behavior they already have today.
- Move `RouteTransition` from wrapping the entire route tree to wrapping only each layout's `<Outlet>` — so only the inner content region plays the enter transition; the sidebar and (for admin) top bar never unmount or re-render on navigation within the same section, and no longer participate in the animation at all.
- **Staff area scope (resolved)**: only the sidebar is hoisted to `StaffLayout`. The three staff pages (dashboard, audit trail, visitor registration) each have a different bespoke header component today with different props (search bar, refresh button, sign-out) — unifying them into one shared, hoistable top bar is out of scope for this change. Each staff page's own header stays part of that page's content and transitions along with it; only the sidebar is guaranteed not to jump for staff pages.
- Admin pages stop rendering their own `description`/`breadcrumb` directly into a page-owned `<AdminTopBar>`; instead they report their header content to the now-persistent `AdminLayout` via a small context (`usePageHeader`), since the top bar itself is no longer something each page instantiates.
- Every admin/staff page's `activeItem` (which sidebar entry highlights) is derived from the current route inside the layout, instead of being a hardcoded prop each page passes to its own sidebar instance.
- Re-verify (not re-fix, per the Why above) that the sidebar-scroll and themed-scrollbar behavior from the prior two changes is intact after `AdminSidebar`/`DashboardSidebar` move from being per-page-instantiated to layout-instantiated.

## Capabilities

### Modified Capabilities
- `app-shell`: extend the "Route navigation is accompanied by a transition animation" requirement so the transition is scoped to the main content region only, and the sidebar/top bar (where a shared one exists for that section) persist across navigation without unmounting or re-rendering.

## Impact

- **Affected code**:
  - New: `AdminLayout`, `StaffLayout`, `PublicLayout` (or equivalent) route-layout components; a `PageHeaderContext`/`usePageHeader` hook; small pure functions mapping the current pathname to each sidebar's active item.
  - `src/App.tsx`: route tree restructured from one flat `<Routes>` list into nested routes under the three layouts; the current app-wide `<RouteTransition>` wrapper around all of `<Routes>` is removed in favor of one per layout.
  - All 25 admin page files and all 3 staff page files: remove their own `<AppShell sidebar={...} topBar={...}>` wrapper (now owned by the layout) and return only their inner content; admin pages additionally replace their direct `<AdminTopBar description=.../>`/`breadcrumb` JSX with a call to `usePageHeader(...)`.
- **Not affected**: `AppShell`, `AdminSidebar`, `DashboardSidebar`, `AdminTopBar`, `RouteTransition`, and `BackButton` themselves keep their current implementation and props — this change relocates *where* they're instantiated, not what they render or how they're styled.
- **No backend impact** — frontend-only (VMMS_WEB).
