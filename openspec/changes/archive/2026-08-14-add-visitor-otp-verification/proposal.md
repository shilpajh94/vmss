## Why

Today, activating "Request Visit" on the landing page drops the visitor straight into the 6-step request wizard with no verification of the contact they're registering. The approved design adds an OTP gate — a "Request a Visit" screen that collects registration type and a mobile number/email, and a verification-code screen — before the wizard begins, so a visit request is tied to a contact the visitor actually controls.

## What Changes

- Add a new "Request a Visit" OTP-request screen at the existing `/visitor/request` entry point: registration type toggle (Single visitor / Group visitors), a single mobile-number-or-email field, and a "Request OTP" action that requests a one-time verification code for that contact.
- Add a new OTP-verify screen shown after a successful OTP request: a single verification-code field, a "Verify and continue" action, and a "Use a different number or email" action that returns to the request screen.
- On successful verification, proceed into the existing 6-step visitor request wizard (`visitor-request-wizard`), pre-filling the wizard's registration type and the verified contact's mobile number or email so the visitor doesn't re-enter them.
- **BREAKING**: The visitor request wizard is no longer reachable immediately from the landing page's "Request Visit" action — it now renders only after OTP verification succeeds.
- Both new screens reuse the existing portal theme and chrome (`PortalHeader` with back navigation, `PortalFooter`, design-theme tokens) so they match the wizard's look and feel.

## Capabilities

### New Capabilities
- `visitor-otp-verification`: Lets a visitor request and verify a one-time code for their mobile number or email before starting a visit request, gating entry to the visitor request wizard.

### Modified Capabilities
- `visitor-request-wizard`: The wizard's entry requirement changes — it is reachable only after OTP verification succeeds, not directly from the landing page's "Request Visit" action. The wizard's first step now accepts pre-filled registration type and contact fields from the verification step.

## Impact

- **Presentation**: new `visitor-otp-request` page/phase and `visitor-otp-verify` page/phase under `src/presentation/pages/visitor-request/` (or a sibling feature folder), reusing `PortalHeader`/`PortalFooter` and design-theme tokens; the `visitor-request` page gains an OTP phase gate ahead of its existing step state.
- **Data/domain**: new `API_ENDPOINTS` entries (`REQUEST_OTP`, `VERIFY_OTP`), new Zod schemas under `src/domain/entities/`, a new repository port under `src/data/repositories/`, and new use cases under `src/data/use-cases/`.
- **Infrastructure**: new adapter under `src/infrastructure/` implementing the OTP port via `ApiClient`.
- **Composition root**: `AppDependencies` gains the OTP use case(s), wired through `createApp()`.
- No changes to the visit-request submission contract (`VisitRequestSchema`) — OTP verification is a UI/flow gate only, not a field on the submitted request.
