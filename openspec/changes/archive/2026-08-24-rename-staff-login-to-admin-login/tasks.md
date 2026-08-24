## 1. Route

- [x] 1.1 In `src/App.tsx`, change the `<Route path="/staff/login" element={<StaffLoginPage />} />` entry to `path="/admin/login"` (component stays `StaffLoginPage`).

## 2. Screen text

- [x] 2.1 In `src/presentation/pages/staff-login/Components/StaffGatewayHeader.tsx`, change the badge text from "STAFF GATEWAY" to "ADMIN GATEWAY".
- [x] 2.2 In `src/presentation/pages/staff-login/Components/LoginFormCard.tsx`, change the eyebrow label from "Staff Portal" to "Admin Portal".

## 3. Guard redirects to the login route

Update every `navigate('/staff/login', ...)` call site to `navigate('/admin/login', ...)` (preserve any `{ replace: true }` option where present):

- [x] 3.1 `src/presentation/pages/staff-dashboard/hooks/use-staff-dashboard.ts` (both occurrences)
- [x] 3.2 `src/presentation/pages/staff-audit-trail/hooks/use-staff-audit-trail.ts` (both occurrences)
- [x] 3.3 `src/presentation/pages/staff-visitor-registration/staff-visitor-registration.tsx` (both occurrences)
- [x] 3.4 `src/presentation/pages/admin-dashboard/hooks/use-admin-dashboard.ts`
- [x] 3.5 `src/presentation/pages/admin-organisation-configs/hooks/use-admin-organisation-configs.ts`
- [x] 3.6 `src/presentation/pages/admin-branches/hooks/use-admin-branches.ts`
- [x] 3.7 `src/presentation/pages/admin-branches/hooks/use-admin-branch-create.ts`
- [x] 3.8 `src/presentation/pages/admin-departments/hooks/use-admin-departments.ts`
- [x] 3.9 `src/presentation/pages/admin-departments/hooks/use-admin-department-form.ts`
- [x] 3.10 `src/presentation/pages/admin-buildings/hooks/use-admin-buildings.ts`
- [x] 3.11 `src/presentation/pages/admin-buildings/hooks/use-admin-building-form.ts`
- [x] 3.12 `src/presentation/pages/admin-floors/hooks/use-admin-floors.ts`
- [x] 3.13 `src/presentation/pages/admin-floors/hooks/use-admin-floor-form.ts`
- [x] 3.14 `src/presentation/pages/admin-host-employees/hooks/use-admin-host-employees.ts`
- [x] 3.15 `src/presentation/pages/admin-host-employees/hooks/use-admin-host-employee-form.ts`
- [x] 3.16 `src/presentation/pages/admin-reception-desks/hooks/use-admin-reception-desks.ts`
- [x] 3.17 `src/presentation/pages/admin-reception-desks/hooks/use-admin-reception-desk-form.ts`
- [x] 3.18 `src/presentation/pages/admin-security-gates/hooks/use-admin-security-gates.ts`
- [x] 3.19 `src/presentation/pages/admin-security-gates/hooks/use-admin-security-gate-form.ts`
- [x] 3.20 `src/presentation/pages/admin-visitor-categories/hooks/use-admin-visitor-categories.ts`
- [x] 3.21 `src/presentation/pages/admin-visitor-categories/hooks/use-admin-visitor-category-form.ts`

## 4. Verification

- [x] 4.1 Search the codebase for any remaining `/staff/login` string literal and confirm none remain (`grep -rn "/staff/login" src`).
- [x] 4.2 Manually verify: navigating to `/admin/login` renders the sign-in screen with the "ADMIN GATEWAY" header badge and "Admin Portal" eyebrow label; `/staff/login` no longer renders it.
- [x] 4.3 Manually verify: triggering a session-expiry/unauthorized redirect from an admin page and from a staff page both land on `/admin/login`.
- [x] 4.4 Manually verify: signing in still navigates to `/admin/dashboard` or `/staff/dashboard` based on the user's role, unchanged.
