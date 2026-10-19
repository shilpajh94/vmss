# Form Builder

Admin-configurable registration steps and fields — branch-scoped, with a
tenant-wide default fallback — behind a draft/publish lifecycle. See
`openspec/changes/form-builder/` for the full proposal/spec/design this
feature was built from.

## Why

Today's invitation/registration form (visitor info, visit details, carried
items, vehicle info, consents) is hardcoded per tenant. This lets an admin
customize what's collected — required-ness, allowed options, admin-defined
custom fields, conditional visibility — without a code change.

## Model

- **`FormStep`** — a registration step (`key`, `name`, `description`,
  `icon`, `isSystem`, `isLocked`, `isActive`, `orderIndex`). `branchId` is
  the scope: a specific branch, or `null` for the tenant-wide default.
- **`FormField`** — one field within a step (`key`, `label`, `placeholder`,
  `helpText`, `fieldType`, `isSystem`, `isLocked`, `isActive`,
  `isRequired`, `options`, `validationRules`, `visibilityCondition`,
  `width`, `hideLabel`, `orderIndex`). `hideLabel` (default `false`) is a
  display-only flag: `label` is still mandatory and still used as the
  field's accessible name and in validation error messages, but when
  `hideLabel` is `true` the visitor-facing renderer omits the visible
  label text — the same posture as `width`, not consulted by submission
  validation at all.
- **`FormConfigVersion`** — the *published* snapshot for one scope
  (`branchId` nullable), overwritten in place on every publish. No version
  history is kept in this iteration — publishing atomically replaces the
  previously-live configuration.

`FormStep`/`FormField` are the admin's mutable **draft** — every create/
update/delete/reorder call only ever touches these rows. They have no
effect on live invitation/registration submission or the public/staff
renderer until `POST /form-builder/publish` re-validates the whole draft
and serializes it into that scope's `FormConfigVersion`.

## Step icons (`auto-assign-form-step-icons`)

A step's `icon` is a slug from a fixed vocabulary
(`form_builder/step_icons.py::STEP_ICON_VOCABULARY`) that every client maps
to its own glyph:

`user`, `calendar`, `briefcase`, `package`, `car`, `shield-check`,
`check-circle`, `file-text`, `file-signature`, `id-card`, `camera`,
`heart-pulse`, `laptop`, `phone`, `building`, `users`, `clock`, `map-pin`,
`alert-triangle`, `clipboard-list` (the neutral default).

- **Create** — `icon` is optional. Omitted (or `null`/empty), the server
  infers one from the step name by keyword (case-insensitive; whole-word
  or word-prefix match, first rule wins): "Vehicle Info" → `car`, "NDA
  Signing" → `file-signature`, "Health Declaration" → `heart-pulse`. No
  match → `clipboard-list`. The admin UI never sends an icon, so this is
  how every custom step gets one.
- **Rename** — a `PATCH` that changes `name` without sending `icon`
  re-infers the icon only if the current one is what the *old* name would
  have inferred (i.e. it was auto-assigned). An icon that differs was
  chosen explicitly and is kept.
- **Reads** — a step stored with a null icon (created before this change)
  is served with the inferred icon from every step endpoint and from
  `/effective`, including old published snapshots. No migration.
- An explicit `icon` outside the vocabulary is still accepted (tightening
  it would break existing clients); clients render a neutral glyph for an
  unknown slug. Adding a slug to the vocabulary means adding a glyph to
  `VMMS_WEB`'s `admin-form-builder/step-icons.ts` (and Flutter, if it
  renders step icons).

## The six canonical steps and field tiers

Every tenant starts with six steps, in order: **Visitor Info**, **Visit
Details**, **Carried Items**, **Vehicle Info**, **Consent Agreement**,
**Review & Confirm**. Visitor Info, Visit Details, and Review & Confirm are
**locked** — they can never be deactivated or removed; the other three can
be toggled off or deleted, and an admin may also add entirely new custom
steps.

Within a step, each field is one of three tiers:

- **Locked** (`isLocked=true`): always active and required; the field
  endpoint rejects any attempt to change either. E.g. full name, email,
  phone, visitor category (Visitor Info); purpose of visit,
  preferred date/time (Visit Details); vehicle type, license plate
  (Vehicle Info).
- **Toggleable**: an admin may activate/deactivate and (for an option-set
  field like registration type or preferred contact method) choose which
  options are offered. E.g. ID proof, profile photo (Visitor Info);
  expected duration, additional notes (Visit Details).
- **Fully configurable**: every step — including Visitor Info and Visit
  Details, alongside their own locked/toggleable seeded fields — accepts an
  admin-authored field added on top, via the same "Add New Custom Field"
  flow for every field type (`add-generic-custom-field-support`). Carried
  Items, Vehicle Info's non-locked fields, Consent Agreement, and any
  custom step have no fixed field set of their own at all.

Every step accepts a *new* field — `POST .../fields` no longer rejects a
creation request targeting Visitor Info or Visit Details. That restriction
existed for one release (`fix-form-builder-step-order-and-ui-gaps`) because
those two steps rendered fixed JSX by known field keys with no
value-storage/rendering path for anything else; both now exist (see
"Custom-field answer storage" below), so the restriction was reversed
rather than kept as dead validation. Updating an *existing* seeded field
(toggling a toggleable field's active/required state) is unaffected either
way.

`defaults.py` is the single source of truth for this seed — both what
materializes a scope's draft on first touch, and the in-code fallback
(`DEFAULT_EFFECTIVE_FORM`) returned when nothing has been published yet, so
a tenant/branch that never opens Form Builder still gets sensible,
pre-`form-builder` behavior with zero admin action required.

## Field groups

A step's fields can be organized into named **`FormFieldGroup`**s
(`key`, `name`, `isSystem`, `isLocked`, `isRepeatable`, `minInstances`,
`maxInstances`, `orderIndex`) — an ungrouped field (`FormField.groupId =
null`) still renders/submits as a flat step-level field, unchanged from
before groups existed. A group marked `isRepeatable` lets the visitor-
facing form submit `minInstances`..`maxInstances` independent copies of
the group's fields (either bound `null` = unset, meaning no floor/ceiling)
— e.g. an admin-authored "Parcels" group on Carried Items with a "Weight"
field, letting a visitor declare several parcels each with their own
weight, the same way Vehicle Info already lets a visitor add several
vehicles.

Vehicle Info's vehicle fields and Visitor Info's co-visitor fields are
each seeded as a single, locked, repeatable group (`vehicles`/`visitors`)
— generalizing what used to be two separate hardcoded "add another"
implementations onto this one mechanism. Vehicle Info's group behaves like
any other repeatable group (admin-configurable `minInstances`/
`maxInstances`, enforced on invitation/registration submission). Visitor
Info's group's cardinality *floor* is governed exclusively by the
existing `registrationType` rule (individual = no co-visitors, group =
one or more); it exposes no admin-editable `minInstances`/`maxInstances`
controls at all — a second, independent range on the same group would
conflict with that rule. Its *ceiling*, however, is enforced through this
same group's `maxInstances`, seeded at migration/provisioning time from
`INVITATION_MAX_GROUP_VISITORS` (previously a standalone, undocumented
settings check in `invitations/service.py` — now retired in favor of this
one group-instance-count mechanism, the same path Vehicle Info's ceiling
already went through). Changing that ceiling today requires a data
migration or manual DB update per branch, not an admin UI action or an
env-var change — a deliberate trade-off for having a single source of
truth (see `openspec/changes/add-repeatable-field-groups/design.md`'s
revised Decision 5).

A group's `key` is unique across a branch's entire active form, the same
uniqueness scope a field's `key` already has, since a submission addresses
a group's instances by key without a step qualifier. Vehicle Info's and
Visitor Info's own vehicle/vehicle-plate-etc. and visitor answers keep
their existing dedicated storage (`InvitationVehicle`/`InvitationVisitor`
— see `docs/features/invitations.md`); every other repeatable group's
per-instance answers round-trip through `Invitation.groupFieldValues`, an
ordered list of answer maps per group key.

### Conditional groups

A group may also declare `visibilityCondition`
(`{fieldKey, operator, value}`, `operator` one of `equals`/`not_equals`)
— the same shape a field's own condition already uses — referencing
another field on the *same step*. The group, and every field inside it,
is shown only when that condition holds; independent of `isRepeatable`, a
group can be conditional only, repeatable only, both, or neither. A
group's condition cannot reference one of its own member fields (a
group-level self-reference), mirroring a field's own self-reference
rejection — but unlike a field's condition, a group's never needs a
transitive-cycle check, since nothing can reference a *group's* condition
in the first place (only a `fieldKey` is ever a watchable target).

When a group is hidden by its condition, none of its fields are treated
as required for that submission — regardless of each field's own
`isRequired` flag — and a repeatable hidden group's configured minimum
instance count isn't enforced either (a visitor who was never shown the
group can't be expected to have filled it in; its maximum still applies
if instances were submitted anyway). This is genuinely new evaluation
logic, and it's scoped to groups only: a plain field's own
`visibilityCondition` is still checked only at authoring time (dangling
reference / cycle prevention) — it is not evaluated against submitted
values to skip that field's own required-check. A field with both
`isRequired` and its own `visibilityCondition`, hidden or not, still
blocks submission if empty, unless that field also happens to belong to a
hidden group.

## Field types

`text`, `email`, `phone`, `number`, `dropdown_select`, `date_picker`,
`time_picker`, `toggle_switch`, `checkbox_list`, `checkbox_single`,
`radio_button`, `file_upload`, `textarea`, `static_text`.
`dropdown_select`, `checkbox_list`, and `radio_button` must declare a
non-empty `options` list; `checkbox_single` is a lone boolean field and
declares none, the same as an option-free `toggle_switch`.
`visitor_category` is the sole exception: its real options come from
the separate, admin-managed Visitor Categories catalog, not this row's own
`options`, so it's exempt from the non-empty-options rule
(`_EXTERNALLY_CATALOGED_FIELD_KEYS` in `form_builder/service.py`). Every
other system-seeded dropdown field — including `id_proof_type` and
`vehicle_type` (`make-id-proof-and-vehicle-type-configurable`) — has no
such external catalog: its `options` **is** the source of truth for what a
visitor/staff submission may declare for that field, validated dynamically
in `invitations/service.py::create_invitation`
(`allowed_id_proof_types`/`allowed_vehicle_types`), so it needs the same
non-empty-options guarantee any admin-authored dropdown has. A field may
declare `visibilityCondition` (`{fieldKey, operator, value}`,
`operator` one of `equals`/`not_equals`) referencing another field in the
*same* step; a dangling reference or a dependency cycle is rejected both at
field-save time and again at publish time.

`static_text` is a display-only content block, not an input: its `label`
renders as a heading and its `helpText` as the full body beneath it (e.g.
an actual Terms & Conditions statement authored by the admin), on both the
staff and visitor forms. It collects no answer, so it can never be marked
required — `FormFieldCreate`/`update_field` reject `isRequired=true` for
this type — and it must declare non-empty `helpText` at creation (a
heading with no body serves no purpose).

## Field description, and editing options after creation

A field's `helpText` is admin-authored static text shown to the visitor
alongside the field itself — e.g. the actual body of a "Terms &
Conditions" or "Data Processing Consent" statement on the Consent
Agreement step — not a value the visitor fills in. It's settable for any
field type from both the "Add New Custom Field" modal (at creation) and
the Field Properties panel (after creation), the latter disabled for a
locked field unless the admin has unlocked it for editing (see "Unlocking
a locked field to edit it" below), matching that field's label/placeholder
inputs. The public/staff renderer (`DynamicField`) shows it under the
field's own control, truncated to its first sentence with a "See
more"/"See less" toggle, for every field type and step uniformly — for a
`static_text` field, which has no input control of its own, this is the
block's entire body content.

`checkbox_list`, `dropdown_select`, `radio_button`, and an optioned
`toggle_switch` field's `options` were previously only settable once, at field creation
(`AddFieldModal`) — the Field Properties panel had no options control at
all, so an existing field's option list (e.g. Carried Items' `items`
field) could never be revisited afterward. The panel now exposes an
add/remove/reorder options editor for these field types, disabled for a
locked field unless the admin has unlocked it for editing; saving an
option-required field down to zero options is rejected by the existing
`update_field` validation, surfaced inline in the panel rather than only
as a toast.

## Changing an existing field's type

A field's type is editable after creation from the Field Properties
panel's "Field Type" dropdown for every field **except** a fixed set of
system-seeded fields whose value is consumed elsewhere in the backend as
a specific structured type, not just rendered as form input
(`_TYPE_LOCKED_SYSTEM_FIELD_KEYS` in `form_builder/service.py`):

| Key | Why its type is fixed |
|---|---|
| `email`, `phone`, `preferredContactMethod` | Coupled together by `_require_reachable_contact`/`_require_contact_for_method` (`invitations/schemas.py`) and consumed as the literal deliverable address/channel by notification dispatch. |
| `registrationType` | A real `RegistrationType` enum, a `list_invitations` filter column, and drives `_check_visitor_list_matches_registration_type`. |
| `preferredVisitDate`, `preferredVisitTime` | Real `Date`/`Time` (not `String`) database columns, consumed as true date/time values by overstay detection and the emergency "who's inside" report. |
| `idProofUpload`, `profilePhoto` | `file_upload` fields feeding the document/photo storage and PII-handling pipeline — their value is a stored file reference, not form input. |
| `visitorCategory` | Its real options come from the separate Visitor Category catalog, not this field's own `options` list. |

Every other field — including every other system field, locked or
toggleable (Full Name, Purpose of Visit, License Plate, Expected
Duration, Additional Notes, ID Proof Type, Vehicle Type) — is
retypeable. Changing it re-runs the same
type-dependent checks field creation already applies, against the
field's *resulting* state (the update's own values where provided, the
field's existing saved values otherwise): a type change to
`dropdown_select`/`checkbox_list` needs a non-empty `options` list (either
already saved or supplied in the same request); a type change to
`static_text` is rejected if the field is still `isRequired=true` or has
no `helpText`. Changing a field's type away from an option-bearing type
clears its stored `options` (they don't apply to the new type).

For a retypeable field's submission-time validation, see "Retyped system
fields and submission validation" in `docs/features/invitations.md`.

## Unlocking a locked field to edit it

A locked field's Label, Placeholder, Description, Field Type, and (if
option-bearing) Options controls are disabled by default in the Field
Properties panel, matching its permanently-locked position/deletion
protection — Field Type only for a locked field whose type isn't one of
the fixed keys in the table above; those stay disabled regardless of lock
state. An admin can select "Unlock to Edit" on a locked field to enable
those controls for that field and save changes to them — e.g. rewording a
mandatory field's label, adding an option to a locked dropdown, or
retyping "Full Name" from a plain text input to a textarea. This does
**not** extend to the field's Required/Active state: that stays governed
by the existing locked-field enforcement (`update_field` rejects
`isActive`/`isRequired` → `false`) whether or not the field has been
unlocked for editing, since those fields back non-nullable database
columns. The unlock state is local to the open Field Properties panel
(not persisted server-side, and not a new `FormField` column) —
switching to a different field, or re-locking, discards any unsaved
edits and returns the panel to its default locked/disabled state. The
backend itself has never rejected a label/placeholder/`helpText`/
`options`/`fieldType` change on a locked field (only `isActive`/
`isRequired` → `false` and delete/reorder are actually enforced
server-side) — the lock this UI shows and lets an admin lift is a
deliberate UX guard against accidental edits, not a backend permission
boundary.

## Scoping and resolution

`GET`/`POST`/etc. under `/form-builder/steps` and `/form-builder/fields`
take an optional `X-Branch-ID` header: present, the request targets that
branch's draft; absent, the tenant-wide default. Customizing a branch for
the first time clones the tenant-default's current draft (or the built-in
defaults, if that's also untouched) rather than starting blank.

`GET /form-builder/effective` (no permission gate — the public visitor-
request page and the staff wizard both need it) resolves: the branch's
published config, falling back to the tenant-default's published config,
falling back to `DEFAULT_EFFECTIVE_FORM`. Resolution is cached in Redis
(`vmss:{tenantId}:form-builder:effective:{branchId|"default"}`, 5-minute
TTL) and invalidated synchronously by `publish`.

### Old snapshots and removed field types (`heal-stale-form-config-data`)

A published snapshot is frozen JSON, so one published before a key existed
lacks that key, and one published before a field type was removed still
carries it. Served verbatim, either made the web app reject the whole form
("Step 0 of 0"). So `resolve_effective_form` passes every snapshot,
including cache hits, through `form_builder/snapshot.py::normalize_snapshot`:
- missing field keys get their defaults (`SNAPSHOT_FIELD_DEFAULTS`: `hideLabel`
  is `false`), and so do missing group keys (`SNAPSHOT_GROUP_DEFAULTS`:
  `visibilityCondition` is `null`);
- a group's missing `fieldIds` is rebuilt from its `fieldKeys`;
- a field whose type isn't in `FormFieldType` is dropped, pruned from its
  group, and logged as `form_field_unknown_type_skipped` (WARNING).

**Adding a key to `service._step_to_snapshot`?** Add its default to
`snapshot.py` too. `test_normalized_snapshot_matches_current_shape` fails
until you do.

The admin reads (step list, a step's fields, reorder) skip stored rows of
an unsupported type with the same warning, instead of a 500 from
`FormFieldOut`'s enum. `PATCH /form-builder/fields/{id}` on such a row
returns 422 unless the request sets a supported `fieldType`; retyping is
how an admin repairs it.

Tenant migration `c3d5e7f9a1b2_heal_stale_form_config_data` cleans the
stored data: in `form_fields` (including soft-deleted rows) and every
snapshot, it converts the removed types as follows:

| Removed type | Becomes | Options |
|---|---|---|
| `signature_pad` | `checkbox_single` (a consent checkbox) | cleared |
| `rich_text_block` | `static_text` | kept |
| `dynamic_table` | `textarea` | cleared |

It also backfills the keys above. It's idempotent and logs every
conversion; the downgrade is a no-op. Apply it with
`scripts/upgrade_all_tenants.py`.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/form-builder/steps` | `form-builder:view` | List the resolved scope's draft steps (with nested fields). Seeds the scope on first call. |
| POST | `/api/v1/form-builder/steps` | `form-builder:manage` | Create a custom step. |
| PATCH | `/api/v1/form-builder/steps/{id}` | `form-builder:manage` | Update a step; 422 if it would deactivate a locked step. |
| DELETE | `/api/v1/form-builder/steps/{id}` | `form-builder:manage` | Soft-delete a step; 422 if locked. |
| POST | `/api/v1/form-builder/steps/reorder` | `form-builder:manage` | Reorder the scope's steps (`orderedIds`). |
| GET | `/api/v1/form-builder/steps/{id}/fields` | `form-builder:view` | List a step's fields. |
| POST | `/api/v1/form-builder/steps/{id}/fields` | `form-builder:manage` | Add a field. |
| PATCH | `/api/v1/form-builder/fields/{id}` | `form-builder:manage` | Update a field; 422 on a locked-field active/required change, a type change for one of the fixed type-locked keys (see "Changing an existing field's type"), a `static_text` field marked required, an option-required type with no options, or an invalid visibility condition. |
| DELETE | `/api/v1/form-builder/fields/{id}` | `form-builder:manage` | Soft-delete a field; 422 if locked. |
| POST | `/api/v1/form-builder/steps/{id}/fields/reorder` | `form-builder:manage` | Reorder a step's fields. |
| GET | `/api/v1/form-builder/steps/{id}/groups` | `form-builder:view` | List a step's field groups. |
| POST | `/api/v1/form-builder/steps/{id}/groups` | `form-builder:manage` | Create a field group on a step. |
| PATCH | `/api/v1/form-builder/groups/{id}` | `form-builder:manage` | Update a group (including `visibilityCondition`); 422 on a locked group made non-repeatable, an invalid `minInstances`/`maxInstances` range, a range change on Visitor Info's group, a dangling `visibilityCondition` reference, or a condition referencing one of the group's own member fields. |
| DELETE | `/api/v1/form-builder/groups/{id}` | `form-builder:manage` | Soft-delete a group (ungroups its fields first); 422 if locked. |
| POST | `/api/v1/form-builder/steps/{id}/groups/reorder` | `form-builder:manage` | Reorder a step's groups. |
| POST | `/api/v1/form-builder/publish` | `form-builder:manage` | Re-validate and publish the resolved scope's draft; bumps `version`. |
| GET | `/api/v1/form-builder/effective` | none (public) | The currently live form for the resolved (or default) branch. |

Publishing queues an `AuditLog` write (actor, scope, new version) via
`BackgroundTasks`, per `security-architecture.md` §5.

## Permissions

`form-builder:manage`/`:view`, seeded by `auth/rbac_catalog.py`, granted to
`admin` only in the default seed.

## Deploying this feature to an already-provisioned tenant

Both this feature's tables (`form_steps`/`form_fields`/`form_config_versions`,
migration `afb2544db111`) and its permission codes
(`form-builder:manage`/`:view`, `auth/rbac_catalog.py`) are only applied
automatically at *new* tenant provisioning (`platform/service.py::
create_tenant`). An existing tenant doesn't pick either up on its own — the
admin Form Builder screen 500s on the missing tables until the schema is
migrated, and even once migrated, 403s until the tenant's `admin` role is
granted the new permissions. Run this once per environment after deploying
this feature (or any future tenant-scoped migration/catalog addition) to
bring every existing tenant current on both:

```
ddev exec uv run python scripts/upgrade_all_tenants.py
```

This applies any pending `alembic_tenant` migrations and re-syncs every
tenant's standard role grants and default form-builder config against the
current catalog — safe to re-run (every step is idempotent). See
`openspec/changes/fix-form-builder-audit-gaps/design.md` for how this was
found and why the fix covers both the schema and the RBAC catalog, not just
the missing tables.

Field groups (`form_field_groups`, migration `b8e3f4a1c6d2`) backfill the
`vehicles`/`visitors` groups for every existing branch's Vehicle Info/
Visitor Info steps as part of the same migration run, but do **not**
force-republish any already-published `FormConfigVersion` — a pre-existing
snapshot with no group data simply behaves as an unlimited repeatable
group (today's actual Vehicle Info behavior) until an admin next publishes
that scope. See `openspec/changes/add-repeatable-field-groups/design.md`
Risks/Migration Plan.

### Preferred Contact Method offers WhatsApp

The locked `preferred_contact_method` field offers `email`, `sms` and
`whatsapp`. New tenants get all three from the seed defaults; migration
`9d2b6f1c4a8e` appends `whatsapp` for existing tenants, in both the draft
`form_fields` row and every published `form_config_versions` snapshot
(idempotent; no republish needed). Rollout order: deploy WhatsApp delivery
(`integrate-fast2sms-dlt-sms`) with its Fast2SMS settings first, then run
`scripts/upgrade_all_tenants.py`, then flush each tenant's
`vmss:{tenant_id}:form-builder:effective:*` Redis keys (or wait out the
cache TTL) so the cached effective form stops hiding the option. See
`openspec/changes/backfill-whatsapp-contact-method-form-option/design.md`.

## Locked-position ordering

Locked steps (Visitor Info, Visit Details, Review & Confirm) always occupy
the first-two/last positions among a scope's steps; locked fields keep
their relative order among themselves within a step. This is upheld two
ways:

- **At creation**: `create_step` positions a new custom step immediately
  before the locked trailing run (before Review & Confirm), never after
  it. A scope whose order was corrupted before this was enforced (a custom
  step ending up positioned after Review & Confirm) is repaired
  automatically, in place, the next time it's accessed — no admin action or
  migration needed.
- **At reorder**: `POST .../steps/reorder` and `POST .../fields/reorder`
  reject (422) any payload that would change a locked step's or field's
  position relative to its locked siblings. The admin Steps overview page's
  drag-and-drop only offers a handle on non-locked step cards (mirroring the
  Step Editor's existing per-field drag handles), so this can't be
  triggered from the UI at all; the server-side guard is what protects a
  direct API call.

See `openspec/changes/fix-form-builder-config-gaps/` (the reorder-time
guard) and `openspec/changes/fix-form-builder-step-order-and-ui-gaps/` (the
creation-time fix and repair, closing a gap the first change's guard
surfaced but didn't fully fix) for how this was found and closed.

## What's wired in, and what isn't yet

`invitations`/`registrations` submission **does** validate against the
calling branch's published configuration now (`invitations/service.py::
create_invitation`) — ID-proof/photo requiredness, required consents, and
allowed Carried Items keys. See `docs/features/invitations.md`'s
"Branch-configurable requiredness" section. **Expected Duration** (Visit
Details) is the one toggleable field with no dynamic check at all —
`invitations/schemas.py::VisitDetailsSubmit.expected_duration` is
structurally required regardless of form-builder configuration; deactivating
it in the admin UI currently has no effect on the backend. Flagged as an
open follow-up, not silently treated as fixed.

The frontend (`VMMS_WEB`) has the admin Form Builder UI (steps overview with
step reordering, step editor with field reordering and a Publish action of
its own) and a config-driven renderer for the public/staff registration
wizards. **Carried Items** and **Consent Agreement**
(`CarriedItemsStep`/`ConsentStep`, shared by both wizards) render their
field *set* directly from the effective form. **Visitor Info, Visit
Details, and Vehicle Info** keep their original fixed JSX layout for their
own seeded fields (that set doesn't change) but are now *effective-form-
aware*: each toggleable field (ID proof type/upload + profile photo on
Visitor Info, additional notes on Visit Details, make/model + color on
Vehicle Info) is shown/hidden and required/optional per the calling
branch's published configuration, the same way Carried Items/Consent
Agreement fields already were. Expected Duration is the one exception (see
above) — always shown and required, since hiding it while the backend
still requires it would break submission with no visible field to fix.

All six steps now additionally render a generic `CustomFieldsSection` for
any admin-authored field beyond their own seeded/fixed set
(`add-generic-custom-field-support`) — a shared component, not a
per-step reimplementation. Where it renders depends on the field's answer
scope (see "Custom-field answer storage" below): once per visitor
(`VisitorFieldsForm`, used by both the primary contact and each
co-visitor), once per vehicle (`VehicleInfoStep`'s draft form), or once per
invitation (`VisitInfoStep`, `CarriedItemsStep`, `GenericConfiguredStep`
for a genuinely custom step). `CarriedItemsStep` previously misbound any
field beyond its seeded `items` to a single `description` slot, which
silently dropped or collided a second custom field's answer — fixed
alongside this, keeping `item_description` (a real seeded field, not a
made-up one) on its own dedicated binding.

### Custom-field answer storage

An admin-authored field's submitted answer is captured at the same scope
its step's own seeded fields already use — not one invitation-wide bag:

- **Visitor Info** → per-visitor. `Invitation.primary_contact_custom_field_values`
  for the primary contact, `InvitationVisitor.custom_field_values` for each
  co-visitor — both JSONB, keyed by field key.
- **Vehicle Info** (beyond the locked license-plate field) → per-vehicle,
  `InvitationVehicle.custom_field_values`.
- **Visit Details, Carried Items** (beyond `items`/`item_description`),
  **and any custom step** → per-invitation, `Invitation.custom_field_values`.
- **Consent Agreement** is the one exception: every field on that step,
  seeded or admin-authored, has always flowed through the existing
  `consents` map (`allowed_consent_keys`/`required_consent_keys` iterate
  every field, not only seeded ones) — a new Consent Agreement field needs
  no change here at all.

`POST /invitations`/`POST /registrations/walk-in` accept the matching
`customFieldValues` map at each scope — nested on each `primaryContact`/
`visitors[]`/`vehicles[]` entry, plus one at the request's top level for
the per-invitation case — validated against the resolved branch's
effective form (unknown key or missing-required-value rejected with 422)
via `form_builder/validation.py`'s `custom_fields_for_step`/
`custom_fields_for_invitation_scope`/`validate_custom_field_values`, which
distinguish a step's seeded fields from admin-authored ones by `isSystem`
alone — no step-key-specific carve-out beyond the Consent Agreement
exception above. See `docs/features/invitations.md` for the full request/
response contract.

Both admin pages now also track and surface "unpublished draft changes"
(a same-session, per-scope client-side flag — no draft-vs-published diff
endpoint exists) with a Publish action reachable from either page, and field
save confirmations say "saved to draft, publish to update the visitor
form" instead of implying the change is already live.

Still entirely unbuilt: the `VisitorCategory.form_schema` column drop
(`tasks.md` §5.2, deliberately deferred for a burn-in period), and inline
rendering of `file_upload` fields on any step (`DynamicField` shows a "not
supported inline yet" placeholder for these today) — `custom_field_values`
storage now exists for every step (`add-generic-custom-field-support`),
but only for the field types `DynamicField` can actually render/collect a
value for. `dynamic_table`, `rich_text_block`, and `signature_pad` were
removed from the field-type catalog entirely
(`update-form-field-type-catalog`) rather than left as an unbuilt-inline
case, since none had a capture UI, submission validation, or rendering
behavior to begin with.
