## Why

An admin can add a custom field (e.g. "test") to the Vehicle Info step via
Form Builder. A visitor/staff user fills it in on the "Add New Vehicle" form
and clicks "Add to List" — but the vehicle table that appears afterward has
hardcoded columns (#, Vehicle Type, License Plate, Make/Model, Color,
Actions) and never renders the custom field, so the user has no way to tell
whether their answer was captured. The same gap exists on the Review &
Confirm step, whose Vehicle Info and Carried Items summaries only echo a
handful of hardcoded fields and drop every custom field answer, all the way
through to final submission.

Investigation confirmed this is a display-only gap, not data loss: custom
field values ARE captured in wizard state, sent in the API payload, and
persisted to `InvitationVehicle.custom_field_values` /
`Invitation.custom_field_values` (JSONB) on the backend, and echoed back in
the response. The fix is confined to the frontend rendering these values the
user already successfully submitted.

## What Changes

- **Vehicle Info step — dynamic table columns.** `VehicleInfoStep.tsx`'s
  vehicle list table renders one additional column per active custom field
  configured for the Vehicle Info step (using the `customFields` prop
  already passed into the component but currently unused for the table),
  alongside the existing fixed columns. A vehicle with no value for a given
  custom field shows an em dash, not a blank cell indistinguishable from
  "column doesn't exist."
- **Review & Confirm step — custom field values shown for Vehicle Info and
  Carried Items.** `ReviewConfirmStep.tsx`'s Vehicle Info summary (per
  vehicle) and Carried Items summary both render each active custom field's
  label and the submitted value, the same way the existing Consent Agreement
  summary already generically renders every consent key.
- No backend change: request/response schemas, persistence, and validation
  for `custom_field_values` are already correct and are out of scope.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `form-builder`: adds a requirement that an active, admin-configured
  custom field's captured value is displayed back to the user — in the
  Vehicle Info step's vehicle list and in the Review & Confirm step's
  summary for any step that supports custom fields (Vehicle Info, Carried
  Items) — not merely captured, sent, and persisted silently.

## Impact

- **Web** (`VMMS_WEB`, no backend changes):
  - `src/presentation/pages/visitor-request/Components/steps/VehicleInfoStep.tsx`
    — vehicle list table (`<thead>`/`<tbody>`, current hardcoded columns).
  - `src/presentation/pages/visitor-request/Components/steps/ReviewConfirmStep.tsx`
    — Vehicle Info and Carried Items summary sections.
  - Shared by both the public self-registration wizard and the staff wizard
    (`staff-visitor-registration.tsx` reuses the same step components), so
    the fix applies to both entry points automatically.
- **No breaking changes**: purely additive rendering of data that is already
  sent and stored today.
