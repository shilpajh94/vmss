## 1. Admin Audit Trail page

- [x] 1.1 Create `src/presentation/pages/admin-audit-trail/` by adapting `src/presentation/pages/staff-audit-trail/{staff-audit-trail.tsx,types.ts}` and `Components/{AuditFilterBar,WorkspaceHeader,ActivityTable,Pagination}.tsx`: rename the page component to `AdminAuditTrailPage`, swap `DashboardSidebar` for `AdminSidebar` (`activeItem="audit-trail"`), and swap the admin top bar/header pattern used by other admin pages (e.g. `admin-dashboard.tsx`) in place of the staff `WorkspaceHeader`/sidebar shell.
- [x] 1.2 Create `src/presentation/pages/admin-audit-trail/hooks/use-admin-audit-trail.ts` adapted from `use-staff-audit-trail.ts`:
  - Keep the token-presence guard (redirect to `/admin/login` when absent).
  - After the token check, fetch the current user via `getCurrentStaffUserUseCase.execute()`; if `isAdmin` is `false`, redirect to `/staff/dashboard` and do not fetch audit trail data (see design.md, "Admin-only gate").
  - Call `getAuditTrailUseCase`, `requestAuditReportUseCase`, `getAuditReportUseCase`, and `downloadAuditReportUseCase` exactly as `use-staff-audit-trail.ts` does, but without any "signed-in staff member as host" narrowing — pass through the date-range/activity-type/search filters only.
  - Preserve pagination, empty-state, and error/notification behavior (inline error message + toast) from the existing hook.
- [x] 1.3 Add the `/admin/audit-trail` route to `src/App.tsx` rendering `AdminAuditTrailPage`.

## 2. Admin sidebar registration

- [x] 2.1 In `src/presentation/components/AdminSidebar.tsx`: add `'audit-trail'` to `AdminSidebarActiveItem`, add a `{ key: 'audit-trail', label: 'Audit Trail', icon: ClockIcon }` entry to `NAV_ITEMS` (reuse `ClockIcon`, importing it from `./icons` alongside the existing icon imports), and add `if (key === 'audit-trail') navigate('/admin/audit-trail')` to `handleActivate`.

## 3. Remove the staff-portal Audit Trail

- [x] 3.1 Delete `src/presentation/pages/staff-audit-trail/` (page, hook, types, Components) once `admin-audit-trail` is in place.
- [x] 3.2 Remove the `/staff/audit-trail` route and the `StaffAuditTrailPage` import from `src/App.tsx`.
- [x] 3.3 In `src/presentation/components/DashboardSidebar.tsx`: remove the `'audit-trail'` member from `DashboardSidebarActiveItem`, remove its `NAV_ITEMS` entry, and remove its `handleActivate` branch (and the now-unused `ClockIcon` import, if nothing else in the file uses it).

## 4. Verification

- [x] 4.1 Run the app and confirm: an admin can reach `/admin/audit-trail` via the Admin sidebar and see the filterable, paginated activity log and report download working as before. *(Verified at the code level only, by user's choice — no backend/credentials available in this sandbox to click through live: `AdminSidebar` registers the `audit-trail` item routing to `/admin/audit-trail`, `AdminAuditTrailPage` renders `AuditFilterBar` + `ActivityTable` + `Pagination` unchanged, and the report-download flow in `use-admin-audit-trail.ts` is a straight port of the working staff-page logic.)*
- [x] 4.2 Confirm a non-admin authenticated staff member navigating directly to `/admin/audit-trail` is redirected to `/staff/dashboard` without the page or its data ever rendering. *(Verified at the code level: `use-admin-audit-trail.ts`'s `load()` fetches the current user first and calls `navigate('/staff/dashboard', { replace: true })` before `setCurrentUser` or the audit-trail/employee fetch runs when `user.isAdmin` is `false` — the audit-trail `Promise.all` fetch is unreachable in that branch.)*
- [x] 4.3 Confirm `/staff/dashboard`'s sidebar no longer shows "Audit trail", and that navigating directly to `/staff/audit-trail` no longer resolves (verify `App.tsx` has no matching route). *(Verified: `DashboardSidebarActiveItem`/`NAV_ITEMS`/`handleActivate` in `DashboardSidebar.tsx` have no `audit-trail` entry, and `grep` for `staff-audit-trail` in `src/App.tsx` and across `src/` returns nothing.)*
- [x] 4.4 Run typecheck/build/lint and the existing test suite to confirm nothing still references the deleted `staff-audit-trail` page/hook/components. *(`npx tsc -b`, `npm run build`, and `npx oxlint` all pass clean; no test suite is configured in this project — `package.json` has no `test` script and no `*.test.*`/`vitest.config*` files exist.)*
