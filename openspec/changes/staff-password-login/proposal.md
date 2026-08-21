## Why

Staff sign-in currently only supports SSO, which requires an external identity provider integration that isn't ready yet. Replacing it with a direct username/password login against `POST /api/v1/auth/login` lets staff authenticate now without depending on SSO.

## What Changes

- **BREAKING**: Remove the "Sign in with SSO" flow (SSO initiation request, redirect-to-IdP behavior) from the staff login screen.
- Add a username/password form to the staff login screen (`/staff/login`).
- Add a new API integration: `POST /api/v1/auth/login` with `{ email, password }`, returning an auth token on success.
- On successful login, store the returned token (same `sessionStorage` token used by the rest of the staff/admin area) and navigate to `/staff/dashboard`.
- On failed login (invalid credentials or request error), show an inline error message on the login screen and keep the form usable for retry.
- Remove the now-unused SSO initiation endpoint, use case, port method, and UI (`INITIATE_STAFF_SSO`, `InitiateStaffSsoUseCase`, `StaffAuthRepository.initiateSso`, `SsoSignInCard`).

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `staff-login`: Sign-in method changes from a single "Sign in with SSO" action to a username/password form submitted to `/api/v1/auth/login`, including new validation, submission, and error-handling requirements, and removal of the SSO-specific requirements.

## Impact

- **Affected code**:
  - `src/data/api/api-endpoints.ts` — remove `INITIATE_STAFF_SSO`, add `STAFF_LOGIN` (`POST /auth/login`, `hasToken: false`).
  - `src/domain/entities/staff-sso-initiate-schema.ts` — remove; add `src/domain/entities/staff-login-schema.ts` (request + response schemas).
  - `src/data/repositories/staff-auth-repository.ts` — replace `initiateSso()` with `login(username, password)`.
  - `src/infrastructure/staff-auth-repository.ts` — replace SSO call with the login call.
  - `src/data/use-cases/initiate-staff-sso.ts` — remove; add `src/data/use-cases/login-staff.ts`.
  - `src/composition-root.ts` — replace `initiateStaffSsoUseCase` with `loginStaffUseCase` on `AppDependencies`.
  - `src/presentation/pages/staff-login/hooks/use-staff-login-page.ts` — replace `signInWithSso` with username/password form state and a submit handler.
  - `src/presentation/pages/staff-login/Components/SsoSignInCard.tsx` — remove; add a password-login form card.
  - `src/presentation/pages/staff-login/staff-login.tsx` — wire the new form card into the page.
- **Confirmed contract** (via the live dev backend's `/openapi.json`, since none was provided up front): the request body is `{ email, password }` (not `username`), and the response is `{ success, message, data: { accessToken, refreshToken, tokenType } }`. `accessToken` is stored as the bearer token already read from `sessionStorage.getItem("token")` by `ApiClient`; `refreshToken` is accepted by the schema for wire-contract accuracy but no refresh flow is implemented (out of scope).
