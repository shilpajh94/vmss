## Context

The staff login screen (`src/presentation/pages/staff-login/`) currently drives an SSO-only flow: `SsoSignInCard` → `useStaffLoginPage` → `InitiateStaffSsoUseCase` → `StaffAuthRepository.initiateSso()` → `POST /staff-auth/sso/initiate` → `window.location.assign(redirectUrl)`. See proposal.md - Why for the motivation to replace this with direct credentials.

The codebase already establishes the layering this change must follow (`.claude/rules/clean-architecture.md`, `.claude/rules/data-api-layer.md`): `API_ENDPOINTS` entry → Zod schema in `domain/entities` → port in `data/repositories` → adapter in `infrastructure` → use case in `data/use-cases` → wiring in `composition-root.ts` → hook in `presentation/pages/staff-login/hooks` → component.

The bearer token contract is already fixed by `ApiClient` (`src/data/api/api-client.ts`): every `hasToken: true` request reads `sessionStorage.getItem("token")`. Every existing admin/staff page hook reads and clears that same `sessionStorage` key directly (e.g. `use-staff-dashboard.ts`, `use-admin-branches.ts`) rather than going through a use case. This change follows that established pattern for writing the token after login, rather than introducing a new abstraction.

## Goals / Non-Goals

**Goals:**
- Replace the SSO initiation call with a `POST /api/v1/auth/login` call that accepts a username and password and returns an auth token.
- Keep the existing session contract: after login, `sessionStorage["token"]` is set so all existing `hasToken: true` requests keep working unchanged.
- Preserve the existing inline-error + toast-notification behavior on failure, and the redirect-to-dashboard behavior on success, just re-pointed at the new flow.

**Non-Goals:**
- Changing how the token is read/removed elsewhere in the app (the per-page `sessionStorage.getItem('token')` guard pattern is out of scope; this change only adds the write-on-success side).
- Adding "remember me", password reset, or account lockout — not requested.
- Changing `GetCurrentStaffUserUseCase` / `/auth/me` — login only obtains the token; the existing "who am I" call is unaffected.

## Decisions

- **Endpoint shape**: add `STAFF_LOGIN: { endpoint: "/auth/login", method: "POST", hasToken: false }` to `API_ENDPOINTS`. `hasToken: false` because this call is what obtains the token in the first place.
- **Request/response schema**: new `src/domain/entities/staff-login-schema.ts` with `StaffLoginRequestSchema` (`{ email: string, password: string }` — confirmed via the live dev backend's `/openapi.json`; the original assumption of `username` was wrong) and `StaffLoginResponseSchema` for the confirmed envelope `{ success, message, data: { accessToken, refreshToken, tokenType } }` (same wrapper shape as `UserOutResponseSchema`). The adapter unwraps this into a `StaffLoginResultSchema` (`{ token: string }`, built from `data.accessToken`) that the port, use case, hook, and UI consume — mirroring how `getCurrentUser()` already maps `UserOutResponse` into the smaller `StaffUser` shape.
- **Port change over new port**: replace `StaffAuthRepository.initiateSso()` with `login(username, password): Promise<StaffLoginResponse>` on the same port, rather than adding a second `AuthRepository`, since `getCurrentUser()` already lives here and both operations are "staff auth."
- **Token write location**: the login hook (`use-staff-login-page.ts`) calls `sessionStorage.setItem('token', token)` directly after a successful `LoginStaffUseCase.execute(...)`, mirroring how every other staff/admin hook already reads/clears this key directly. Introducing a "session repository" abstraction here would be a bigger change than this proposal's scope.
- **Form validation**: minimal client-side required-field check before calling the use case (matches the spec's "missing field" scenario); no additional password-strength rules, since the backend owns credential validation.
- **Removal, not deprecation**: `INITIATE_STAFF_SSO`, `InitiateStaffSsoUseCase`, `staff-sso-initiate-schema.ts`, and `SsoSignInCard.tsx` are deleted outright rather than left dead, per repo convention (no backwards-compatibility shims for code that's fully replaced).

## Risks / Trade-offs

- [Request/response contract was unknown up front] → Resolved by reading the live dev backend's `/openapi.json` during implementation (`LoginRequest`: `email`/`password`; `Envelope_TokenResponse_`: `success`/`message`/`data.{accessToken,refreshToken,tokenType}`), confirmed against the actual server with a real `401` response; proposal.md and this design were corrected to match.
- [Removing SSO is a breaking change for any staff already relying on it] → Called out as **BREAKING** in proposal.md; acceptable per the request, since SSO integration isn't in place yet.
- [Plaintext password travels in a JSON POST body like other unauthenticated endpoints in this app (e.g. visitor OTP)] → Consistent with existing patterns in this codebase (HTTPS is assumed at the deployment level); no new risk introduced relative to current endpoints.

## Migration Plan

1. Add the new endpoint, schema, port method, adapter method, and use case alongside the existing SSO code (additive, non-breaking).
2. Swap the staff-login hook and UI to the password form and the new use case.
3. Remove the SSO-only endpoint, schema, use case, and component, and drop `initiateSso` from the port/adapter.
4. Update `composition-root.ts` to expose `loginStaffUseCase` instead of `initiateStaffSsoUseCase`.

No data migration or rollback concerns: this is a stateless UI/API-integration swap with no persisted staff-login data.
