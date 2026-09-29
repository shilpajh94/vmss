## Context

See `proposal.md` - Why. Relevant current-state constraints:

- `useVisitorOtp` (`src/presentation/pages/visitor-request/hooks/use-visitor-otp.ts`) already calls `VerifyVisitorOtpUseCase`, whose response already includes `proofToken` (`src/domain/entities/visitor-otp-verify-schema.ts`) — it's just discarded today.
- `VisitorRequestPage` (`src/presentation/pages/visitor-request/visitor-request.tsx`) is a small state machine: it renders the OTP screens until `onVerified` fires, then sets `wizardInitial` and renders the wizard. There is no intermediate state today.
- `ApiClient.makeRequest`'s `hasToken: true` path is hardwired to a single global credential: `sessionStorage.getItem('token')`, the staff/admin session token (`data-api-layer.md`). The visitor's `proofToken` is a different, short-lived (15 min), visitor-scoped credential and must never be read from or written to that key.
- `ApiClient.handleAuthFailure` currently treats **any** response's `401`, on **any** endpoint regardless of `hasToken`, as "the staff session token is dead": it clears `sessionStorage['token']` and dispatches the app-wide `SESSION_EXPIRED_EVENT`. Today this is dormant for `hasToken: false` endpoints (OTP request/verify, track-request) because none of them actually return 401. `visitor-portal/me` will return 401 routinely (expired proof token), so this dormant behavior would otherwise incorrectly sign the staff session out on every expired visitor proof token.
- `VisitRequestSchema`/`VisitorSchema` (`src/domain/entities`) already define the wizard's primary-contact shape (`fullName`, `email`, `phone`, `preferredContactMethod`, `idProofType`); the prefill payload maps directly onto a subset of `VisitorSchema`.

## Goals / Non-Goals

**Goals:**
- Fetch `visitor-portal/me` with the OTP proof token right after verification, without touching the staff-session auth mechanism.
- Reuse the existing wizard and its `VisitorSchema`-shaped primary-contact fields for the prefill, rather than introducing a parallel form.
- Keep the proof token out of `localStorage` and out of logs.

**Non-Goals:**
- Changing `POST /registrations/walk-in` or any staff/admin-authenticated endpoint.
- Building a general-purpose per-request bearer-token mechanism in `ApiClient` — this design adds the minimum needed for one caller to supply its own `Authorization` header.
- Prefilling the ID-proof image or profile photo (explicitly excluded by the backend and by the specs).

## Decisions

**1. Proof token travels as an explicit `Authorization` header on the call, not through `hasToken`.**
`API_ENDPOINTS.GET_VISITOR_PORTAL_ME` is declared `hasToken: false`, and the infrastructure adapter passes `headers: { Authorization: \`Bearer ${proofToken}\` }` via `makeRequest`'s existing `headers` option (already used elsewhere for `X-Branch-ID`). Alternative considered: add a second `hasToken`-like flag/credential source to `ApiClient` — rejected as unnecessary generality for a single caller; the existing `headers` escape hatch already covers it.

**2. `ApiClient.handleAuthFailure` scopes its session-clearing/redirect behavior to `hasToken` endpoints only.**
Change the 401 branch to only clear `sessionStorage['token']` and dispatch `SESSION_EXPIRED_EVENT` when the endpoint that was called has `hasToken: true`. For `hasToken: false` endpoints, a 401 falls through to the same plain-`Error`-with-backend-message path already used for other non-2xx statuses. This is a shared-file change but only changes behavior for the (previously unexercised) 401-on-public-endpoint case. The visitor-portal adapter/use case catches that plain error and the calling hook maps it to "return to OTP-verify" per the `visitor-otp-verification` delta spec.

**3. `proofToken` is kept in React state (in memory) for the lifetime of the flow, not `sessionStorage`.**
It's produced and consumed within the same page's component tree (verify → lookup → history/wizard), so component state is sufficient and trivially satisfies "never `localStorage`, never logged." A page refresh drops it, which just re-enters OTP verification — the same as the existing OTP session (`contact`/`registrationType`) already does today. Alternative: `sessionStorage`, to survive a refresh — rejected for now since nothing in the requirements asks the flow to survive a reload, and it avoids adding another sessionStorage key to reason about.

**4. History/prefill lookup slots into the existing `VisitorRequestPage` state machine as a third state, not a new route.**
Per the confirmed direction (extend the existing "Request a Visit" flow rather than a new landing entry point), `VisitorRequestPage` gains a `history` result (from a new `useReturningVisitorPortal`-style hook) between the OTP phase and `wizardInitial`. `useVisitorOtp` itself is unchanged in responsibility (still just OTP request/verify) but its `onVerified` callback now also receives the `proofToken`, so the page can trigger the lookup.

**5. Data layer follows the standard checklist (`data-api-layer.md`).**
- `API_ENDPOINTS.GET_VISITOR_PORTAL_ME`: `{ endpoint: "/visitor-portal/me", method: "GET", hasToken: false }`.
- `src/domain/entities/visitor-portal-schema.ts`: `VisitHistoryEntrySchema`, `VisitorPrefillSchema` (nullable), a `PaginationSchema`, composed into `VisitorPortalMeResponseSchema` (`success`/`message`/`data` envelope, matching the OTP schemas' shape).
- Port `VisitorPortalRepository` (`src/data/repositories/`): `getMe(proofToken: string, page?: PageParams): Promise<VisitorPortalMe>`.
- Confirmed against `VMMS_API/src/vmss_api/visitor_return_visit/schemas.py` (source of truth over the announcement email): `history[]` entries are `{trackingId, status, visitDate: string|null, purpose: string|null}`; `prefill` is `{fullName, email: string|null, phone: string|null, preferredContactMethod: string, idProofType: string|null, photoUrl: string|null} | null`; `pagination` is `{page, pageSize, total, totalPages}`. All JSON keys are camelCase (backend's `CamelModel`). 401 responses carry `{detail: "Not authenticated"}` or `{detail: "Not a verified-contact proof token"}`; 404 (tenant misconfigured) carries `{detail: "Tenant not found or inactive"}`; both are handled generically by the existing `extractErrorMessage`.
- Adapter `src/infrastructure/visitor-portal-repository.ts`: implements the port, calls `apiClient.makeRequest` with the header above.
- Use case `GetVisitorPortalMeUseCase` (`src/data/use-cases/`): thin delegation, as with the existing OTP use cases.
- `composition-root.ts`: lazy `resolveVisitorPortalRepository` → `resolveGetVisitorPortalMeUseCase`, exposed on `AppDependencies`.

**6. `ApiClient` throws a typed `ApiError` (carrying the HTTP `status`) instead of a plain `Error`.**
Discovered while implementing: today `ensureOk` throws `new Error(extractErrorMessage(...))` with no status code attached, and no existing caller in the codebase needs to distinguish status codes (they all just show `err.message`). This feature needs to: return to OTP-verify on 401, show a rate-limit message on 429, and a misconfiguration message on 404 — which requires the status to survive the throw. Add `export class ApiError extends Error { status: number }` (e.g. in `api-error.ts`) and throw it from `ensureOk`/the 401 fallthrough added in Decision 2. `ApiError extends Error`, so every existing `catch` that does `err instanceof Error ? err.message : ...` is unaffected.

## Risks / Trade-offs

- [Exact `history`/`prefill`/`pagination` field names and nullability aren't confirmed here — the email summarizes them but the authoritative shapes are in `docs/features/visitor_return_visit.md` in the API repo, which isn't available in this codebase] → Mitigation: write the Zod schemas from the email's field list, treat confirming them against that doc as the first implementation task; a shape mismatch fails loudly as a `ZodError` rather than silently mis-mapping data.
- [Change 2 (scoping `handleAuthFailure` to `hasToken`) touches shared `ApiClient` logic used by every existing endpoint] → Mitigation: the changed branch only affects the previously-unexercised case (401 from a `hasToken: false` endpoint); all `hasToken: true` endpoints keep today's exact behavior. Cover both branches with a unit test on `ApiClient`.
- [In-memory-only `proofToken` means the returning-visitor flow does not survive a page refresh] → Mitigation: acceptable — matches existing OTP-session behavior; a refresh simply returns the visitor to "Request a Visit" from the top.
