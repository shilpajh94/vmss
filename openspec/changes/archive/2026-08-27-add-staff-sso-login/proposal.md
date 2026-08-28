## Why

Staff sign-in has been running on a temporary email/password form since `staff-password-login` (2026-08-24), put in place specifically because the SSO identity-provider integration wasn't ready yet. That integration is now live on the backend (`GET /api/v1/auth/sso/{tenant_slug}/login`, `GET /api/v1/auth/sso/callback`, `POST /api/v1/auth/sso/exchange`), and an approved Figma design ("staff-sso-login", node 30:14) exists for the screen. Staff sign-in can move back to SSO as originally intended, at its own `/staff/login` route, while admin keeps the password screen at `/admin/login`.

## What Changes

- Add a new "Enterprise Sign In" screen at `/staff/login`: a branded card ("STAFF PORTAL" tag, "Enterprise Sign In" title, "Sign in with your organization credentials" description, a single "Sign in with SSO" action, a "Secured by corporate multi-factor authentication" note) plus a "Need help? Contact System Administrator" link — matching the existing admin-login page's hero-image/header/footer chrome, per the Figma design.
- "Sign in with SSO" navigates the browser to `GET /api/v1/auth/sso/{tenant_slug}/login`, which redirects to the tenant's identity provider. The tenant slug is a build-time config value (`VITE_SSO_TENANT_SLUG`), not user-entered — this deployment serves a single tenant, matching the existing single-tenant `VITE_API_BASE_URL` setup.
- After the identity provider redirects back through the backend's `GET /api/v1/auth/sso/callback`, the browser lands back on `/staff/login` carrying an exchange `code` query parameter. The screen detects that parameter, shows a "completing sign-in" loading state, and calls `POST /api/v1/auth/sso/exchange` with the code to obtain the real token pair.
- On a successful exchange, store the access token (`sessionStorage["token"]`, the existing session contract) and navigate to `/staff/dashboard`. `/staff/login` is staff-only, so there is no role branching here (unlike `/admin/login`).
- On failure (denied/expired code, network error, non-success response), show an inline error on the screen and an error toast, matching the existing login-failure pattern.
- **BREAKING**: Staff no longer use the `/admin/login` password form. The unauthenticated/unauthorized session-guard redirects on staff-only pages (`staff-dashboard`, `staff-audit-trail`, `staff-visitor-registration`) change from `/admin/login` to `/staff/login`. Admin-only pages' guard redirects are unaffected and continue to target `/admin/login`.
- The existing `staff-login` folder, components, hooks, and route (`/admin/login`, password form) are left as-is — this change does not rename or touch them; the new screen lives in its own `staff-sso-login` feature folder.

## Capabilities

### New Capabilities
- `staff-sso-login`: the SSO sign-in screen at `/staff/login` — initiating SSO, handling the IdP callback/exchange round trip, and landing on the staff dashboard.

### Modified Capabilities
- `staff-login`: the session-guard requirement ("An expired or unauthorized session redirects to the login screen") splits by audience — staff-only pages now redirect to `/staff/login`, while admin-only pages continue redirecting to `/admin/login`.

## Impact

- **Affected code**:
  - New: `src/presentation/pages/staff-sso-login/` (page, hook, components), `src/domain/entities/sso-*-schema.ts`, `src/data/repositories/sso-auth-repository.ts`, `src/infrastructure/sso-auth-repository.ts`, `src/data/use-cases/*-sso*.ts`, new `API_ENDPOINTS` entries (`START_SSO_LOGIN`, `SSO_EXCHANGE`), `composition-root.ts` wiring, a `VITE_SSO_TENANT_SLUG` env var, new key/shield icon assets.
  - `src/App.tsx` — add the `/staff/login` route.
  - Staff-only guard redirects — `src/presentation/pages/staff-dashboard/hooks/use-staff-dashboard.ts`, `src/presentation/pages/staff-audit-trail/hooks/use-staff-audit-trail.ts`, `src/presentation/pages/staff-visitor-registration/staff-visitor-registration.tsx` — change their `navigate('/admin/login', ...)` calls to `/staff/login`.
- **Not affected**: the `staff-login` folder/components/hooks (`StaffLoginPage`, `StaffGatewayHeader`, `LoginFormCard`, `StaffLoginFooter`, `use-staff-login-page.ts`), the `/admin/login` route, `POST /api/v1/auth/login`, and all admin-only guard redirects (still `/admin/login`).
