## 1. Domain schemas

- [x] 1.1 Create `src/domain/entities/visitor-schema.ts` (`VisitorSchema`: fullName, email, phone, address, visitorCategory, idProofType, idProofFileRef?, profileImageFileRef?)
- [x] 1.5 Add `visitorCategory` field to `VisitorSchema`, `VisitorFieldsForm`, and the wizard's per-visitor validation (post-implementation addition) — verified: renders, blocks "Next" until selected, appears in the Review summary
- [x] 1.2 Create `src/domain/entities/vehicle-schema.ts` (`VehicleSchema`: vehicleType, licensePlate, makeModel, color)
- [x] 1.3 Create `src/domain/entities/visit-request-schema.ts` (`VisitRequestSchema` + `VisitRequestResponseSchema`)
- [x] 1.4 Create `src/domain/entities/upload-response-schema.ts` (`UploadResponseSchema`: fileRef)

## 2. API contract and client

- [x] 2.1 Add `CREATE_VISIT_REQUEST` (`POST /visit-requests`, `hasToken: false`) and `UPLOAD_VISITOR_DOCUMENT` (`POST /uploads/visitor-documents`, `hasToken: false`) to `src/data/api/api-endpoints.ts`
- [x] 2.2 Add `uploadFile({ endpointConfig, file, parserSchema })` to `ApiClient` in `src/data/api/api-client.ts` (FormData body, no explicit Content-Type header)

## 3. Repository, use cases, composition root

- [x] 3.1 Create `src/data/repositories/visit-request-repository.ts` (port: `submit(request): Promise<VisitRequestResponse>`, `uploadDocument(file): Promise<UploadResponse>`)
- [x] 3.2 Create `src/infrastructure/visit-request-repository.ts` (adapter implementing the port via `ApiClient.makeRequest`/`uploadFile`)
- [x] 3.3 Create `src/data/use-cases/submit-visit-request.ts` and `src/data/use-cases/upload-visitor-document.ts`
- [x] 3.4 Wire `resolveVisitRequestRepository` → the two use cases in `composition-root.ts`; expose both on `AppDependencies`

## 4. Shared form primitives

- [x] 4.1 Create `src/presentation/components/ui/TextField.tsx`, `TextareaField.tsx`, `SelectField.tsx`, `Checkbox.tsx`
- [x] 4.2 Create `src/presentation/components/ui/FileUploadField.tsx` (accepts PNG/JPG/PDF, max 5MB, calls the upload use case on selection, surfaces validation errors)
- [x] 4.3 Create `src/presentation/components/ui/SegmentedToggle.tsx` (used for Individual/Group and vehicle type)

## 5. Shared header promotion

- [x] 5.1 Move `src/presentation/pages/visitor-portal-landing/Components/PortalHeader.tsx` to `src/presentation/components/PortalHeader.tsx`, adding an optional back-chevron prop
- [x] 5.2 Update the landing page to import the promoted `PortalHeader`

## 6. Wizard steps

- [x] 6.1 Create `src/presentation/pages/visitor-request/Components/steps/VisitorInfoStep.tsx` (Individual/Group toggle; primary contact fields incl. address, ID proof, profile image; group visitor list with add/edit/remove)
- [x] 6.2 Create `src/presentation/pages/visitor-request/Components/steps/VisitInfoStep.tsx` (purpose, host, date, time, duration, location, building, department, notes)
- [x] 6.3 Create `src/presentation/pages/visitor-request/Components/steps/CarriedItemsStep.tsx` (category checklist + optional description)
- [x] 6.4 Create `src/presentation/pages/visitor-request/Components/steps/VehicleInfoStep.tsx` (dynamic vehicle list with add/edit/remove)
- [x] 6.5 Create `src/presentation/pages/visitor-request/Components/steps/ConsentStep.tsx` (terms text + three required checkboxes)
- [x] 6.6 Create `src/presentation/pages/visitor-request/Components/steps/ReviewConfirmStep.tsx` (read-only summary of all steps, Back + Submit, loading/success/error states)
- [x] 6.7 Create `src/presentation/pages/visitor-request/Components/StepSidebar.tsx` (6-step progress indicator)

## 7. Wizard page and wiring

- [x] 7.1 Create `src/presentation/pages/visitor-request/hooks/use-visitor-request-wizard.ts` (step index + form state, per-step validation gating, submit via `useAppDependencies()`)
- [x] 7.2 Create `src/presentation/pages/visitor-request/visitor-request.tsx` composing the promoted header, `StepSidebar`, active step, and footer — also promoted `PortalFooter` to shared (same "second consumer now exists" reasoning as the header; the wizard's footer matches the landing page's per Figma)
- [x] 7.3 Register `/visitor/request` in `src/App.tsx`

## 8. Verification

- [x] 8.1 Run the app locally and confirm each step's required-field validation blocks "Next" per the spec (Visitor Info, Visit Info, Consent), and that Carried Items/Vehicle Info allow proceeding empty
- [x] 8.2 Confirm Individual vs Group shows the right fields, and Group blocks progression with zero visitors in the list
- [x] 8.3 Confirm file upload accepts PNG/JPG/PDF under 5MB and rejects oversized/unsupported files, for both ID proof and profile image
- [x] 8.4 Confirm the Review & Confirm step's summary reflects all previously entered data, including address, profile image, location, and building
- [x] 8.5 Confirm submitting against the (absent) backend shows the failure state without losing entered data
- [x] 8.6 Confirm the landing page's "Request Visit" button now lands on a working first step, and the back chevron returns to `/`
