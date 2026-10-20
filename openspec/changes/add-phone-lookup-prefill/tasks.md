## 1. Data & domain layers

- [x] 1.1 Add `email: z.string().nullish()` to `StaffVisitorLookupSchema` in `src/domain/entities/staff-visitor-lookup-schema.ts` and update its header comment
- [x] 1.2 Add `LOOKUP_STAFF_VISITOR_BY_PHONE` (`/invitations/lookup-by-phone`, GET, `hasToken: true`) to `API_ENDPOINTS`
- [x] 1.3 Add `lookupByPhone(phone)` to the `StaffVisitorLookupRepository` port
- [x] 1.4 Implement `lookupByPhone` in `HttpStaffVisitorLookupRepository` via `makeRequest` with `queryParams: { phone }`
- [x] 1.5 Create `src/data/use-cases/lookup-staff-visitor-by-phone.ts`

## 2. Composition root

- [x] 2.1 Add `resolveLookupStaffVisitorByPhoneUseCase` and expose `lookupStaffVisitorByPhoneUseCase` on `AppDependencies`/`createApp()`; update any test/mocks of `AppDependencies`

## 3. Wizard behaviour

- [x] 3.1 Extract an `applyLookupMatch` helper that fills only empty primary-contact fields and files (name, email, preferred contact method, category, ID proof type, photo, ID proof file)
- [x] 3.2 Refactor the existing email lookup effect to use the helper and skip fetching files already present
- [x] 3.3 Add the debounced phone lookup effect (≥7 digits, ≤50 chars, digits-keyed last-looked-up ref, stale-response guard, silent on null/422/error)
- [x] 3.4 Sync `lastLookedUpEmailRef`/`lastLookedUpPhoneRef` when a match fills the other field to avoid a redundant second lookup
- [x] 3.5 Show the "Existing visitor found" toast only when at least one field was actually prefilled

## 4. Verification

- [ ] 4.1 Add/update tests: phone <7 digits no request; hit prefills empty fields only; typed values preserved; null email; null `idProofUrl`; `data: null`; request failure; email-lookup no-overwrite
- [x] 4.2 Run typecheck, lint and the test suite
- [ ] 4.3 After backend deployment, verify on stage (formats `+91 95442 32271`, `95442-32271`, `9544232271`) and confirm `X-Branch-ID` behaviour with the backend; add the header per design decision 8 if required
