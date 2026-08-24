## Why

The shared sign-in gateway currently lives at `/staff/login` and is branded "Staff Gateway" / "Staff Portal", even though it is the single entry point for both staff and admin users (it routes to `/admin/dashboard` or `/staff/dashboard` after sign-in based on the authenticated user's role). The URL and on-screen branding should read as `/admin/login` going forward.

## What Changes

- Change the sign-in route from `/staff/login` to `/admin/login` in `src/App.tsx`. The `/staff/login` path is removed (no redirect kept).
- Update every unauthenticated/unauthorized guard redirect across the staff and admin pages (currently `navigate('/staff/login', ...)`) to target `/admin/login` instead, so session-expiry and access-denied flows land on the new route.
- Update the on-screen text of the login screen to read as the admin gateway: the header badge ("STAFF GATEWAY" → "ADMIN GATEWAY") and the sign-in card's eyebrow label ("Staff Portal" → "Admin Portal").
- Keep the underlying files, components, hooks, and exports named `staff-login` / `StaffLoginPage` / `StaffGatewayHeader` / etc. as-is — this change only touches the route path and the visible copy, not internal naming (per explicit confirmation with the user).
- No changes to authentication behavior, the login form fields, or the post-login destination logic (still role-based: `/admin/dashboard` vs `/staff/dashboard`).

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `staff-login`: The sign-in screen's route changes from `/staff/login` to `/admin/login`, and its header/eyebrow copy changes from "Staff Gateway"/"Staff Portal" to "Admin Gateway"/"Admin Portal".

## Impact

- **Affected code**:
  - `src/App.tsx` — route path `/staff/login` → `/admin/login`.
  - `src/presentation/pages/staff-login/Components/StaffGatewayHeader.tsx` — badge text "STAFF GATEWAY" → "ADMIN GATEWAY".
  - `src/presentation/pages/staff-login/Components/LoginFormCard.tsx` — eyebrow label "Staff Portal" → "Admin Portal".
  - All guard-redirect call sites currently navigating to `/staff/login` on session expiry / 401 (across `admin-*` and `staff-*` page hooks, e.g. `use-admin-dashboard.ts`, `use-staff-dashboard.ts`, `use-staff-audit-trail.ts`, `use-staff-visitor-registration-wizard`-related code, and the `admin-branches`, `admin-buildings`, `admin-departments`, `admin-floors`, `admin-host-employees`, `admin-organisation-configs`, `admin-reception-desks`, `admin-security-gates`, `admin-visitor-categories` hooks) — update the literal string to `/admin/login`.
- **Not affected**: `staff-login` file/folder names, component/hook/export names, the login form fields, the login use case, and the role-based post-login navigation (`/admin/dashboard` vs `/staff/dashboard`).
