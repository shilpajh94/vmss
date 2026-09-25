## Why

An admin opening the Field Properties panel for a system-seeded field
(e.g. "ID Proof Type", shown as a `Dropdown Select` with the message "This
is a default system field, so its type can't be changed") has no path to
retype it, even after unlocking the field's other properties. That
blanket rule (`fix-field-type-editing-and-lock-ux`) was deliberately
conservative — system fields are "keyed into fixed, structural application
code and database columns that a type switch cannot safely repoint" — but
that's only actually true for a subset of them. Most seeded system fields
(Full Name, Purpose of Visit, Host, Department to Visit, License Plate,
Expected Duration, Additional Notes, ID Proof Type, Vehicle Type) are
plain, unconstrained string columns with no cross-cutting backend
consumer that depends on their value having a specific shape. The
business now needs admins to be able to retype these — the same way they
can already reword their label or edit their options — without deleting
and recreating them and losing their key, order position, and any
already-submitted answers' association.

## What Changes

- A system field's `field_type` becomes editable through the Field
  Properties panel for every system field **except** a fixed exclusion
  list of fields whose value is consumed elsewhere in the backend as a
  specific structured type, not just rendered on a form:
  - `email`, `phone`, `preferred_contact_method` — coupled together by
    `_require_reachable_contact`/`_require_contact_for_method`
    (`invitations/schemas.py`) and consumed as a real deliverable address/
    channel by notification dispatch; a value that isn't an actual email/
    phone breaks message delivery, not just form validation.
  - `registration_type` — a real `RegistrationType` enum, DB filter
    column (`invitations/repository.py::list_invitations`), and drives
    `_check_visitor_list_matches_registration_type`'s conditional
    validation.
  - `preferred_visit_date`, `preferred_visit_time` — real `Date`/`Time`
    (not `String`) DB columns, consumed as true date/time values by
    overstay detection and the emergency "who's inside" report.
  - `id_proof_upload`, `profile_photo` — `file_upload` fields feeding the
    document/photo storage and PII-handling pipeline
    (`security-architecture.md` §4, `file-upload-handling.md`); their
    value is a stored file reference, not form input.
  - `visitor_category` — already exempted from the "must declare
    options" rule because its real options come from the separate
    Visitor Category catalog, not this field's own `options` list
    (`make-id-proof-and-vehicle-type-configurable`); retyping it away
    from a catalog-driven selector doesn't have a coherent meaning.

  For every other system field — `full_name`, `purpose_of_visit`, `host`,
  `department_to_visit`, `license_plate`, `expected_duration`,
  `additional_notes`, `id_proof_type`, `vehicle_type` — `field_type`
  becomes a genuinely editable property, re-validated against the same
  type-dependent constraints (`OPTION_REQUIRED_TYPES` needs non-empty
  `options`, `static_text` can't be required) that
  `fix-field-type-editing-and-lock-ux` already applies to admin-authored
  fields.
- For a **locked** system field, `field_type` joins the set of controls
  gated behind "Unlock to Edit" (`add-static-text-field-and-unlock-toggle`)
  — it stays disabled until the admin explicitly unlocks the field, the
  same as its Label/Placeholder/Description/Options. For a **toggleable**
  (not locked) system field, it's editable directly, matching how those
  fields' other properties already work without an unlock step. Required
  and Active are unaffected by any of this and stay fixed for every
  system field regardless of lock state — this change is scoped to
  `field_type` and the field's other values, not to whether a mandatory
  field can be made optional or inactive.
- Submission-time validation for the newly-retypeable system fields
  becomes dynamic against the field's **currently configured** type,
  mirroring the mechanism `make-id-proof-and-vehicle-type-configurable`
  already built for `id_proof_type`/`vehicle_type`: when the configured
  type is option-bearing (`dropdown_select`/`checkbox_list`), the
  submitted value must match one of the branch's currently published
  options; when it isn't, ordinary free-text validation applies (as
  today). Without this, changing e.g. Purpose of Visit to a dropdown
  would only be a cosmetic form-rendering change — the backend would keep
  accepting any string.
- The Field Properties panel's disabled-Field-Type explanation
  (`clarify-system-field-type-restriction`) narrows to only the exclusion
  list above, and its copy becomes specific to *why* — "this field's
  value must stay a valid email/phone for notifications to reach the
  visitor," "this field's value is stored as an uploaded file," etc. —
  instead of one generic "default system field" message covering every
  system field indiscriminately.

## Capabilities

### New Capabilities

(none — this continues refining the existing `form-builder` and
`invitations` capabilities)

### Modified Capabilities

- `form-builder`: narrows the "a system field's type is permanently
  fixed" rule to a specific, rationale-backed exclusion list instead of
  every `isSystem` field; gates the remaining system fields' `field_type`
  editability behind the existing lock/unlock affordance (locked fields)
  or leaves it directly editable (toggleable fields), consistent with how
  their other properties already behave; updates the disabled-Field-Type
  explanatory text to be field-specific.
- `invitations`: submission-time validation for the system fields this
  change makes retypeable becomes dynamic against the field's currently
  configured type/options instead of unconstrained free text, mirroring
  the existing `id_proof_type`/`vehicle_type` mechanism.

## Impact

- **Backend (`VMSS_API`)**:
  - `src/vmss_api/form_builder/service.py::update_field` — replace the
    unconditional `field_row.is_system` rejection of a `field_type`
    change with a check against a `TYPE_LOCKED_SYSTEM_FIELD_KEYS`
    constant (the exclusion list above, keyed by field `key`, not just
    `is_system`). The backend does not separately enforce a locked
    field's "unlocked for editing" state for `field_type`, consistent
    with the existing pattern: the backend has never rejected a locked
    field's label/placeholder/`helpText`/options change either — "unlock"
    is a client-side UX guard against accidental edits
    (`add-static-text-field-and-unlock-toggle`), not a backend permission
    boundary, and `field_type` joins that same UI-only gate rather than
    getting a new, inconsistent server-side one.
  - `src/vmss_api/form_builder/validation.py` — generalize the
    `allowed_id_proof_types`/`allowed_vehicle_types` pattern into a
    keyed-by-field-key helper (e.g. `allowed_options_for_system_field`)
    covering every newly-retypeable, option-bearing system field, not
    just those two.
  - `src/vmss_api/invitations/service.py` — validate `full_name`,
    `purpose_of_visit`, `department_to_visit`, `license_plate`,
    `expected_duration`, `additional_notes` against the resolved
    effective form's configured type/options for that field key when
    it's option-bearing, mirroring the existing `id_proof_type`/
    `vehicle_type` 422 pattern. `host` is excluded — its submitted value
    is always discarded before persistence, so there is nothing to
    validate.
  - No database migration: every newly-retypeable field's underlying
    column is already a plain `String`, and the exclusion list keeps
    every genuinely non-`String`-backed or cross-cutting-typed column
    (`Date`, `Time`, `EmailStr`, `RegistrationType` enum) off the table.
  - `docs/features/form_builder.md` ("Changing an existing field's type",
    "Unlocking a locked field to edit it") and `docs/features/
    invitations.md` — document the narrowed exclusion list and the
    dynamic-validation extension.
- **Frontend (`VMMS_WEB`)**:
  - `src/presentation/pages/admin-form-builder/Components/
    FieldPropertiesPanel.tsx` — Field Type `SelectField`'s `disabled`
    condition changes from `field.isSystem` to "key is in the exclusion
    list, OR (`isLocked` and not yet unlocked for editing)"; include
    `fieldType` in the set of draft values the unlock toggle gates for a
    locked field; update the disabled-state explanatory text to be
    field-specific.
  - A shared constant mirroring the backend's exclusion list (or a field
    returned by `GET /form-builder/effective`/steps-with-fields
    indicating whether a given system field's type is fixed) so the
    frontend doesn't re-derive the list independently and drift from the
    backend's enforcement.
- **Tests**: new backend `pytest` coverage in `form_builder/tests.py`
  (field-type change accepted for each newly-retypeable system field,
  rejected for each excluded field, locked-field type change rejected
  until unlocked-equivalent payload is sent, toggleable system field type
  change accepted directly) and `invitations/tests.py` (submission
  accepted/rejected against a retyped system field's configured options).
  Frontend has no test framework in this repo (pre-existing gap) —
  covered by manual verification, as with every prior form-builder
  change.
