## 1. Domain & API registry

- [x] 1.1 Add `REQUEST_VISITOR_OTP` (`POST /visitor-otp/request`, `hasToken: false`) and `VERIFY_VISITOR_OTP` (`POST /visitor-otp/verify`, `hasToken: false`) to `src/data/api/api-endpoints.ts`
- [x] 1.2 Add `VisitorOtpRequestSchema`/`VisitorOtpRequestResponseSchema` and `VisitorOtpVerifySchema`/`VisitorOtpVerifyResponseSchema` (+ inferred types) under `src/domain/entities/`

## 2. Data layer (port & use cases)

- [x] 2.1 Add `VisitorOtpRepository` port interface (`requestOtp`, `verifyOtp`) under `src/data/repositories/`
- [x] 2.2 Add `RequestVisitorOtpUseCase` under `src/data/use-cases/`, constructor-injected with `VisitorOtpRepository`
- [x] 2.3 Add `VerifyVisitorOtpUseCase` under `src/data/use-cases/`, constructor-injected with `VisitorOtpRepository`

## 3. Infrastructure & composition root

- [x] 3.1 Add `HttpVisitorOtpRepository` adapter under `src/infrastructure/`, implementing `VisitorOtpRepository` via `ApiClient.makeRequest` and the new endpoints/schemas
- [x] 3.2 Wire `visitorOtpRepository`, `requestVisitorOtpUseCase`, `verifyVisitorOtpUseCase` into `createApp()` and `AppDependencies` in `src/composition-root.ts`, following the existing lazy-resolver pattern

## 4. OTP request screen

- [x] 4.1 Build `OtpRequestScreen` component (registration type toggle defaulting to "Single visitor", mobile-number-or-email field, "Request OTP" button) reusing `PortalHeader`/`PortalFooter` and design-theme tokens, matching the approved screen
- [x] 4.2 Add `use-visitor-otp.ts` hook under `src/presentation/pages/visitor-request/hooks/` exposing phase state, registration type, contact, request/verify handlers, and validation/error state, calling `requestVisitorOtpUseCase`/`verifyVisitorOtpUseCase` via `useAppDependencies()`
- [x] 4.3 Validate the contact field is non-empty before calling "Request OTP"; on success, show the generic "If that contact is valid, a verification code has been sent to it." confirmation and advance to the verify phase

## 5. OTP verify screen

- [x] 5.1 Build `OtpVerifyScreen` component (verification-code field, "Verify and continue" button, "Use a different number or email" link) reusing the same shared chrome/tokens, matching the approved screen
- [x] 5.2 Validate the code field is non-empty before calling "Verify and continue"; show an inline error and stay on the screen when verification fails, without discarding the current OTP session
- [x] 5.3 Wire "Use a different number or email" to return to the OTP request phase, ready for a new contact/registration type

## 6. Wizard integration

- [x] 6.1 Add a phase state (`'otp-request' | 'otp-verify' | 'wizard'`) to `VisitorRequestPage`, starting at `'otp-request'`, rendering the corresponding screen/wizard per phase
- [x] 6.2 Extend `useVisitorRequestWizard` to accept an optional initial registration type + primary contact override, defaulting to `createInitialFormState()` when absent
- [x] 6.3 On successful verification, transition to the `'wizard'` phase and initialize the wizard with the verified registration type and contact (mobile number or email) pre-filled into the primary contact's corresponding field

## 7. Verification

- [x] 7.1 Manually walk the flow in the browser: landing → "Request Visit" → OTP request → OTP verify → wizard Visitor Info step, confirming pre-filled registration type/contact and that visual theme matches the wizard and landing page
- [x] 7.2 Confirm the wizard is unreachable at `/visitor/request` without completing verification (no direct render of `VisitorInfoStep` before the OTP phases)
