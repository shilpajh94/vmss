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
  `width`, `orderIndex`).
- **`FormConfigVersion`** — the *published* snapshot for one scope
  (`branchId` nullable), overwritten in place on every publish. No version
  history is kept in this iteration — publishing atomically replaces the
  previously-live configuration.

`FormStep`/`FormField` are the admin's mutable **draft** — every create/
update/delete/reorder call only ever touches these rows. They have no
effect on live invitation/registration submission or the public/staff
renderer until `POST /form-builder/publish` re-validates the whole draft
and serializes it into that scope's `FormConfigVersion`.

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
  phone, visitor category (Visitor Info); purpose of visit, host,
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

## Field types

`text`, `email`, `phone`, `number`, `dropdown_select`, `date_picker`,
`time_picker`, `toggle_switch`, `checkbox_list`, `file_upload`, `textarea`,
`dynamic_table`, `rich_text_block`, `signature_pad`. `dropdown_select` and
`checkbox_list` must declare a non-empty `options` list (system fields
whose real options come from a live catalog — e.g. Visitor Category — are
exempt, since their options aren't static). A field may declare
`visibilityCondition` (`{fieldKey, operator, value}`, `operator` one of
`equals`/`not_equals`) referencing another field in the *same* step; a
dangling reference or a dependency cycle is rejected both at field-save
time and again at publish time.

## Field description, and editing options after creation

A field's `helpText` is admin-authored static text shown to the visitor
alongside the field itself — e.g. the actual body of a "Terms &
Conditions" or "Data Processing Consent" statement on the Consent
Agreement step — not a value the visitor fills in. It's settable for any
field type from both the "Add New Custom Field" modal (at creation) and
the Field Properties panel (after creation), the latter disabled when the
field is locked, matching that field's label/placeholder inputs. The
public/staff renderer (`DynamicField`) shows it under the field's own
control, truncated to its first sentence with a "See more"/"See less"
toggle, for every field type and step uniformly.

`checkbox_list`, `dropdown_select`, and an optioned `toggle_switch`
field's `options` were previously only settable once, at field creation
(`AddFieldModal`) — the Field Properties panel had no options control at
all, so an existing field's option list (e.g. Carried Items' `items`
field) could never be revisited afterward. The panel now exposes an
add/remove/reorder options editor for these field types, disabled when
the field is locked; saving an option-required field down to zero options
is rejected by the existing `update_field` validation, surfaced inline in
the panel rather than only as a toast.

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
| PATCH | `/api/v1/form-builder/fields/{id}` | `form-builder:manage` | Update a field; 422 on a locked-field active/required change, an option-required type with no options, or an invalid visibility condition. |
| DELETE | `/api/v1/form-builder/fields/{id}` | `form-builder:manage` | Soft-delete a field; 422 if locked. |
| POST | `/api/v1/form-builder/steps/{id}/fields/reorder` | `form-builder:manage` | Reorder a step's fields. |
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
rendering of `file_upload`/`dynamic_table`/`signature_pad`/`rich_text_block`
fields on any step (`DynamicField` shows a "not supported inline yet"
placeholder for these today) — `custom_field_values` storage now exists for
every step (`add-generic-custom-field-support`), but only for the field
types `DynamicField` can actually render/collect a value for.
