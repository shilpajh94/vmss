## Why

Users with the "Reception" role (an existing backend-configured role, alongside "Admin") currently have no dedicated landing page — they land on the generic staff dashboard (the visit-requests kanban board). Reception staff need an at-a-glance overview of today's visitor activity, the same way admins already get one on the Admin Dashboard.

## What Changes

- Add a new "Reception Dashboard" page at `/reception/dashboard`, showing the same at-a-glance overview as the Admin Dashboard — the KPI row (Today's Visitors, Currently On-Site, Pending Approval, Upcoming Visitors), the Recent Check-ins list, and the Upcoming Pre-Registered Visitors list — restricted to users with the Reception role.
- Add a minimal Reception sidebar (brand mark + a single "Dashboard" item) distinct from both the Admin sidebar (which exposes org-management sections Reception should not have) and the staff sidebar (which is the visit-requests workspace, not this overview).
- The system SHALL recognize the Reception role client-side (the current-user response's role list) the same way it already recognizes Admin, and SHALL branch the post-login destination three ways: Admin → `/admin/dashboard`, Reception → `/reception/dashboard`, everyone else → `/staff/dashboard`.
- A non-Reception authenticated user navigating directly to `/reception/dashboard` SHALL be redirected to `/staff/dashboard` instead of seeing the page (mirroring the existing admin-only guard on `/admin/audit-trail`).

## Capabilities

### New Capabilities
- `reception-dashboard`: Reception-only landing page at `/reception/dashboard` reusing the Admin Dashboard's KPI/recent-check-ins/upcoming-visitors overview, with its own minimal sidebar and a reception-only access guard.

### Modified Capabilities
- `staff-login`: The post-login redirect becomes role-based across three destinations (Admin, Reception, everyone else) instead of the currently-documented single staff-dashboard destination.

## Impact

- **Affected code**:
  - `src/domain/entities/staff-user-schema.ts` — add `isReception: boolean` to `StaffUser`, alongside the existing `isAdmin`.
  - `src/infrastructure/staff-auth-repository.ts` — derive `isReception` from `branchRoles` the same way `isAdmin` is derived today.
  - `src/presentation/pages/staff-login/hooks/use-staff-login-page.ts` — post-login navigation becomes a three-way branch.
  - New `src/presentation/components/ReceptionSidebar.tsx` — minimal sidebar with a single "Dashboard" item.
  - New `src/presentation/pages/reception-dashboard/**` (page, hook, a small top-bar component) — reusing `getCurrentStaffUserUseCase`, `getDashboardOverviewUseCase`, `listRecentCheckinsUseCase`, `listHostEmployeesUseCase` from `useAppDependencies()`; no new use cases, ports, adapters, or endpoints.
  - `src/presentation/pages/admin-dashboard/Components/{KpiRow,RecentCheckinsCard,UpcomingVisitorsCard}.tsx` — promoted to a shared location so both `admin-dashboard` and `reception-dashboard` can import them without a cross-feature deep import (per this repo's presentation-layer convention); `admin-dashboard.tsx`'s imports update to match. No behavior change to the Admin Dashboard.
  - `src/App.tsx` — add the `/reception/dashboard` route.
  - `openspec/specs/reception-dashboard/spec.md` — new.
  - `openspec/specs/staff-login/spec.md` — post-login redirect requirement updated.
- **Not affected**: the dashboard-overview/recent-checkins/host-employees API endpoints, their Zod schemas, and the `admin-dashboard` capability's own requirements (Reception reuses the same data and widgets, but Admin's observable behavior is unchanged).
- **Open risk (flagged in design.md, not blocking)**: the dashboard-overview and recent-checkins endpoints are path-prefixed `/admin/...`; whether the backend already authorizes a Reception-role token to call them, or needs a permission change, cannot be confirmed from this repo alone.
