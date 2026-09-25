## 1. Backend: Narrow the Field-Type Change Gate

- [x] 1.1 Add a `TYPE_LOCKED_SYSTEM_FIELD_KEYS` constant to
      `src/vmss_api/form_builder/service.py` (or a shared constants
      module) containing: `registration_type`, `email`, `phone`,
      `preferred_contact_method`, `visitor_category`,
      `id_proof_upload`, `profile_photo`, `preferred_visit_date`,
      `preferred_visit_time`.
- [x] 1.2 In `update_field`, replace the unconditional
      `field_row.is_system` rejection of a `field_type` change with a
      check against `TYPE_LOCKED_SYSTEM_FIELD_KEYS` (matched on
      `field_row.key`), applied to every field (`is_system` or not —
      admin-authored fields were never in the exclusion list, so this is
      a strict loosening, not a behavior change for them).
- [x] 1.3 For a `field_type` change that passes the exclusion check,
      confirm the existing resulting-state re-validation
      (`fix-field-type-editing-and-lock-ux`'s logic: option-required type
      needs non-empty options, `static_text` can't be required/needs
      `help_text`, options cleared when leaving an option-bearing type)
      already applies unconditionally regardless of `is_system` — extend
      it if it's currently gated on `not is_system`.
      **Confirmed**: `resulting_needs_options`/`field_type_changing`
      logic (`service.py::update_field`) was already unconditional, not
      gated on `is_system` — no change needed.
- [x] 1.4 Confirm Required/Active enforcement for locked fields
      (`isActive`/`isRequired` → `false` rejection) is untouched by this
      change — no task expected here, this is a regression check.
      **Confirmed**: that check is keyed on `field_row.is_locked`, a
      separate code path from the `field_type` gate this change edited.

## 2. Backend: Generalize Dynamic Option Validation

- [x] 2.1 In `src/vmss_api/form_builder/validation.py`, generalize
      `allowed_id_proof_types`/`allowed_vehicle_types` into
      `allowed_options_for_system_field(effective_form, field_key) ->
      list[str] | None`, returning the field's current `options` when its
      configured type is `dropdown_select`/`checkbox_list`, `None`
      otherwise. Keep (or re-point) `allowed_id_proof_types`/
      `allowed_vehicle_types` as thin wrappers so existing call sites and
      tests keep working.
      **Note**: their return type changed from `set[str]` to
      `set[str] | None` (not preserved as originally suggested) — this
      was necessary for correctness: once `id_proof_type`/`vehicle_type`
      can themselves be retyped away from `dropdown_select`, the old
      always-a-set contract couldn't distinguish "not option-bearing,
      accept anything" from "option-bearing with zero configured
      options, accept nothing". Both call sites in
      `invitations/service.py` were updated accordingly.
- [x] 2.2 In `src/vmss_api/invitations/service.py`, extend the
      submission-time validation loop to call
      `allowed_options_for_system_field` for `full_name`,
      `purpose_of_visit`, `department_to_visit`, `license_plate`,
      `expected_duration`, `additional_notes` (in addition to the
      existing `id_proof_type`/`vehicle_type` calls); when it returns a
      list, reject the submission (422) if the submitted value isn't a
      member; when it returns `None`, apply the existing free-text
      validation unchanged. **`host` deliberately excluded** — its
      submitted value (`VisitDetailsSubmit.host_name_or_email`) is always
      discarded by `_resolve_visit_detail_ids`
      (role-based-invitation-workflow), so there is nothing to validate.
- [x] 2.3 Implement 2.2 as one loop over a
      `(field_key, submitted_value)` list rather than seven near-duplicate
      `if` blocks (per design.md's risk mitigation).

## 3. Frontend: Field Type Editability in the Field Properties Panel

- [x] 3.1 Add a `TYPE_LOCKED_SYSTEM_FIELD_KEYS` constant to
      `VMMS_WEB` (e.g. alongside `field-type-catalog.ts`), mirroring the
      backend's list exactly.
- [x] 3.2 `FieldPropertiesPanel.tsx`: change the Field Type
      `SelectField`'s `disabled` condition from `field.isSystem` to
      `TYPE_LOCKED_SYSTEM_FIELD_KEYS.has(field.key) || (field.isLocked &&
      !isUnlockedForEditing)`.
- [x] 3.3 Include the draft `fieldType` value in the set of fields the
      unlock toggle resets/discards on re-lock or field switch, alongside
      the existing label/placeholder/description/options draft state.
      **Confirmed already covered**: `fix-field-type-editing-and-lock-ux`
      already added `fieldType` to both the `field.id`-keyed `useEffect`
      and `reset()` (which `relock()` calls) — no change needed.
- [x] 3.4 Confirm the panel's live-recompute of `showOptionsEditor`/
      `isContentOnly` from the draft `fieldType` (already added by
      `fix-field-type-editing-and-lock-ux`) behaves correctly when the
      draft type change originates from a newly-unlocked locked field,
      not just an admin-authored field.
      **Confirmed**: both are derived from the generic `fieldType` state
      with no admin-authored-only branching — behaves identically
      regardless of which kind of field is selected.

## 4. Frontend: Field-Specific Disabled Explanation

- [x] 4.1 `FieldPropertiesPanel.tsx`: replace the single generic
      "This is a default system field, so its type can't be changed."
      message with per-key explanatory copy for each
      `TYPE_LOCKED_SYSTEM_FIELD_KEYS` entry (e.g. email/phone: "This
      field's value must stay a valid contact address for notifications
      to reach the visitor."; date/time: "This field's value is used as
      a real date/time for overstay detection and the emergency
      report."; uploads: "This field's value is a stored file, not form
      input."; `visitor_category`: "This field's options come from the
      Visitor Categories catalog, not this list."; `registration_type`:
      "This field determines how the invitation is processed and
      filtered."). No explanatory text renders for a retypeable system
      field (locked or toggleable) at all.

## 5. Backend Tests

- [x] 5.1 `pytest`: changing `field_type` for each retypeable system
      field (`full_name`, `purpose_of_visit`, `host`,
      `department_to_visit`, `license_plate`, `expected_duration`,
      `additional_notes`, `id_proof_type`, `vehicle_type`) succeeds.
      Implemented as two representative tests (a locked field: `full_name`;
      a toggleable field: `additional_notes`) plus the existing
      dropdown/options-focused tests using `purpose_of_visit` — the
      `update_field` code path is identical for every key not in the
      exclusion set, so these aren't testing nine independent branches.
- [x] 5.2 `pytest`: changing `field_type` for each excluded field
      (`registration_type`, `email`, `phone`, `preferred_contact_method`,
      `visitor_category`, `id_proof_upload`, `profile_photo`,
      `preferred_visit_date`, `preferred_visit_time`) is rejected (422)
      and the field's type is unchanged. Implemented as one parametrized
      test covering all nine keys.
- [x] 5.3 `pytest`: changing a retypeable system field's type to an
      option-required type without options is rejected; supplying options
      in the same request succeeds.
- [x] 5.4 `pytest`: changing an existing admin-authored field's type
      still works exactly as before (regression check —
      `TYPE_LOCKED_SYSTEM_FIELD_KEYS` never matches a non-system field).
      Already covered by the pre-existing `test_custom_field_type_can_be_changed`
      — unaffected by this change's edits, re-verified passing.
- [x] 5.5 `pytest` (`invitations/tests.py`): submitting a value for a
      retyped, option-bearing system field that matches the configured
      options succeeds; a non-matching value is rejected with a 422.
- [x] 5.6 `pytest`: submitting a value for a system field still in its
      default (non-option-bearing) type is validated as free text,
      unchanged from today.
- [x] 5.7 `pytest`: publishing a retyped system field's config is
      reflected in `GET /form-builder/effective`.
- [x] 5.8 Tenant-isolation case (`testing-standards.md` §2): a
      field-type change made under one tenant's schema does not affect
      another tenant's default/branch config for the same system field
      key.

## 6. Documentation

- [x] 6.1 Update `docs/features/form_builder.md`'s "Changing an existing
      field's type" section to describe the exclusion list (by key, with
      rationale) instead of "every system field, locked or toggleable,
      stays fixed." Also updated "Unlocking a locked field to edit it"
      (Field Type now joins the unlock-gated set) and the endpoints table
      row for `PATCH /form-builder/fields/{id}`.
- [x] 6.2 Update `docs/features/invitations.md` to document that
      `full_name`, `purpose_of_visit`, `department_to_visit`,
      `license_plate`, `expected_duration`, `additional_notes` are now
      validated against the branch's currently configured options when
      their Form Builder type is option-bearing (`host` excluded — see
      task 2.2's note).

## 7. Manual Verification

- [ ] ~~7.1 Manual verification (no frontend test framework in this repo,
      pre-existing gap): confirm in a running instance that (a) a locked,
      retypeable field's Field Type control stays disabled until
      unlocked, then becomes editable; (b) a toggleable retypeable field's
      Field Type control is editable directly; (c) each excluded field's
      Field Type control stays disabled with its specific explanatory
      text regardless of lock state; (d) a retyped field's new type is
      reflected on both the visitor and staff registration wizards after
      publish.~~ — deferred, same as every prior form-builder change: this
      sandbox has no browser tooling to drive `VMMS_WEB` against a
      running `VMSS_API` instance. `tsc -b` and `oxlint` both pass clean
      on every touched file, and the backend pytest suite (94 tests
      across `form_builder`/`invitations`/`registrations`, all passing)
      covers the underlying `update_field`/submission-validation behavior
      the browser would exercise. Flagged to the user to spot-check
      visually before shipping.
