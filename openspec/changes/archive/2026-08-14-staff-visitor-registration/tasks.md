## 1. Domain schemas

- [x] 1.1 Add `src/domain/entities/staff-visitor-schema.ts` with `StaffVisitorSchema` (fullName, email, phone, preferredContactMethod optional, idProofType, idProofFileRef optional) and its `z.infer` type.
- [x] 1.2 Add `src/domain/entities/staff-visit-request-schema.ts` with `StaffVisitRequestSchema` (registrationType, primaryContact: StaffVisitorSchema, additionalVisitors: StaffVisitorSchema[], visitInfo/carriedItems/vehicles/consent matching the shapes in `visit-request-schema.ts`) and its `z.infer` type. Reuse `VehicleSchema` from `vehicle-schema.ts`.

## 2. API endpoint and data layer

- [x] 2.1 Add `STAFF_CREATE_VISIT_REQUEST` to `API_ENDPOINTS` in `src/data/api/api-endpoints.ts` (`endpoint: "/staff/visit-requests"`, `method: "POST"`, `hasToken: true`).
- [x] 2.2 Add `src/data/repositories/staff-visit-request-repository.ts` exporting a `StaffVisitRequestRepository` port with `submit(request: StaffVisitRequest): Promise<VisitRequestResponse>`.
- [x] 2.3 Add `src/infrastructure/staff-visit-request-repository.ts` implementing `StaffVisitRequestRepository`, calling `apiClient.makeRequest` with `API_ENDPOINTS.STAFF_CREATE_VISIT_REQUEST` and `parserSchema: VisitRequestResponseSchema`.
- [x] 2.4 Add `src/data/use-cases/submit-staff-visit-request.ts` exporting `SubmitStaffVisitRequestUseCase`, constructor-injected with `StaffVisitRequestRepository`, `execute(request)` delegating to `submit`.
- [x] 2.5 Wire `resolveStaffVisitRequestRepository` and `resolveSubmitStaffVisitRequestUseCase` into `src/composition-root.ts`, exposing `submitStaffVisitRequestUseCase` on `AppDependencies`.

## 3. Shared sidebar promotion

- [x] 3.1 Move `DashboardSidebar` from `src/presentation/pages/staff-dashboard/Components/` to `src/presentation/components/`, parameterizing the active nav item (`activeItem: 'all-visitors' | 'my-actions' | 'audit-trail'`) and an `onMyActionsClick` (or `useNavigate`-based) handler instead of a hardcoded `active` flag.
- [x] 3.2 Update `src/presentation/pages/staff-dashboard/staff-dashboard.tsx` (and its hook, if it renders the sidebar) to import the shared component, pass `activeItem="all-visitors"`, and navigate to the Register Visitor route when "My actions" is activated.

## 4. Routing and page shell

- [x] 4.1 Add route `/staff/visitors/new` in `src/App.tsx` rendering the new `StaffVisitorRegistrationPage`.
- [x] 4.2 Create `src/presentation/pages/staff-visitor-registration/staff-visitor-registration.tsx`: check for a staff auth token, redirect to `/staff/login` if absent, otherwise render the shared sidebar (`activeItem="my-actions"`), a workspace header (signed-in staff name/role from `getCurrentStaffUserUseCase`, sign-out), the six-step stepper, and the active step's content.
- [x] 4.3 Create `src/presentation/pages/staff-visitor-registration/hooks/use-staff-visitor-registration-wizard.ts` managing current step, form state (registration type, primary contact, additional visitors, visitInfo, carriedItems, vehicles, consent), per-step validation gating "Next", and submission via `submitStaffVisitRequestUseCase`.
- [x] 4.4 Create `src/presentation/pages/staff-visitor-registration/types.ts` with a `StaffVisitorFormEntry` type (no address/category/profile image), a `StaffVisitRequestFormState` reusing `VisitInfoFormState`/`CarriedItemsFormState`/`ConsentFormState`/`Vehicle[]` from the visitor-request feature, and `toStaffVisitRequest(formState)` mapping to `StaffVisitRequest`.

## 5. Step 1 — Visitor Info (pixel-perfect from Figma)

- [x] 5.1 Create `src/presentation/pages/staff-visitor-registration/Components/RegistrationTypeToggle.tsx` (Individual/Group segmented control) matching the Figma "card-registration-type" styling.
- [x] 5.2 Create `src/presentation/pages/staff-visitor-registration/Components/PrimaryContactCard.tsx` with full name, email (plus the "OTP will be sent to this email" hint text), phone, a preferred-contact-method segmented toggle (Email/SMS), an ID proof type select, and an upload control, matching the Figma "card-primary-contact" layout.
- [x] 5.3 Create `src/presentation/pages/staff-visitor-registration/Components/VisitorDetailsTable.tsx` rendering added visitors (# / Full Name / Email-Phone / ID Proof / edit-delete actions), shown only in Group mode, matching the Figma "visitor-table".
- [x] 5.4 Create `src/presentation/pages/staff-visitor-registration/Components/AddVisitorForm.tsx` (inline full name/email/phone fields, ID proof select + upload, Cancel/"Add to List" actions) matching the Figma "inline-add-form", appending a valid entry to the visitor list and clearing itself.
- [x] 5.5 Compose the above into `Components/VisitorInfoStep.tsx`, enforcing: primary contact fields required; in Group mode, at least one added visitor required before "Next" is enabled.
- [x] 5.6 Wire file selection for ID proof through the existing `uploadVisitorDocumentUseCase`, enforcing PNG/JPG/PDF and 5MB limits, consistent with the self-service upload behavior.

## 6. Steps 2-6 — reuse existing components

- [x] 6.1 Confirm `VisitInfoStep`, `CarriedItemsStep`, and `VehicleInfoStep` from `src/presentation/pages/visitor-request/Components/steps/` accept only their own form-state slice (no visitor-contact coupling); import and reuse them directly in the staff wizard.
- [x] 6.2 Confirm `ConsentStep` reuses directly; wire it to the staff wizard's `consent` slice.
- [x] 6.3 Generalize `ReviewConfirmStep`'s visitor-summary rendering to accept either a full self-service visitor entry or a narrower staff visitor entry (fullName/email/phone/idProofType only), rendering address/category/profile image only when present. Verify the self-service review screen still renders unchanged.
- [x] 6.4 Wire the staff wizard's Review & Confirm step to summarize registration type, all visitor entries, visit info, carried items, vehicles, and consent, and to call `submitStaffVisitRequestUseCase` on confirmation.

## 7. Submission, errors, and cancel

- [x] 7.1 On successful submission, show a confirmation with the returned tracking reference.
- [x] 7.2 On submission failure, show an error message, remain on Review & Confirm, and preserve all entered form state for retry.
- [x] 7.3 Wire the footer "Cancel" control (present on every step per the Figma footer) to discard the in-progress form state and navigate back to `/staff/dashboard`.

## 8. Specs housekeeping

- [x] 8.1 Update `openspec/specs/staff-dashboard/spec.md`'s "My actions" behavior per this change's delta spec once implementation lands (handled at archive time; no action needed before then).
