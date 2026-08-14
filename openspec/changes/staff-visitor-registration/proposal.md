## Why

Staff currently have no way to create a visitor pass request from inside the staff portal — the only entry point today is the public, unauthenticated self-service wizard on the visitor landing page. The Figma design ("Register Visitor", node 42:5) specifies a staff-facing registration flow so front-desk/host staff can register a visitor or a group of visitors themselves, without routing every walk-in through the kiosk.

## What Changes

- Add a new "Register Visitor" 6-step wizard (Visitor Info → Visit Info → Carried Items → Vehicle Info → Consent Agreement → Review & Confirm) rendered inside the staff shell (sidebar + workspace header), reachable from the staff dashboard.
- Step 1 (Visitor Info) is built pixel-for-pixel from the Figma design: a registration-type toggle (Individual/Group), primary contact fields (full name, email with an "OTP will be sent to this email" hint, phone, preferred contact method, ID proof type + upload), and, in Group mode, an editable visitor list (table of added visitors plus an inline add-visitor form).
- Steps 2-6 reuse the existing visitor-request-wizard step components (Visit Info, Carried Items, Vehicle Info, Consent Agreement, Review & Confirm) restyled inside the staff shell, so the same validation rules apply to staff-submitted requests.
- The staff dashboard's "My actions" sidebar item, currently inert, becomes a functional link that opens the Register Visitor wizard.
- Add a new authenticated submission path (endpoint, schema, repository, use case) so a staff-submitted visit request records which staff member created it, kept separate from the existing unauthenticated self-service submission endpoint.

## Capabilities

### New Capabilities
- `staff-visitor-registration`: the staff-facing "Register Visitor" wizard — registration type selection, primary contact and group visitor list entry, reuse of the existing visit-info/carried-items/vehicle/consent/review steps, and authenticated submission attributed to the signed-in staff member.

### Modified Capabilities
- `staff-dashboard`: the "My actions" sidebar item's requirement changes from "renders but does not navigate anywhere" to "navigates to the Register Visitor wizard".

## Impact

- **New**: `src/presentation/pages/staff-visitor-registration/` (page, `Components/`, `hooks/`), a new `StaffVisitRequestSchema`/reused `VisitRequestSchema` fields in `src/domain/entities/`, a new port in `src/data/repositories/`, a new use case in `src/data/use-cases/`, a new adapter in `src/infrastructure/`, a new `API_ENDPOINTS.STAFF_CREATE_VISIT_REQUEST` entry (`hasToken: true`), and composition-root wiring exposing the new use case via `AppDependencies`.
- **Modified**: `src/presentation/pages/staff-dashboard/Components/DashboardSidebar.tsx` (or equivalent) to make "My actions" a working navigation link; the app's router to add the new wizard route.
- **Reused, unmodified**: the existing step components under `src/presentation/pages/visitor-request/Components/steps/` and their underlying validation logic; the existing unauthenticated `CREATE_VISIT_REQUEST` endpoint remains dedicated to self-service kiosk submissions.
