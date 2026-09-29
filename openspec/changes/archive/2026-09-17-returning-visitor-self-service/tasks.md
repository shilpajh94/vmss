## 1. Confirm response shapes

- [x] 1.1 Read `docs/features/visitor_return_visit.md` and `src/vmss_api/visitor_return_visit/schemas.py`/`router.py` in the `VMMS_API` repo (checked out locally at `/home/shilpa/VMMS_API`) and confirmed exact field names/types/nullability. Confirmed: `history[]` = `{trackingId, status, visitDate: string|null, purpose: string|null}`; `prefill` = `{fullName, email: string|null, phone: string|null, preferredContactMethod: string, idProofType: string|null, photoUrl: string|null} | null`; `pagination` = `{page, pageSize, total, totalPages}`; all camelCase.

## 2. Domain schemas

- [x] 2.1 Add `src/domain/entities/visitor-portal-schema.ts`: `VisitHistoryEntrySchema` (trackingId, status, visitDate nullable, purpose nullable), `VisitorPrefillSchema` (fullName, email nullable, phone nullable, preferredContactMethod, idProofType nullable, photoUrl nullable — the whole object also nullable), `PaginationSchema` (page, pageSize, total, totalPages), and `VisitorPortalMeResponseSchema` wrapping them in the `success`/`message`/`data` envelope; export the corresponding `z.infer` types.

## 3. Data & infrastructure layer

- [x] 3.1 Add `API_ENDPOINTS.GET_VISITOR_PORTAL_ME` (`/visitor-portal/me`, `GET`, `hasToken: false`) in `src/data/api/api-endpoints.ts`.
- [x] 3.2 Add port `VisitorPortalRepository` in `src/data/repositories/visitor-portal-repository.ts` with `getMe(proofToken: string, page?: { page: number; pageSize: number }): Promise<VisitorPortalMe>`.
- [x] 3.3 Implement `src/infrastructure/visitor-portal-repository.ts`, calling `apiClient.makeRequest` with `headers: { Authorization: \`Bearer ${proofToken}\` }` and `parserSchema: VisitorPortalMeResponseSchema`.
- [x] 3.4 Add `GetVisitorPortalMeUseCase` in `src/data/use-cases/get-visitor-portal-me.ts`, constructor-injected with `VisitorPortalRepository`.
- [x] 3.5 Wire `ApiClient` → `VisitorPortalRepository` adapter → `GetVisitorPortalMeUseCase` in `composition-root.ts`, and expose the use case on `AppDependencies`.

## 4. ApiClient 401 scoping fix and status-aware errors

- [x] 4.1 Add `export class ApiError extends Error { status: number }` (e.g. in `src/data/api/api-error.ts`) so callers can distinguish HTTP status codes without breaking existing `err instanceof Error` handling.
- [x] 4.2 In `src/data/api/api-client.ts`, change `handleAuthFailure` to only clear `sessionStorage['token']` and dispatch `SESSION_EXPIRED_EVENT` on 401 when the called endpoint has `hasToken: true`; for `hasToken: false` endpoints, fall through to `ensureOk`'s error path.
- [x] 4.3 Change `ensureOk` (and the 403 branch) to throw `ApiError` (carrying `response.status`) instead of a plain `Error`.
- [x] 4.4 SKIPPED — this repo has no test framework configured at all (no vitest/jest, no test script, no existing test files); the user confirmed not to introduce one for a single test file. Verified instead via manual exercise in task group 8.

## 5. OTP hook: capture and pass the proof token

- [x] 5.1 In `src/presentation/pages/visitor-request/hooks/use-visitor-otp.ts`, capture the `proofToken` from `verifyVisitorOtpUseCase.execute(...)`'s response and pass it through `onVerified(registrationType, contact, proofToken)`.

## 6. Returning-visitor history hook and screen

- [x] 6.1 Add a hook (e.g. `src/presentation/pages/visitor-request/hooks/use-returning-visitor-portal.ts`) that calls `getVisitorPortalMeUseCase.execute(proofToken, ...)`, holds `history`/`prefill`/pagination/error state, exposes a "load more" action driven by the pagination metadata, and maps a 401 to a "return to OTP-request" signal.
- [x] 6.2 Add a return-visit history screen component (alongside `Components/otp/`) that lists each visit's tracking id, status, visit date, and purpose, and renders a "Start a new request" action.
- [x] 6.3 Render rate-limit (429) and service-misconfigured (404) errors from the lookup with a retry action that does not require re-verifying.

## 7. Wire history into the request flow and wizard prefill

- [x] 7.1 In `src/presentation/pages/visitor-request/visitor-request.tsx`, add the history screen as a third state between OTP verification and the wizard: on `onVerified`, run the lookup; render the history screen when it returns one or more visits, otherwise go straight to the wizard as today; on a 401 from the lookup, return to the OTP-request screen.
- [x] 7.2 Map a non-null `prefill` profile onto `VisitorRequestWizardInitialData`'s primary contact (full name, email, phone, preferred contact method, ID-proof type), leaving the ID-proof image and profile photo fields unfilled, when "Start a new request" is activated from the history screen.
- [x] 7.3 Confirm the wizard still renders with only registration type and contact pre-filled when `prefill` is null (first-time visitor / no history), unchanged from current behavior.

## 8. Verification

- [x] 8.1 Verified end-to-end against the real backend (ddev `vmss-new-api`, local Mailpit for OTP codes), driven through the actual UI at `/visitor/request` via a scripted Chromium session: a contact with prior history (`sedfse@gmail.com`) verified → history screen showed `INV-07ABC1A3`/"delivery" → "Start a new request" opened the wizard with fullName "rewr", email "sedfse@gmail.com", phone "213123123" pre-filled. A fresh first-time contact verified → went straight to the wizard with no history screen shown and only the verified email filled in (fullName empty).
- [x] 8.2 Verified via the same scripted session, mocking `visitor-portal/me`'s response: 401 → returned to the OTP-request screen (`#otp-contact` visible again), no history screen shown. 429 → history-screen shell shown with "You've made too many requests..." and a Retry action. 404 → history-screen shell shown with "This service is temporarily unavailable..." plus the backend's "Tenant not found or inactive" detail and a Retry action. Also independently confirmed the real backend's 401/429 shapes via curl (`{success:false,message,errors:null}`) and that `extractErrorMessage` already handles that envelope.
- [x] 8.3 Confirmed via the scripted session: seeding `sessionStorage['token']` (simulating a staff session) before triggering a 401 from `visitor-portal/me` left that key unchanged and did not dispatch `auth:session-expired` — the `ApiClient` fix (task group 4) works as designed. The proof token itself is held only in React state (never written to `localStorage`/`sessionStorage`) and is sent solely as the `Authorization` header on the `visitor-portal/me` request.
