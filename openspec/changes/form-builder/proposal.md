## Why

Today the invitation/registration form (visitor info, visit details, carried
items, vehicle info, consents) is hardcoded — fixed Pydantic schemas on the
API side, fixed wizard-step components on the frontend, and a per-category
`VisitorCategory.form_schema` (visitors capability) that isn't even wired
into invitation creation yet. Every tenant's registration process differs
(what's required, what's optional, what extra data a site needs to collect),
and today that means a code change and a deploy per tenant request. We need
admins to configure their own registration steps and fields from the admin
UI, with the invitation/walk-in-registration flow rendering and validating
against that configuration instead of a fixed shape.

## What Changes

- Add a new **Form Builder** admin capability: branch-scoped (falling back to
  a tenant-wide default) configuration of registration **steps** and, per
  step, the **fields** collected — field type, label, placeholder, required/
  active state, option sets, validation rules, conditional visibility
  (show/hide a field based on another field's value), and display width.
  Six canonical steps ship by default (Visitor Info, Visit Details, Carried
  Items, Vehicle Info, Consent Agreement, Review & Confirm); admins may also
  add wholly new custom steps.
- Field-level configurability is tiered, matching what's structurally safe to
  change without breaking downstream code that reads specific columns:
  - **Locked system fields** (full name, email, phone, visitor category in
    Visitor Info; purpose/host/date/time/department in Visit Details;
    license plate in Vehicle Info): always required, always shown — an admin
    may edit label/placeholder/help text but not turn them off.
  - **Toggleable system fields** (preferred contact method's allowed
    channels, ID-proof type/upload, profile photo in Visitor Info; expected
    duration, additional notes in Visit Details): admin can activate/
    deactivate and, for option-set fields (registration type, preferred
    contact method), choose which options are offered.
  - **Fully configurable steps** (Carried Items, Vehicle Info beyond license
    plate, Consent Agreement, and any new custom step): the admin authors the
    field list from scratch, the same way "Add New Custom Field" works in the
    mockups.
  - Visitor Info, Visit Details, and Review & Confirm are locked steps that
    can never be deactivated or removed; all other steps can be toggled
    active/inactive or removed.
- Draft/publish lifecycle: an admin's in-progress edits are a draft; only
  when published does a branch's live form change for new invitations/
  registrations. No version history or rollback in this iteration — a
  publish overwrites the previously-active version.
- `POST /invitations` and `POST /registrations/walk-in` (which shares its
  contract per the `registrations` capability) validate incoming submissions
  against the calling branch's currently published form configuration:
  required-ness of toggleable fields, which option values are accepted,
  which carried-item/vehicle/consent fields exist, and any admin-added custom
  field values — instead of the fixed enums/booleans used today.
- **BREAKING** (data shape only, not the wire contract's outer keys):
  `carriedItems` item categories, vehicle fields beyond the locked ones, and
  `consents` move from fixed enums/booleans to branch-configured field lists;
  a data migration seeds every existing branch's published configuration
  from today's fixed field set so existing behavior is preserved until an
  admin changes it.
- `VisitorCategory.form_schema` (visitors capability), never wired into
  invitation creation, is superseded: category-specific extra fields are now
  authored as ordinary Visitor Info fields with conditional visibility
  ("show when Registration Category equals `<category>`") rather than a
  separate per-category schema.
- Frontend: new "Form Builder" admin sidebar menu — a registration-steps
  overview page, a per-step field-list editor (drag-to-reorder, add/edit/
  delete field, field-properties panel), and a config-driven step/field
  renderer that replaces the hardcoded wizard step components for both the
  public visitor-request flow and the staff pre-registration flow.

## Capabilities

### New Capabilities
- `form-builder`: branch-scoped (tenant-default-fallback) CRUD for
  registration steps and fields, draft/publish lifecycle, and the resolved
  "effective form" read used by invitation/registration submission and by
  the frontend renderer.

### Modified Capabilities
- `invitations`: submission validation for ID-proof/photo requiredness,
  consent requirements, carried-item categories, and vehicle fields becomes
  driven by the branch's published form configuration instead of fixed
  enums/booleans.
- `visitors`: `VisitorCategory.form_schema` and its per-field validation
  requirement are removed in favor of `form-builder`'s conditional-visibility
  fields; category CRUD otherwise unchanged.

## Impact

- **New code**: `src/vmss_api/form_builder/` (models, schemas, service,
  repository, router, tests) — new tables `form_steps`, `form_fields`
  (tenant-scoped, `alembic_tenant/`); new permission codes
  `form-builder:manage`/`form-builder:view` in `auth/rbac_catalog.py`.
- **Changed code**: `invitations/schemas.py` and `invitations/service.py`
  (dynamic validation against the effective form instead of fixed Pydantic
  shapes for the affected sections), `invitations/models.py` (new JSONB
  columns for admin-defined custom field values on `Invitation` and
  `InvitationVehicle`; `carried_items`/`consents` JSON shape changes),
  `visitors/models.py` + `visitors/schemas.py` (`form_schema` removal),
  `api.py` (router registration), `main.py` (`openapi_tags`).
- **Data migration**: `alembic_tenant/` migrations to add the new tables/
  columns and to backfill every existing branch's published form
  configuration from today's fixed field set (registration type options,
  contact method options, the three fixed consents, the fixed
  `CarriedItemCategory` enum as seeded checklist items, the fixed vehicle
  fields), so no existing branch's behavior changes until an admin edits it.
- **Frontend (`VMMS_WEB`)**: new admin pages/routes and sidebar entry; a new
  drag-and-drop dependency (`@dnd-kit/core`, none installed today); a
  config-driven step/field renderer consumed by both
  `visitor-request`/`use-visitor-request-wizard` and
  `staff-visitor-registration`/`use-staff-visitor-registration-wizard`,
  replacing their per-step hardcoded components; zod schemas for the wire
  contract regenerated per the effective form rather than hand-written.
