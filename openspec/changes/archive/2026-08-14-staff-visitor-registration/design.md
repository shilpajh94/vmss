## Context

The self-service `visitor-request-wizard` already implements five of the six steps this change needs (Visit Info, Carried Items, Vehicle Info, Consent Agreement, Review & Confirm) as standalone components under `src/presentation/pages/visitor-request/Components/steps/`, driven by a `VisitRequestFormState` whose `visitInfo`, `carriedItems`, `vehicles`, and `consent` slices are independent of the visitor-contact shape. Submission goes through the unauthenticated `CREATE_VISIT_REQUEST` endpoint via `VisitRequestRepository` / `SubmitVisitRequestUseCase`.

The Figma "Register Visitor" screen (node 42:5) is the wizard's Step 1 for staff. Its primary-contact and add-visitor fields are full name, email, phone, preferred contact method, and ID proof type + upload — it does **not** collect address, visitor category, or a profile image, all of which the existing `VisitorSchema` requires (`.min(1)`). The staff dashboard's sidebar (`DashboardSidebar`) is currently a dashboard-only component with a hardcoded `active` item and no click handling.

See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Ship a staff-facing Register Visitor wizard visually identical to the Figma design for Step 1, functionally complete end-to-end through submission.
- Reuse the existing Visit Info / Carried Items / Vehicle Info / Consent Agreement / Review & Confirm step components rather than forking them.
- Attribute staff-submitted requests to the authenticated staff member via a new authenticated endpoint, without changing the self-service endpoint or its schema.

**Non-Goals:**
- No backend implementation — this change covers the frontend contract (endpoint shape, schema) only; the API itself is assumed to exist per `VITE_API_BASE_URL`.
- No changes to the self-service wizard's own requirements, fields, or endpoint.
- No OTP request/verify step in the staff wizard — the Figma stepper lists six steps with no OTP step, and the staff member is already authenticated.

## Decisions

**New domain schemas instead of reusing `VisitorSchema`/`VisitRequestSchema` for the visitor-contact shape.**
The staff form collects strictly fewer fields per visitor than self-service does (no address, visitor category, or profile image). Rather than force those fields into a form the design doesn't show, or send empty strings through a schema that models them as required, add `StaffVisitorSchema` (fullName, email, phone, preferredContactMethod, idProofType, idProofFileRef) and `StaffVisitRequestSchema` (registrationType, primaryContact, additionalVisitors, plus the *same* `visitInfo`/`carriedItems`/`vehicles`/`consent` shapes `VisitRequestSchema` already defines, so those parts stay structurally interchangeable with the reused step components). Alternative considered: extend `VisitorSchema` to make address/category optional — rejected because that field is a hard requirement in the self-service spec (visitor-request-wizard) and weakening it there to accommodate a different flow would be a silent behavior change to an unrelated capability.

**New authenticated endpoint `STAFF_CREATE_VISIT_REQUEST` (`hasToken: true`) instead of reusing `CREATE_VISIT_REQUEST`.**
`ApiClient` attaches the staff bearer token automatically when `hasToken: true`; the backend derives the submitting staff member from that token, so the client payload never needs to carry a staff identifier. This keeps the existing unauthenticated endpoint dedicated to kiosk traffic. Alternative considered: reuse `CREATE_VISIT_REQUEST` and add an optional staff-id field — rejected per the chosen approach of keeping self-service and staff submission paths independent.

**Reuse `VisitInfoStep`, `CarriedItemsStep`, `VehicleInfoStep`, `ConsentStep` unchanged; adapt `ReviewConfirmStep`'s props to a narrower shape.**
The first four operate only on their own form-state slice (`VisitInfoFormState`, `CarriedItemsFormState`, `Vehicle[]`, `ConsentFormState`) and the `Vehicle`/`VehicleSchema` type, all independent of visitor-contact fields, so they drop into the staff wizard as-is. `ReviewConfirmStep` currently likely renders the self-service visitor's address/category/profile image; it needs its visitor-summary rendering generalized to only show fields that are present, so it can summarize both a full self-service `VisitorFormEntry` and a narrower staff visitor entry without forking the component.

**Promote `DashboardSidebar` to shared presentation UI.**
Both the dashboard and the new wizard render the same sidebar chrome, differing only in which nav item is active and what "My actions" does. Move it to `src/presentation/components/` and parameterize the active item and navigation, per the clean-architecture rule that cross-feature component reuse requires promotion to shared UI rather than a direct cross-feature import.

**New route `/staff/visitors/new`, guarded like `/staff/dashboard`.**
Added to `App.tsx` alongside the existing staff routes; the page checks for a staff auth token the same way `StaffDashboardPage` does and redirects to `/staff/login` otherwise.

**Preserve the "OTP will be sent to this email" hint text under the email field for visual fidelity, without wiring an OTP step.**
The copy is inherited design-system text; since no OTP step exists among the wizard's six steps, it doesn't trigger any request/verify behavior in this flow.

**Treat the Figma step-3 label "Cancel Items" as a typo for "Carried Items."**
Every other step name (Visitor Info, Visit Info, Vehicle Info, Consent Agreement, Review & Confirm) matches the self-service wizard's step names and the reused `CarriedItemsStep` component exactly; "Carried Items" is used in the stepper and specs for consistency.

## Risks / Trade-offs

- [Two parallel visitor-contact schemas (self-service vs. staff) increase surface area] → Mitigated by sharing the `visitInfo`/`carriedItems`/`vehicles`/`consent` shapes between both `VisitRequestSchema` and `StaffVisitRequestSchema`, so only the contact fields diverge.
- [`ReviewConfirmStep` prop-shape changes could regress the self-service review screen] → Cover both usages with the existing visitor-request-wizard tests plus new staff-wizard tests before merging.
- [Backend endpoint `STAFF_CREATE_VISIT_REQUEST` may not exist yet] → Frontend work proceeds against the agreed contract (path, method, `hasToken: true`, response shape matching `VisitRequestResponseSchema`); submission will 404/fail until the backend ships it.

## Migration Plan

Purely additive: a new route, new schemas/endpoint, and a promoted shared component. No data migration. The self-service wizard and its endpoint are unmodified and can ship independently; if the staff endpoint isn't ready, the route can be merged behind normal review without affecting existing flows.
