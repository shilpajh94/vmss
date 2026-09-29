## 1. Backend: Loosen Request Schema

- [x] 1.1 Remove `IdProofType` and `VehicleType` (`invitations/schemas.py`)
- [x] 1.2 Change `VisitorSubmit.id_proof_type` and
      `InvitationPrimaryContactCreate.id_proof_type` to
      `str | None = Field(default=None, max_length=100)`
- [x] 1.3 Change `VehicleSubmit.vehicle_type` to
      `str = Field(max_length=50)`

## 2. Backend: Dynamic Validation

- [x] 2.1 Add `allowed_id_proof_types(effective_form)` to
      `form_builder/validation.py`, mirroring
      `allowed_carried_item_keys` (`_find_field(effective_form,
      "visitor_info", "id_proof_type")["options"]`, empty set if absent)
- [x] 2.2 Add `allowed_vehicle_types(effective_form)`, same pattern for
      `_find_field(effective_form, "vehicle_info", "vehicle_type")`
- [x] 2.3 In `invitations/service.py::create_invitation`, validate the
      primary contact's `id_proof_type` (when set) and each visitor's
      `id_proof_type` (when set) against `allowed_id_proof_types`,
      rejecting with a 422 that names the invalid value(s), mirroring the
      existing carried-items/consent-keys rejection style and
      `registration_form_config_validation_failed` warning log
- [x] 2.4 Validate each vehicle's `vehicle_type` against
      `allowed_vehicle_types` the same way
- [x] 2.5 Confirm `registrations/service.py::create_walk_in_registration`
      needs no separate change (delegates to `create_invitation` verbatim)

## 3. Backend: Narrow the Options-Required Exemption

- [x] 3.1 In `form_builder/service.py`, replace
      `_requires_static_options`'s `not field_row.is_system` check with a
      named-key exemption: `field_row.key not in
      _EXTERNALLY_CATALOGED_FIELD_KEYS` where
      `_EXTERNALLY_CATALOGED_FIELD_KEYS = frozenset({"visitor_category"})`
- [x] 3.2 Confirm this affects both call sites of
      `_requires_static_options` (`update_field`'s resulting-options check
      added by `add-static-text-field-and-unlock-toggle`, and
      `_validate_draft_for_publish`)

## 4. Backend Tests

- [x] 4.1 `pytest` test: creating/updating an invitation with an
      `idProofType` not in the branch's configured options is rejected —
      already covered by the pre-existing
      `test_create_invitation_invalid_id_proof_type_rejected` (confirmed
      it still passes: previously a Pydantic enum rejection, now this
      change's dynamic check, same 422 outcome)
- [x] 4.2 `pytest` test: an admin-added ID Proof Type option (e.g. "Voter
      ID") is accepted once published
      (`test_create_invitation_admin_added_id_proof_type_option_accepted`)
- [x] 4.3 `pytest` test: a `vehicleType` not in the branch's configured
      options is rejected (pre-existing
      `test_create_invitation_invalid_vehicle_type_rejected`, confirmed
      still passing); an admin-added option is accepted once published
      (`test_create_invitation_admin_added_vehicle_type_option_accepted`)
- [x] 4.4 `pytest` test: "ID Proof Type"'s options cannot be emptied —
      rejected at update time (`test_id_proof_type_options_cannot_be_emptied`),
      before a publish could ever see an emptied state; this is a stronger
      guarantee than a publish-time-only check, since the API path to reach
      that state no longer exists at all
- [x] 4.5 `pytest` test: same for "Vehicle Type"
      (`test_vehicle_type_options_cannot_be_emptied`)
- [x] 4.6 `pytest` test: "Visitor Category" with no options still publishes
      successfully (`test_visitor_category_remains_exempt_from_options_required`)
      — confirms the exemption narrowing didn't regress the one field it
      must still cover
- [x] 4.7 `pytest` test: an invitation created against a branch that has
      never customized either field still accepts the original four ID
      proof types and three vehicle types
      (`test_create_invitation_default_id_proof_and_vehicle_types_still_accepted`) —
      also implicitly covered by every other passing invitation test using
      default values

## 5. Frontend: Thread Live Options Through Both Wizards

- [x] 5.1 `use-visitor-request-wizard.ts`: extend `VisitorInfoFieldState`
      with `idProofOptions: string[]`, computed in the existing
      `visitorInfoFields` `useMemo` from the resolved `id_proof_type`
      field's `options`
- [x] 5.2 `use-staff-visitor-registration-wizard.ts`: same addition to its
      own `visitorInfoFields` `useMemo`
- [x] 5.3 `VehicleInfoStep.tsx`: extend `VehicleInfoFieldState` with
      `vehicleTypeOptions: string[]`
- [x] 5.4 Both wizard hooks' `vehicleInfoFields` `useMemo`: compute
      `vehicleTypeOptions` from the resolved `vehicle_type` field's
      `options`

## 6. Frontend: Replace Hardcoded Option Lists

- [x] 6.1 `VisitorFieldsForm.tsx`: remove the local `ID_PROOF_OPTIONS`
      const; build the `SelectField`'s options from
      `visitorInfoFields.idProofOptions`
- [x] 6.2 `staff-visitor-registration/Components/constants.ts`: remove the
      exported `ID_PROOF_OPTIONS`; update `AddVisitorForm.tsx` and
      `PrimaryContactCard.tsx` to build options from
      `visitorInfoFields.idProofOptions` (already received as a prop)
      instead of importing the removed constant
- [x] 6.3 `VehicleInfoStep.tsx`: remove the module-level
      `VEHICLE_TYPE_OPTIONS` const; use `vehicleInfoFields.vehicleTypeOptions`
      for both the input's options and the review-table label lookup (or
      display the raw value directly, per design.md Decision 5)
- [x] 6.4 Update any other display-only reference to the old hardcoded
      label tables (e.g. `ReviewConfirmStep.tsx`, `VisitorDetailsTable.tsx`,
      `VisitorInfoModal.tsx`) to render the stored value directly — checked
      all three; each already displays `visitor.idProofType` as the raw
      stored string with no label-lookup table, so no change was needed

## 7. Documentation

- [x] 7.1 Update `docs/features/form_builder.md`: note that "ID Proof
      Type" and "Vehicle Type" options are now load-bearing (validated
      against on submission), not decorative, and that they're no longer
      exempt from the non-empty-options-to-publish rule
- [x] 7.2 Update the relevant `docs/features/invitations.md` (or
      equivalent) section documenting `idProofType`/`vehicleType` as
      branch-configured values rather than a fixed enum, if such a
      reference exists

## 8. Manual Verification

- [ ] ~~8.1 Manual verification (no frontend test framework in this repo,
      pre-existing gap): confirm in a running instance that (a) adding a
      new ID Proof Type option in Form Builder and publishing makes it
      selectable on both the visitor and staff wizards, (b) the same for
      Vehicle Type, and (c) a visitor/staff submission using a removed
      option is rejected~~ — deferred, same as every prior form-builder
      change: no browser tooling in this sandbox. `tsc -b` and `oxlint`
      both pass clean across the whole frontend project, and the pytest
      suite (13 new/confirmed tests) exercises the exact same
      `resolve_effective_form`/dynamic-validation code path both wizards'
      hooks now read from. Flagged to the user to spot-check visually
      before shipping.
