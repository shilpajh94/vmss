## 1. API registration

- [x] 1.1 Add `STAFF_LOGIN` (`POST /auth/login`, `hasToken: false`) to `src/data/api/api-endpoints.ts`; remove `INITIATE_STAFF_SSO`.

## 2. Domain schema

- [x] 2.1 Create `src/domain/entities/staff-login-schema.ts` with `StaffLoginRequestSchema` (`email`, `password` — confirmed via the live backend's `/openapi.json`, not `username` as originally assumed) and `StaffLoginResponseSchema` (confirmed envelope `{ success, message, data: { accessToken, refreshToken, tokenType } }`), plus a `StaffLoginResultSchema` (`{ token }`) that the port/use case return, and their `z.infer` types.
- [x] 2.2 Delete `src/domain/entities/staff-sso-initiate-schema.ts`.

## 3. Port and adapter

- [x] 3.1 In `src/data/repositories/staff-auth-repository.ts`, replace `initiateSso(): Promise<StaffSsoInitiateResponse>` with `login(email: string, password: string): Promise<StaffLoginResult>`.
- [x] 3.2 In `src/infrastructure/staff-auth-repository.ts`, replace the `initiateSso` implementation with a `login` implementation that calls `apiClient.makeRequest` with `API_ENDPOINTS.STAFF_LOGIN`, the `{ email, password }` body, parses the response with `StaffLoginResponseSchema`, and returns `{ token: response.data.accessToken }`.

## 4. Use case

- [x] 4.1 Delete `src/data/use-cases/initiate-staff-sso.ts`.
- [x] 4.2 Create `src/data/use-cases/login-staff.ts` with a `LoginStaffUseCase` class, constructor-injected `StaffAuthRepository`, and an `execute(email, password)` method delegating to `staffAuthRepository.login(...)`.

## 5. Composition root

- [x] 5.1 In `src/composition-root.ts`, remove `initiateStaffSsoUseCase` (import, resolver, `AppDependencies` field, getter) and add `loginStaffUseCase` (import `LoginStaffUseCase`, lazy resolver via `resolveStaffAuthRepository()`, `AppDependencies` field, getter).

## 6. Staff login page

- [x] 6.1 Delete `src/presentation/pages/staff-login/Components/SsoSignInCard.tsx`.
- [x] 6.2 Add a login form card component (e.g. `Components/LoginFormCard.tsx`) with email and password inputs, a "Sign In" submit button, a loading state, and an inline error message, following this project's form-handling conventions.
- [x] 6.3 Rewrite `src/presentation/pages/staff-login/hooks/use-staff-login-page.ts`: replace `signInWithSso` with email/password state, a required-fields check, and a submit handler that calls `loginStaffUseCase.execute(...)` via `useAppDependencies()`, then on success sets `sessionStorage.setItem('token', token)` and navigates to `/staff/dashboard` (via `useNavigate`), and on failure sets the inline error message and shows an error toast (matching the existing `useToast` pattern).
- [x] 6.4 Update `src/presentation/pages/staff-login/staff-login.tsx` to render the new login form card instead of `SsoSignInCard`, wiring up the hook's new state and submit handler.

## 7. Verification

- [x] 7.1 Manually verify: submitting valid credentials stores the token in `sessionStorage` and navigates to `/staff/dashboard`. (Verified against the confirmed API envelope via a mocked `200` response — no valid staff credentials were available for a live end-to-end run; see note below.)
- [x] 7.2 Manually verify: submitting with a missing field shows a validation message and does not call the API.
- [x] 7.3 Manually verify: a failed login (wrong credentials or network error) shows the inline error, triggers the error toast, and leaves the form usable for retry. (Verified against the live dev backend, which returned a real `401`.)
- [x] 7.4 Confirm no remaining references to `INITIATE_STAFF_SSO`, `InitiateStaffSsoUseCase`, `initiateSso`, `StaffSsoInitiateResponse`, `SsoSignInCard`, or `initiateStaffSsoUseCase` anywhere in `src/`.
