## Why

Returning visitors currently have to re-enter their full profile (name, email, phone, contact preference, ID-proof type) every time they submit a new visit request, even though the backend already has that data from a prior visit. Backend support for looking up a verified visitor's history and a prefill profile is now live (`GET /visitor-portal/me`, reusing the existing OTP proof flow), so the wizard can skip re-collecting known fields and show the visitor their past visits.

## What Changes

- After a visitor completes the existing OTP verification (`visitor-otp-verification`), call `GET /visitor-portal/me` with the verification's `proofToken` before deciding where to route the visitor.
- If the visitor has past visits, show a history screen (trackingId, status, visitDate, purpose) with a "Start a new request" action that opens the visitor request wizard pre-filled from the returned `prefill` profile.
- If the visitor has no history (first-time visitor, `prefill` is `null`), skip the history screen and route straight into the empty wizard, exactly as today.
- Extend the wizard's existing post-verification prefill (registration type + contact) to also carry full name, email, phone, preferred contact method, and ID-proof type when a `prefill` profile is available. The ID-proof document image and the profile photo are never prefilled — a returning visitor still uploads both fresh, exactly like a first-time visitor.
- Store the `proofToken` returned by OTP verification in memory/sessionStorage only (never `localStorage`, never logged), and use it solely as the bearer token for the `visitor-portal/me` call; it is not sent to `/registrations/walk-in`, which is unchanged.
- Handle `401` (expired/invalid token) by returning the visitor to OTP verification, `429` (rate limited) and `404` (service misconfigured) with a clear error, without losing the OTP session details already required by `visitor-otp-verification`.

## Capabilities

### New Capabilities
- `visitor-return-history`: fetching a verified visitor's visit history and prefill profile from `visitor-portal/me`, rendering the history list, and handling that call's error states (401/429/404).

### Modified Capabilities
- `visitor-otp-verification`: successful verification now branches through the history lookup instead of always proceeding straight into the wizard.
- `visitor-request-wizard`: the wizard's post-verification prefill requirement now also carries full-profile fields (full name, email, phone, preferred contact method, ID-proof type) when the verified visitor has a non-null prefill profile, in addition to the registration type and contact it already pre-fills.

## Impact

- New: `API_ENDPOINTS.GET_VISITOR_PORTAL_ME` (or similar) in `src/data/api/api-endpoints.ts`; domain schemas for the `history`/`prefill`/`pagination` response shape; a `visitor-portal` repository port + infrastructure adapter; a use case wired into `composition-root.ts`.
- Changed: `src/presentation/pages/visitor-request/hooks/use-visitor-otp.ts` (capture `proofToken`, call the new use case after verify, branch on history), the wizard's prefill-mapping logic, and a new history screen component alongside the existing `otp/` components.
- No change to `POST /registrations/walk-in` or its request contract.
