## Context

`/visitor/request` currently renders `VisitorRequestPage`, which owns a `currentStep` number (0-5) driving the six wizard steps via `useVisitorRequestWizard()`. Dependencies reach the page only through `useAppDependencies()` (see `app-shell` spec and `.claude/rules/clean-architecture.md`). All HTTP calls must go through `ApiClient.makeRequest` with a registered `API_ENDPOINTS` entry and a Zod schema (`.claude/rules/data-api-layer.md`); there is no existing OTP endpoint, schema, port, or use case. `VisitRequestSchema` (the submission payload) has no OTP/session field, so verification does not need to hand anything to the final submit call — it only needs to gate rendering and pre-fill two wizard fields (registration type, primary contact).

See proposal.md - Why / What Changes for motivation and scope.

## Goals / Non-Goals

**Goals:**
- Gate the existing wizard behind an OTP request + verify phase, reusing the wizard's route (`/visitor/request`) rather than adding new routes.
- Follow the established port → use case → adapter → composition-root wiring for the two new network calls (request OTP, verify OTP).
- Pre-fill the wizard's registration type and primary contact from the verified data so the visitor isn't asked twice.
- Match the two approved screens visually using existing shared chrome (`PortalHeader`, `PortalFooter`) and design tokens — no new theme work.

**Non-Goals:**
- No resend-code timer/cooldown UI (not present in the approved screens).
- No persistent session/auth token carried from verification into the final visit-request submission — `VisitRequestSchema` is unchanged.
- No changes to the wizard's six steps themselves beyond accepting pre-filled initial values.

## Decisions

- **Single route, phase-driven, no router changes**: `VisitorRequestPage` gains a local phase state — `'otp-request' | 'otp-verify' | 'wizard'` — starting at `'otp-request'`. This mirrors the existing pattern of `currentStep` driving which step renders, keeps `App.tsx` routing untouched, and matches the screenshots (OTP screens use the same header/back-to-landing chrome as the wizard). Alternative considered: separate routes (`/visitor/request/otp`, `/visitor/request/verify`) — rejected as unnecessary indirection since there's no need for these intermediate screens to be deep-linkable or bookmarkable.
- **New capability folder, feature-scoped**: OTP UI lives under `src/presentation/pages/visitor-request/Components/otp/` (e.g. `OtpRequestScreen.tsx`, `OtpVerifyScreen.tsx`) and a new hook `use-visitor-otp.ts` under `src/presentation/pages/visitor-request/hooks/`, since the flow only exists in service of this one wizard entry point.
- **New port `VisitorOtpRepository`** (`src/data/repositories/visitor-otp-repository.ts`) with `requestOtp(contact, registrationType)` and `verifyOtp(contact, code)`, implemented by `HttpVisitorOtpRepository` (`src/infrastructure/`) using two new `API_ENDPOINTS` entries: `REQUEST_VISITOR_OTP` (`POST /visitor-otp/request`, `hasToken: false`) and `VERIFY_VISITOR_OTP` (`POST /visitor-otp/verify`, `hasToken: false`) — unauthenticated, matching the existing `CREATE_VISIT_REQUEST`/`TRACK_VISIT_REQUEST` pattern for pre-login visitor flows.
- **New use cases** `RequestVisitorOtpUseCase` and `VerifyVisitorOtpUseCase` (`src/data/use-cases/`), each constructor-injected with `VisitorOtpRepository`, wired into `AppDependencies` via `createApp()`'s lazy-resolver pattern alongside the existing visit-request/tracking use cases.
- **Response schemas kept minimal**: `VisitorOtpRequestResponseSchema` (`{ requested: boolean }` or similar acknowledgement) and `VisitorOtpVerifyResponseSchema` (`{ verified: boolean }`) under `src/domain/entities/` — deliberately no session/token field, since nothing downstream needs one (see Context). The UI shows the generic "If that contact is valid..." copy regardless of the acknowledgement's content, per the anti-enumeration requirement.
- **Pre-fill via lifted state, not props threading through routes**: `VisitorRequestPage` holds the verified `{ registrationType, contact }` in state after verify succeeds and passes it as the wizard's initial values; `useVisitorRequestWizard` accepts an optional initial-state override so `createInitialFormState()` remains the default for direct testing/storybook use.

## Risks / Trade-offs

- [No deep link to OTP screens or mid-wizard state] → Acceptable: matches current wizard behavior (also not deep-linkable mid-step), and nothing in the request asks for resumability.
- [Contact-format validation (mobile vs. email) is loose — the spec only requires non-empty] → Mitigation: defer strict format validation to the backend's OTP-request response; the requirement only commits the frontend to non-empty-field validation, avoiding speculative regex rules not shown in the approved design.
- [New unauthenticated endpoints are a target for OTP-request abuse (spam)] → Mitigation: rate-limiting/throttling is a backend concern, out of scope for this frontend change; noted here so it isn't lost.
