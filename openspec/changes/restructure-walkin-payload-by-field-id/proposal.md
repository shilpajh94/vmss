## Why

`POST /registrations/walk-in` (and `POST /invitations`, whose contract it
reuses byte-for-byte per `registrations/spec.md`) captures every
admin-authored form-builder answer — `customFieldValues` (visitor,
primary-contact, vehicle, and invitation-level), `consents`, and
`groupValues` — as a `dict[str, Any]`/`dict[str, bool]` keyed by the
`FormField`/`FormFieldGroup`'s **`key`** string
(`invitations/schemas.py:104,174,191,244,252,262`), and
`form_builder/validation.py` resolves a submitted value back to its field
definition the same way (`fields_by_key = {field["key"]: field ...}`,
`validate_custom_field_values`).

`FormField.id`/`FormFieldGroup.id` already exist as stable UUID primary
keys, but nothing in the submission path uses them — `key` is the only join
between a submitted value and its live field definition. That's a fragile
foundation for an EAV-shaped payload whose whole point is that fields are
admin-defined and change over time: the wire contract, storage shape, and
validation logic should be built around the identifier that's actually
guaranteed stable (`id`), not the one that merely happens not to be editable
today. (Note: as implemented, `FormFieldUpdate`/`FormFieldGroupUpdate`
don't currently expose a way to rename `key` after creation — so today's
key-based join isn't actually broken by a live renaming bug. This change is
a deliberate hardening of the join contract before that assumption becomes
load-bearing, not a fix for an observed incident.)

This also collapses two different EAV mechanisms — `customFieldValues`
(admin-authored fields) and `consents` (which are themselves ordinary
`FormField` rows on the locked Consent Agreement step, per
`form_builder/validation.py::allowed_consent_keys`/`required_consent_keys`)
— onto one consistent shape and one join key, instead of the same
underlying concept being keyed two different ways depending on which step
the field happens to live on.

## What Changes

- **BREAKING** (nested payload shape only — `registrationType`,
  `primaryContact`, `visitors`, `visitDetails`, `carriedItems`, `vehicles`,
  `consents`, `customFieldValues`, `groupValues` all remain present as
  top-level/nested keys, matching the precedent set by the parent
  `form-builder` change's own "data shape only, not the wire contract's
  outer keys" breaking change):
  - `customFieldValues` (on `InvitationCreate`, `InvitationPrimaryContactCreate`,
    `VisitorSubmit`, `VehicleSubmit`) changes from `dict[key, value]` to
    `customFields: list[{fieldId: UUID, value}]` — validated by looking the
    `fieldId` up directly against the resolved branch's live `form_fields`
    (via the cached effective-form snapshot, unchanged mechanism otherwise),
    never by re-deriving or trusting a key.
  - `consents` changes from `dict[consentKey, bool]` to
    `consents: list[{fieldId: UUID, accepted: bool}]`, joined against the
    Consent Agreement step's fields by `fieldId` the same way, replacing
    `allowed_consent_keys`/`required_consent_keys`'s key-set logic with an
    id-set equivalent.
  - `groupValues` changes from `dict[groupKey, list[dict[fieldKey, value]]]`
    to `groups: list[{groupId: UUID, instances: list[list[{fieldId, value}]]}]`
    — both the group and its member fields are now referenced by id, not key,
    for the same reason.
  - Locked/system fields (`fullName`, `email`, `phone`,
    `preferredContactMethod`, `idProofType`, `purposeOfVisit`,
    `preferredVisitDate`/`Time`, `departmentToVisit`, `vehicleType`,
    `licensePlate`, the `registrationType` discriminator itself, etc.) are
    **unchanged** — they stay hardcoded, named Pydantic fields exactly as
    today. Nothing about this change touches how a locked/system field is
    submitted or validated; only the admin-authored (`isSystem: false`)
    field/consent/group EAV maps switch their join key.
  - Response schemas (`InvitationOut` and every nested `*CustomFieldValues`
    field returned by creation/detail/tracking/check-in/check-out/list) move
    to the same `list[{fieldId, value}]` shape, so a client can resolve a
    returned value against the same form-builder field catalog it used to
    render the form, without re-deriving a key.
- `form_builder/validation.py`'s field/group/consent lookup helpers
  (`_find_field_by_key`, `custom_fields_for_step`,
  `custom_fields_for_invitation_scope`, `custom_groups_for_invitation_scope`,
  `custom_groups_for_step`, `allowed_consent_keys`, `required_consent_keys`,
  `validate_custom_field_values`) are rewritten to resolve by `id`, keeping
  their existing branch-scoped, effective-form-snapshot-driven behavior
  otherwise unchanged (still Redis-cached, still reads the published
  `FormConfigVersion.snapshot`, not a live table read per request).
- `invitations/router.py`'s file-upload value resolution
  (`_resolve_custom_field_file_values`, the function whose docstring already
  says it rewrites "a `customFieldValues`-shaped map") is updated to resolve
  `file_upload`-typed answers by `fieldId` instead of key.
- Storage: `Invitation.custom_field_values`,
  `Invitation.primary_contact_custom_field_values`, `Invitation.consents`,
  `InvitationVisitor.custom_field_values`, `InvitationVehicle.custom_field_values`
  stay `JSONB` columns (no schema migration needed) but their keys become
  field/group id strings instead of key strings going forward. A one-time
  tenant-schema data migration (per `database-architecture.md` §5's
  `alembic_tenant/` tree) best-effort translates each existing row's
  key-keyed JSONB to id-keyed JSONB using the *current* live
  `form_fields`/`form_field_groups` key→id mapping at migration time; a
  stored key with no matching live field (deleted since submission) is left
  under its original key, un-migrated, and flagged in the migration's log
  output rather than silently dropped.
- `docs/features/registrations.md` and `docs/features/invitations.md`
  (`api-documentation.md` §2/`git-workflow.md` §3) are updated for the new
  payload shape, and `POST /invitations`'s self-documenting `payload` field
  description (`invitations/spec.md` "Self-Documenting Without Try It Out")
  is regenerated to match.
- Out of scope: `carriedItems.items` (a list of one system field's own
  `options` values, not a reference to *other* fields) and the
  `idProofType`/`vehicleType` retyped-system-field option checks stay
  string-value-based — those aren't a field-to-field join and don't have
  the key-vs-id problem this change addresses.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `registrations`: "Walk-in registration accepts the same visit-record
  contract as staff pre-registration" is updated to describe the
  `customFields`/`consents`/`groups` id-keyed shape instead of the old
  key-keyed `customFieldValues`/`consents`/`groupValues` shape.
- `invitations`: every requirement whose scenarios reference
  `customFieldValues`, `consents`, or `groupValues` by key (Consent Is
  Mandatory and Recorded; Carried Items and Vehicles Are Optional Structured
  Declarations' custom-field angle; the generic custom-field/repeatable-
  group capture requirements from `add-generic-custom-field-support` and
  `add-repeatable-field-groups`) is updated to the id-keyed shape and to
  reject an unresolvable `fieldId`/`groupId` (unknown, inactive, or
  belonging to a different step/branch) the way an unknown key is rejected
  today.

## Impact

- Code: `src/vmss_api/invitations/{schemas,service,router,models}.py`,
  `src/vmss_api/registrations/{schemas,service,router}.py` (contract
  re-export/pass-through only — it owns no schema of its own),
  `src/vmss_api/form_builder/validation.py`.
- Data: one Alembic tenant-schema migration (`alembic_tenant/versions/`) to
  backfill existing JSONB rows; applied per tenant the same way every other
  tenant migration is (`platform/service.py`'s provisioning path /
  `database-architecture.md` §5).
- Tests: `src/vmss_api/registrations/tests.py` and
  `src/vmss_api/invitations/tests.py` — every test asserting
  key-keyed `customFieldValues`/`consents`/`groupValues` (including
  `test_walk_in_registration_custom_field_unknown_key_rejected`) needs
  updating to the id-keyed shape; new tests for unresolvable
  `fieldId`/`groupId` rejection.
- Clients: React portal and Flutter app (separate repos) both submit and
  render this payload shape and need a coordinated update — flagged per
  `api-conventions.md` §2, following the same in-place-`v1`-breaking-change
  precedent the parent `form-builder` change already established for this
  product's pre-stabilization phase, rather than a `/api/v2` bump.
