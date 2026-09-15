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
- **Fully configurable**: Carried Items, Vehicle Info's non-locked fields,
  Consent Agreement, and any custom step accept an admin-authored field
  list from scratch — the same "Add New Custom Field" flow for every field
  type.

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

## What's wired in, and what isn't yet

`invitations`/`registrations` submission **does** validate against the
calling branch's published configuration now (`invitations/service.py::
create_invitation`) — ID-proof/photo requiredness, required consents, and
allowed Carried Items keys. See `docs/features/invitations.md`'s
"Branch-configurable requiredness" section.

The frontend (`VMMS_WEB`) has both the admin Form Builder UI (steps
overview, step editor) and a config-driven renderer for the public/staff
registration wizards — but the renderer only covers the **Carried Items**
and **Consent Agreement** steps (`CarriedItemsStep`/`ConsentStep`, shared
by both wizards) — the two steps whose admin-configurable field *set*
actually changed. Visitor Info, Visit Details, and Vehicle Info still use
their original hardcoded components: correct for the fixed field set
`defaults.py` seeds, but not yet reactive to an admin deactivating one of
their toggleable fields (ID proof, profile photo, expected duration,
additional notes) — the wizard still asks for all of them regardless of
branch configuration, which is stricter than the backend requires, never
laxer. See `openspec/changes/form-builder/tasks.md` §7's "Known remaining
gaps" for the specifics.

Still entirely unbuilt: the `VisitorCategory.form_schema` column drop
(`tasks.md` §5.2, deliberately deferred for a burn-in period) and any
`custom_field_values` storage for an admin-added Vehicle Info/custom-step
field (`tasks.md` §1.3/§4.3 — no scenario has required it yet).
