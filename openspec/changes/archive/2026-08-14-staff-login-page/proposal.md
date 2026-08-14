## Why

Staff currently have no dedicated entry point into the system — only visitor-facing flows (portal landing, visit request, tracking) exist. The approved Figma design (node `30:4`, "staff-sso-login") defines an Enterprise Sign In screen for staff, and this change implements it so staff have a branded gateway into the application, wired for a future SSO provider.

## What Changes

- Add a new `/staff/login` route rendering the "Enterprise Sign In" screen: dark "Staff Gateway" header with system-status indicator, background office photo, a centered SSO card ("Staff Portal" tag, title, subtitle, "Sign in with SSO" action, MFA reassurance line), help link, and a footer with copyright and policy links — matching the Figma design pixel-for-pixel.
- Wire the "Sign in with SSO" button to an `initiate-staff-sso` use case that calls a new `INITIATE_STAFF_SSO` API endpoint and navigates to the redirect URL the backend returns. The real identity-provider contract is not finalized yet — this change stubs the endpoint definition and client-side flow so the button is fully wired end-to-end against a placeholder contract.
- Add a new placeholder `/staff/dashboard` route/page as the landing target after a successful SSO redirect, since no staff-facing area exists yet in the app.
- Surface and block on an inline error state on the login screen if SSO initiation fails, without leaving the button in a stuck loading state.

## Capabilities

### New Capabilities
- `staff-login`: Staff SSO sign-in screen, the SSO-initiation use case/API wiring, and the placeholder post-login staff dashboard route.

### Modified Capabilities
(none — no existing capability's requirements change)

## Impact

- **Routing**: `src/App.tsx` gains `/staff/login` and `/staff/dashboard` routes.
- **Presentation**: new `src/presentation/pages/staff-login/` (page + Components + hooks) and a minimal `src/presentation/pages/staff-dashboard/` placeholder page.
- **Data/API layer**: new `INITIATE_STAFF_SSO` entry in `API_ENDPOINTS`, a new domain schema for the SSO-initiate response, a new `StaffAuthRepository` port, an `InitiateStaffSsoUseCase`.
- **Infrastructure**: new `HttpStaffAuthRepository` adapter implementing the port via `ApiClient`.
- **Composition root**: `AppDependencies` gains `initiateStaffSsoUseCase`.
- No changes to existing visitor-facing capabilities or their specs.
