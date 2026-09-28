## Why

Investigating why "ID Proof Type"/"Vehicle Type" can't have their Form
Builder *type* changed (they're correctly locked — both are hardcoded
Pydantic enums server-side, `IdProofType`/`VehicleType`, and changing the
input type would break registration validation) surfaced a deeper, real
gap: even though these two fields already have an editable `options` list
in the Field Properties panel (they're not required-locked), editing it
has **zero effect**. An admin who adds "Voter ID" to ID Proof Type's
options today gets a value that the backend's hardcoded `IdProofType` enum
still rejects, and the visitor/staff forms don't even show it — both the
request schema and the frontend forms hardcode the same fixed lists,
completely independent of what Form Builder stores. Unlike Visitor
Category (which already has its own live, admin-manageable catalog these
two fields lack), there is genuinely no way today to add, remove, or
rename an ID proof type or vehicle type choice without a code change and
redeploy.

## What Changes

- `id_proof_type` (Visitor Info) and `vehicle_type` (Vehicle Info) become
  genuinely admin-configurable through the Form Builder options editor
  that already exists for them — the same mechanism Carried Items'
  checkbox options already use (`CarriedItemsSubmit.items`: "a valid key is
  whatever the calling branch's published step currently declares as an
  option — validated dynamically," not a fixed enum). **BREAKING** (request
  contract): `VisitorSubmit.id_proof_type`,
  `InvitationPrimaryContactCreate.id_proof_type`, and
  `VehicleSubmit.vehicle_type` stop being validated against the hardcoded
  `IdProofType`/`VehicleType` enums and become plain strings, validated
  instead against the calling branch's currently configured options for
  that field — mirroring the carried-items/consent-keys pattern already
  used elsewhere in the same endpoint.
- The Form Builder's "system fields don't need non-empty options" exemption
  (`_requires_static_options`) narrows to only `visitor_category` — the one
  field whose real options genuinely come from elsewhere (the separate
  Visitor Categories catalog). `id_proof_type`/`vehicle_type` now require a
  non-empty options list to publish, the same as any other admin-authored
  dropdown, since their options are now load-bearing.
- The visitor self-registration wizard and staff pre-registration wizard
  stop hardcoding the ID proof type / vehicle type choice lists and render
  whatever the branch's effective form currently declares for those two
  fields — the same reactive pattern already used for
  `idProofActive`/`idProofRequired` (`VisitorInfoFieldState`) and
  `makeModelActive`/`colorActive` (`VehicleInfoFieldState`), extended with
  an `Options` field each.
- Out of scope: Visitor Category is untouched — it already has its own
  admin-manageable catalog outside Form Builder, and the exemption that
  lets it skip the "must have static options" rule stays exactly as it is.

## Capabilities

### New Capabilities

(none — this continues refining the existing `invitations` and
`form-builder` capabilities)

### Modified Capabilities

- `invitations`: `id_proof_type`/`vehicle_type` submissions are validated
  against the calling branch's currently configured Form Builder options
  for those fields, not a fixed server-side enum.
- `form-builder`: narrows which system fields are exempt from the
  "dropdown/checkbox fields must declare non-empty options" rule to just
  `visitor_category`.

## Impact

- **Backend (`VMSS_API`)**:
  - `src/vmss_api/invitations/schemas.py` — remove `IdProofType`/
    `VehicleType` enums; `VisitorSubmit.id_proof_type`,
    `InvitationPrimaryContactCreate.id_proof_type` become
    `str | None`; `VehicleSubmit.vehicle_type` becomes `str`.
  - `src/vmss_api/form_builder/validation.py` — add
    `allowed_id_proof_types(effective_form)` and
    `allowed_vehicle_types(effective_form)`, mirroring
    `allowed_carried_item_keys`.
  - `src/vmss_api/invitations/service.py::create_invitation` — validate
    the primary contact's and each visitor's `id_proof_type` (when set)
    against `allowed_id_proof_types`, and each vehicle's `vehicle_type`
    against `allowed_vehicle_types`, mirroring the existing carried-items/
    consent-keys 422 pattern.
  - `src/vmss_api/form_builder/service.py::_requires_static_options` —
    narrow the exemption from "any `is_system` field" to just the
    `visitor_category` field key.
  - No database migration: both columns are already plain
    `String`/`String | None`, never enum-backed at the DB layer.
- **Frontend (`VMMS_WEB`)**:
  - `src/presentation/pages/visitor-request/hooks/use-visitor-request-wizard.ts`
    and `src/presentation/pages/staff-visitor-registration/hooks/use-staff-visitor-registration-wizard.ts` —
    extend `VisitorInfoFieldState`/`VehicleInfoFieldState` with
    `idProofOptions`/`vehicleTypeOptions: string[]`, resolved from the
    effective form.
  - `src/presentation/pages/visitor-request/Components/steps/VisitorFieldsForm.tsx`,
    `src/presentation/pages/staff-visitor-registration/Components/constants.ts`
    (and its consumers `AddVisitorForm.tsx`/`PrimaryContactCard.tsx`),
    `src/presentation/pages/visitor-request/Components/steps/VehicleInfoStep.tsx` —
    drop the hardcoded option-list constants; render the live list from
    props instead.
  - Any remaining display-only lookup of a stored id-proof-type/vehicle-
    type value (e.g. `ReviewConfirmStep.tsx`, `VisitorDetailsTable.tsx`,
    `VisitorInfoModal.tsx`) displays the raw stored string directly instead
    of mapping it through a hardcoded label table.
- **Tests**: new backend `pytest` coverage for the dynamic validation
  (unknown id-proof-type/vehicle-type rejected, branch-customized value
  accepted, options-required-to-publish for both fields) in
  `invitations/tests.py` and `form_builder/tests.py`. Frontend has no test
  framework in this repo (pre-existing, unchanged).
