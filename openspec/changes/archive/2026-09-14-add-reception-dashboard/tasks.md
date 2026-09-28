## 1. Role recognition

- [x] 1.1 In `src/domain/entities/staff-user-schema.ts`, add `isReception: z.boolean()` to `StaffUserSchema`, alongside `isAdmin`.
- [x] 1.2 In `src/infrastructure/staff-auth-repository.ts`'s `getCurrentUser()`, compute `isReception: response.data.branchRoles.some(br => br.roleName.toLowerCase() === 'reception')` next to the existing `isAdmin` line.
- [x] 1.3 In `src/presentation/pages/staff-login/hooks/use-staff-login-page.ts`, change the post-login `navigate(...)` call (currently `navigate(user.isAdmin ? '/admin/dashboard' : '/staff/dashboard')`) to a three-way branch: `navigate(user.isAdmin ? '/admin/dashboard' : user.isReception ? '/reception/dashboard' : '/staff/dashboard')`.

## 2. Promote shared dashboard widgets

- [x] 2.1 Move `src/presentation/pages/admin-dashboard/Components/{KpiRow,RecentCheckinsCard,UpcomingVisitorsCard}.tsx` to `src/presentation/components/dashboard/` unchanged (only relative-import paths inside each file need updating for their new depth).
- [x] 2.2 Update `src/presentation/pages/admin-dashboard/admin-dashboard.tsx`'s imports for these three components to the new shared path. No other change to that file.

## 3. Reception Dashboard page

- [x] 3.1 Create `src/presentation/components/ReceptionSidebar.tsx`: `ReceptionSidebarActiveItem = 'dashboard'`, a single nav entry ("Dashboard", `HomeIcon`, matching `AdminSidebar`'s `dashboard` icon choice) routing to `/reception/dashboard`, following `AdminSidebar`'s brand-mark-plus-nav-list layout and styling.
- [x] 3.2 Create `src/presentation/pages/reception-dashboard/Components/ReceptionTopBar.tsx`: mirrors `AdminTopBar`'s structure (current-user name/role, `NotificationBell`, sign-out button) but with reception-appropriate heading copy (no "Organization Admin" text) and sign-out navigating to `/staff/login`.
- [x] 3.3 Create `src/presentation/pages/reception-dashboard/hooks/use-reception-dashboard.ts`, adapted from `use-admin-dashboard.ts`:
  - Token-presence guard: redirect to `/staff/login` (not `/admin/login`) when absent.
  - After fetching the current user, if `!user.isReception`, redirect to `/staff/dashboard` and skip fetching dashboard data (mirroring `use-admin-audit-trail.ts`'s admin-only branch).
  - Otherwise fetch `getDashboardOverviewUseCase`, `listRecentCheckinsUseCase`, `listHostEmployeesUseCase` exactly as `use-admin-dashboard.ts` does, and expose the same `kpis`/`recentCheckins`/`employeeNameById`/`overview.upcomingVisitors`/`isLoading`/`errorMessage`/`retry` shape.
- [x] 3.4 Create `src/presentation/pages/reception-dashboard/reception-dashboard.tsx` (`ReceptionDashboardPage`): `ReceptionSidebar` + `ReceptionTopBar` + the promoted `KpiRow` / `RecentCheckinsCard` / `UpcomingVisitorsCard`, following `admin-dashboard.tsx`'s layout (error/loading/content branches identical in shape).
- [x] 3.5 Add the `/reception/dashboard` route to `src/App.tsx` rendering `ReceptionDashboardPage`.

## 4. Verification

- [x] 4.1 Run typecheck (`tsc -b`), lint (`oxlint`), and build (`npm run build`); confirm no errors and no stray references to the old `admin-dashboard/Components/` paths for the three moved files. *(All three pass clean; `grep` for `admin-dashboard/Components` across `src/` returns nothing.)*
- [x] 4.2 Confirm at the code level: a user whose current-user response has `isReception: true` (and `isAdmin: false`) reaches `/reception/dashboard` after login and sees the same KPI/recent-check-ins/upcoming-visitors layout as the Admin Dashboard. *(`use-staff-login-page.ts:42` branches correctly; `reception-dashboard.tsx` renders the identical promoted `KpiRow`/`RecentCheckinsCard`/`UpcomingVisitorsCard` in the same layout as `admin-dashboard.tsx`. No live backend/credentials in this sandbox, so verified by tracing the code, not a browser click-through — consistent with how the audit-trail change was verified earlier in this session.)*
- [x] 4.3 Confirm at the code level: a non-Reception authenticated user hitting `/reception/dashboard` directly is redirected to `/staff/dashboard` before any dashboard data is fetched. *(`use-reception-dashboard.ts:44-45`: the `!user.isReception` check and redirect happen before the `Promise.all` overview/checkins/employees fetch further down the same function — the fetch is unreachable in that branch.)*
- [x] 4.4 Backend authorization for a Reception-role token on `/admin/dashboard/overview` and `/admin/dashboard/checkins` is **unverified** — no backend access in this sandbox. Flagged as-is per design.md's Open Question; needs confirming against the real API before relying on this feature end-to-end.
