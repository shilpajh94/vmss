## Context

`StaffUser` (`src/domain/entities/staff-user-schema.ts`) is `{ name, role, isAdmin }`; `isAdmin` is derived client-side in `HttpStaffAuthRepository.getCurrentUser()` (`src/infrastructure/staff-auth-repository.ts`) as `branchRoles.some(r => r.roleName.toLowerCase() === 'admin')`. Login (`use-staff-login-page.ts`) branches only on this boolean today: `navigate(user.isAdmin ? '/admin/dashboard' : '/staff/dashboard')`.

There is exactly one precedent for a role-restricted page: `admin-audit-trail`'s hook (`use-admin-audit-trail.ts`) fetches the current user, and if `!user.isAdmin`, redirects away before fetching any page data. No route-level guard/middleware exists anywhere (see that change's own design.md); every guard is inline in a page's hook.

The Admin Dashboard's overview widgets (`KpiRow`, `RecentCheckinsCard`, `UpcomingVisitorsCard`, all under `src/presentation/pages/admin-dashboard/Components/`) are plain presentational components taking only data props (`DashboardKpi[]`, `DashboardRecentCheckin[]`, `DashboardUpcomingVisitor[]`, `employeeNameById`) — no admin-specific logic, just `admin-accent` Tailwind coloring, which is fine to keep since the request is for a page that looks the same as Admin's.

## Goals / Non-Goals

**Goals:**
- Give a Reception-role user a `/reception/dashboard` landing page with the same overview content as the Admin Dashboard.
- Recognize the Reception role client-side, the same way Admin is recognized today, and branch post-login destination three ways.

**Non-Goals:**
- No new generic role-guard/route-middleware mechanism — this follows the same inline-hook-guard pattern as `admin-audit-trail`, not a shared `RequireRole()` abstraction. (Two role-gated pages now exist with near-identical guard logic; if a third one arrives, extracting a shared hook becomes worth it then, not now.)
- No changes to the dashboard-overview/recent-checkins/host-employees API contracts, ports, or adapters — same use cases, same endpoints, called from a second page.
- No Reception-specific data (e.g. a reception-only KPI) — the request is for "the same as admin," not a variant.
- No change to what other admin sections (branches, roles, invitations, etc.) show or who can reach them — this change only adds the one Reception page and the login branch.

## Decisions

**Promote `KpiRow`, `RecentCheckinsCard`, `UpcomingVisitorsCard` from `admin-dashboard/Components/` to a shared location** (`src/presentation/components/dashboard/`), and import them from both `admin-dashboard.tsx` and the new `reception-dashboard.tsx`.
Per this repo's own convention (`clean-architecture.md`: "page-specific UI pieces... should not be imported cross-feature unless promoted to shared UI"), reusing these three components as-is via a deep cross-feature import would violate that rule. Promoting them is a pure move (no behavior change) — `admin-dashboard.tsx`'s only change is its import paths.
- *Alternative considered*: duplicate the three components under `reception-dashboard/Components/`. Rejected — guarantees the two dashboards drift out of sync the next time either widget changes, for no benefit (they're already generic).

**New `ReceptionSidebar` component under `src/presentation/components/`** (shared-component location, matching `DashboardSidebar`/`AdminSidebar`'s existing placement), with a closed active-item union of just `'dashboard'` and a single nav entry.
Mirrors the two existing sidebars' shape (brand mark + nav list) rather than inventing a new layout pattern. Kept as a real component (not inlined into the page) for consistency with the rest of the app, even though it only has one item today — if Reception ever gets a second page, this is where its nav item goes.

**New page-local `ReceptionTopBar` under `reception-dashboard/Components/`, not a reuse of `AdminTopBar`.**
`AdminTopBar` (`src/presentation/components/AdminTopBar.tsx`) hardcodes the heading "Organization Admin" when no breadcrumb is supplied (line 42) — showing that to a Reception user would misrepresent their role. Rather than parameterize `AdminTopBar` for a heading it wasn't designed to vary, a small page-local top bar (current-user name/role, notification bell, sign-out) is simpler and avoids adding a branch to a component named for a different portal. It intentionally mirrors `AdminTopBar`'s visual structure so the page looks the same as Admin's, per the request.

**Reception-only gate implemented inline in `use-reception-dashboard.ts`, copying the `admin-audit-trail` pattern exactly**: token check → redirect `/staff/login` if absent (Reception is a non-admin, staff-tier role, so it follows the staff-only-page convention, not the admin-only one) → fetch current user → if `!user.isReception`, redirect to `/staff/dashboard` before fetching any dashboard data → otherwise fetch overview/recent-checkins/host-employees exactly as `use-admin-dashboard.ts` does.

**`isReception` derived the same way `isAdmin` is**: `branchRoles.some(r => r.roleName.toLowerCase() === 'reception')`, added to `StaffUserSchema` and computed in `HttpStaffAuthRepository.getCurrentUser()` right next to the existing `isAdmin` line. Per your confirmation, "Reception" already exists as a configured `roleName` on the backend, so no backend change is implied — this only teaches the frontend to recognize a role name it already receives.

**Login redirect becomes `user.isAdmin ? '/admin/dashboard' : user.isReception ? '/reception/dashboard' : '/staff/dashboard'`** — Admin takes precedence over Reception if a user somehow holds both roles, consistent with Admin being the most-privileged branch today.

## Risks / Trade-offs

- **Unconfirmed backend authorization** → `getDashboardOverviewUseCase`/`listRecentCheckinsUseCase` call endpoints path-prefixed `/admin/...` (`GET_ADMIN_DASHBOARD_OVERVIEW`, `LIST_DASHBOARD_CHECKINS` in `api-endpoints.ts`). Whether the backend already accepts a Reception-role token on these routes, or will 403 it, cannot be determined from this repo. If it 403s, the frontend already degrades gracefully (`ApiClient.handleAuthFailure` surfaces a plain "you do not have permission" error instead of forcing sign-out — see `admin-audit-trail`'s design.md for the same note), so the page would show its existing error state rather than crash; but the feature would not actually work end-to-end until the backend permits it. → Mitigation: verify against the running API before or during implementation; flagged as an Open Question below rather than blocking this proposal, since it doesn't change the frontend approach either way.
- **Two independent "is this role restricted-page-worthy" checks now exist** (`admin-audit-trail`'s `isAdmin` check, this change's `isReception` check) with no shared abstraction → slightly more places to keep consistent if the pattern changes later. Accepted per Non-Goals (extract only when a third page needs it).

## Open Questions

- Does the backend already authorize a Reception-role token on `/admin/dashboard/overview` and `/admin/dashboard/checkins`? Verifiable against the running API without changing the spec, approach, or task breakdown — the frontend calls the same use cases regardless of the answer.
