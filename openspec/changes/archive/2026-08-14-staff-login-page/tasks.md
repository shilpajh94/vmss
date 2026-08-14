## 1. Domain & API contract

- [x] 1.1 Add `StaffSsoInitiateResponseSchema` (`redirectUrl: z.string()`) and its `StaffSsoInitiateResponse` type in `src/domain/entities/staff-sso-initiate-schema.ts`
- [x] 1.2 Add `INITIATE_STAFF_SSO` entry to `API_ENDPOINTS` in `src/data/api/api-endpoints.ts` (`POST /staff-auth/sso/initiate`, `hasToken: false`)

## 2. Data layer (port & use case)

- [x] 2.1 Add `StaffAuthRepository` port interface (`initiateSso(): Promise<StaffSsoInitiateResponse>`) in `src/data/repositories/staff-auth-repository.ts`
- [x] 2.2 Add `InitiateStaffSsoUseCase` in `src/data/use-cases/initiate-staff-sso.ts`, constructor-injected with `StaffAuthRepository`, `execute()` delegating to the port

## 3. Infrastructure adapter

- [x] 3.1 Add `HttpStaffAuthRepository` in `src/infrastructure/staff-auth-repository.ts` implementing `StaffAuthRepository` via `ApiClient.makeRequest` with `API_ENDPOINTS.INITIATE_STAFF_SSO` and `StaffSsoInitiateResponseSchema`

## 4. Composition root wiring

- [x] 4.1 Add lazy `resolveStaffAuthRepository` and `resolveInitiateStaffSsoUseCase` resolvers in `src/composition-root.ts`
- [x] 4.2 Expose `initiateStaffSsoUseCase` on `AppDependencies`

## 5. Staff login page (presentation)

- [x] 5.1 Scaffold `src/presentation/pages/staff-login/staff-login.tsx` route component
- [x] 5.2 Build `StaffGatewayHeader` (dark header: "VisitorPass" mark, "STAFF GATEWAY" badge, "All Systems Operational" status dot) under `src/presentation/pages/staff-login/Components/`
- [x] 5.3 Build the SSO card (Staff Portal tag, "Enterprise Sign In" title, subtitle, "Sign in with SSO" button with key icon, MFA reassurance line with shield icon) under `src/presentation/pages/staff-login/Components/`
- [x] 5.4 Build the background image layer with dark overlay, help-link row ("Need help? Contact System Administrator"), and footer (copyright + "Security Policy" / "Terms of Service" links), matching Figma spacing, colors, and typography tokens from `src/styles/theme.css`
- [x] 5.5 Add `use-staff-login-page.ts` hook under `src/presentation/pages/staff-login/hooks/` that calls `initiateStaffSsoUseCase.execute()` via `useAppDependencies()`, manages loading/error state, and on success calls `window.location.assign(redirectUrl)`
- [x] 5.6 Wire the SSO button to the hook's submit handler; show the inline error message on failure and re-enable the button

## 6. Staff dashboard placeholder

- [x] 6.1 Add minimal placeholder page `src/presentation/pages/staff-dashboard/staff-dashboard.tsx`

## 7. Routing

- [x] 7.1 Add `/staff/login` and `/staff/dashboard` routes to `src/App.tsx`

## 8. Verification

- [x] 8.1 Run the app and visually compare `/staff/login` against the Figma design (node `30:4`) for layout, spacing, colors, and typography
- [x] 8.2 Verify the SSO button shows a loading state, then either redirects (on a mocked success response) or shows an inline error and re-enables itself (on a mocked failure response)
- [x] 8.3 Verify `/staff/dashboard` renders directly when navigated to
- [x] 8.4 Run `npm run lint` and `tsc -b` (via `npm run build`) with no new errors
