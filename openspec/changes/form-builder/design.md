## Context

See `proposal.md` for motivation. Relevant current state this design builds
on or must not break:

- `invitations/models.py::Invitation` has fixed typed columns for every
  section of today's form (primary contact, visit details, carried items as
  a JSONB list of a fixed `CarriedItemCategory` enum, three fixed consent
  booleans); `InvitationVehicle` is a child table with fixed columns
  (`vehicle_type`, `license_plate`, `make`, `model`, `color`).
  `invitations/schemas.py::InvitationCreate` validates all of this with
  hardcoded Pydantic models.
- `visitors/models.py::VisitorCategory.form_schema` (JSONB list of
  `FormFieldDefinition`: `name`, `label`, `field_type`, `required`,
  `options`, `help_text`) already models "a flat list of extra fields," but
  is never read by `invitations/service.py` — dead weight this change
  removes (see the `visitors` delta spec).
- `org_structure/deps.py::get_branch_context` already resolves `X-Branch-ID`
  → `Branch`; `registrations` (walk-in) resolves branch via a device
  credential or a server-configured default. Both paths end up with a
  concrete `branch_id` before invitation/registration creation runs.
- `auth/rbac_catalog.py` is the single source of truth for permission codes
  and role grants (`PERMISSION_CODES` + `ROLE_PERMISSIONS`,
  idempotently applied by `seed_default_roles()`).
- Frontend (`VMMS_WEB`): React 19 + `react-router` 8 + Tailwind 4 + Zod 4,
  hexagonal layout (`domain/entities`, `data/use-cases`, `presentation/...`).
  No form library, no DnD library, no UI kit installed. Two existing
  hardcoded multi-step wizards (`use-visitor-request-wizard.ts`,
  `use-staff-visitor-registration-wizard.ts`) already implement
  step-state/step-validation/step-components against a fixed zod schema
  mirroring `InvitationCreate`.

## Goals / Non-Goals

**Goals:**
- Admin-configurable steps/fields, branch-scoped with a tenant-default
  fallback, per the tiered configurability the user specified (locked /
  toggleable / fully-configurable, see `specs/form-builder/spec.md`).
- Zero behavior change for any tenant/branch that never opens the Form
  Builder — the migration seeds every existing branch's effective
  configuration from today's fixed fields.
- A single config-driven renderer that both the public visitor-request
  wizard and the staff pre-registration wizard consume, replacing their
  per-step hardcoded components.
- Keep the existing typed `Invitation`/`InvitationVehicle` columns for
  system fields (reporting/audit/search continue to work unchanged); only
  admin-added custom fields land in new JSONB storage.

**Non-Goals:**
- Version history or rollback (explicitly deferred — see proposal).
- Compound conditional-visibility logic (AND/OR groups, multi-field
  expressions) — one field, one comparison operator, one value, matching
  the mockup's "Show this field when / Condition is" pair.
- Malware/content scanning for the new File Upload field type — already an
  open, tracked pre-production item in `file-upload-handling.md` §4,
  unaffected by this change.
- Localization/multi-language field labels.
- Concurrent-edit conflict resolution beyond last-write-wins on a draft.

## Decisions

### Decision 1: Two-layer storage — mutable draft tables + an immutable published snapshot
`form_steps` / `form_fields` (tenant-scoped tables, `alembic_tenant/`) are
the admin's **draft** working copy — every create/update/delete/reorder call
mutates these rows directly, scoped by `branch_id` (nullable = tenant
default). A separate `form_config_versions` table holds, per scope
(`branch_id` nullable, one row per scope), a JSONB **snapshot** of the fully
resolved step/field tree plus a `version` integer and `published_at`/
`published_by_user_id`. `POST .../publish` re-validates the current draft as
a whole (dangling conditional references, option-less select fields, a
locked field improperly toggled) and, only if valid, serializes it into that
scope's `form_config_versions` row — overwriting it (no history, per the
proposal's chosen scope).

*Why*: invitation/registration creation is a hot, sometimes-public path that
needs one cheap read to get "the live form," not a join across
steps+fields+conditions on every submission. Draft mutation staying in
normalized tables keeps the admin CRUD/reorder/validate operations simple
and relational (foreign keys, uniqueness constraints); publish is the one
place that pays the cost of resolving the tree, once, instead of on every
submission.

*Alternative considered*: a single versioned table (`FormStep`/`FormField`
rows each tagged `draft`/`published`, doubled per edit). Rejected — doubles
every row's lifecycle management (every field update becomes two writes)
for no benefit here, since no history/rollback is in scope; the snapshot
table gets the same "safe to edit without affecting live traffic" property
more simply.

### Decision 2: Branch scoping and fallback resolution
`form_config_versions.branch_id` is nullable; `NULL` is the tenant-default
scope. Effective-form resolution: look up the calling branch's row; if
absent, fall back to the `NULL`-scope row; if that's also absent (should be
impossible post-migration/post-provisioning), log `ERROR` and fail the
request, mirroring the `registrations` capability's existing "unconfigured
default" server-misconfiguration handling. Customizing a branch for the
first time clones the tenant-default's *draft* (or another branch's, admin's
choice) into new `branch_id`-scoped `form_steps`/`form_fields` rows rather
than starting empty.

*Why*: matches the mockup's workspace selector and the user's explicit
choice of per-branch-with-tenant-default scoping, while giving every branch
a sensible starting point instead of a blank form.

### Decision 3: Field/step configurability tiers are columns, not a separate table
`form_fields` carries `is_system` (built-in vs admin-created),
`is_locked` (required/active immutable via the API — true only for the
fields enumerated in `specs/form-builder/spec.md`'s "System Fields Are
Seeded..."), `active`, `required`, `options` (JSONB), `validation_rules`
(JSONB), `visibility_condition` (JSONB `{field_key, operator, value}` or
null), `width`, `order_index`. `form_steps` carries the analogous
`is_system`/`is_locked`/`active`/`order_index`. The field-update endpoint
rejects any attempt to change `active`/`required` on a row with
`is_locked = true`.

*Why*: keeps one field/step model and one CRUD code path for both "system"
and fully custom fields — the tier is data, not a type hierarchy — which is
what lets Carried Items/Vehicle Info/Consent Agreement be "fully
configurable" (admin freely adds/removes non-locked rows) with no special
casing beyond the locked-field guard.

### Decision 4: Submitted-value storage stays hybrid, per field tier
- **Locked + toggleable system fields** (Visitor Info, Visit Details,
  Vehicle Info's license plate): keep today's typed `Invitation`/
  `InvitationVehicle` columns unchanged. `invitations/service.py` reads the
  effective form to decide requiredness/allowed-options at validation time,
  but still writes to the same columns it does today.
- **Consent Agreement**: replace the three fixed boolean columns with one
  `consents: dict[str, bool]` JSONB column (key = the consent field's
  `key`, matching whatever the branch's published configuration declares)
  plus the existing `consent_recorded_at` timestamp. A migration backfills
  every existing invitation's three booleans into this shape before the old
  columns are dropped (Decision 9 / Migration Plan).
- **Carried items**: no column change — `carried_items` is already a JSONB
  list; only the *meaning* changes, from "must be one of the fixed
  `CarriedItemCategory` enum" to "must be one of the calling branch's
  published Carried Items field keys."
- **Vehicle Info beyond the locked fields, and any admin-added field on a
  custom step**: a new `custom_field_values: dict[str, Any]` JSONB column —
  on `InvitationVehicle` for vehicle-step custom fields, and on `Invitation`
  for anything in a brand-new custom step — keyed by the field's `key`.

*Why*: this is the least-migration-risk path that still satisfies "fully
configurable" where the user asked for it. It avoids turning `Invitation`
into "one big JSON blob with no typed columns," which would break every
existing report/audit/search query built against named columns, while still
giving Carried Items/Vehicle Info/Consent Agreement/new-custom-steps a real
escape hatch for arbitrary admin-defined fields.

### Decision 5: A dynamic validation layer runs after Pydantic, before persistence
`InvitationCreate` (Pydantic) keeps validating structural shape — which
top-level keys exist, that a vehicle has `licensePlate`, that
`registrationType` is one of the two enum values. A new
`form_builder/validation.py::validate_against_effective_form(payload,
effective_form)` runs in `invitations/service.py` immediately after
Pydantic validation and before any DB write: it resolves each active field's
required/option/validation-rule state (applying conditional-visibility —
a field whose condition isn't met is exempted from its own requiredness),
and raises the same 422 validation-error shape used today.

*Why*: Pydantic validators can't await a DB/Redis read for the effective
form, so the branch-configured half of validation can't live in the
Pydantic model itself. Splitting "structural shape" (Pydantic, unchanged)
from "branch-configured requiredness/options" (new service-layer step) keeps
each half simple and testable in isolation, and keeps the fixed-shape
scenarios in the `invitations` delta spec (missing top-level field, vehicle
missing `licensePlate`) verifiably unaffected by branch configuration.

### Decision 6: Effective form is cached, invalidated synchronously on publish
`GET`-effective-form reads (invoked on every invitation/registration
creation and by the frontend's public/staff wizards to fetch the live form)
are cached in Redis at `vmss:{tenant_id}:form-builder:effective:{branch_id
or "default"}` (`database-architecture.md` §6 convention), TTL'd as a
safety net. `POST .../publish` invalidates the affected scope's key in the
same request before returning success.

*Why*: this read sits on the hot invitation-creation path (`query-
performance.md`'s "don't loop-and-query" applies just as much to "don't
resolve a step/field tree from Postgres on every submission").

### Decision 7: Permissions
Two new codes in `auth/rbac_catalog.py`: `form-builder:manage` (create/
update/delete/reorder/publish; granted to `admin`) and `form-builder:view`
(read the draft in the admin UI; granted to `admin`). Resolving the
*effective* (published) form for submission/rendering is an internal read
with no permission gate of its own — it's invoked by the invitation/
registration flow (already permission/credential-gated on its own terms),
and by the public visitor-request page, which by definition has no admin
permission to check.

### Decision 8: Frontend — extend the existing patterns, avoid a second forms paradigm
No form-library/schema-form package (react-hook-form, Formik, `@rjsf/core`,
Formily, uniforms) is introduced. The codebase already has a working
pattern — per-step state + Zod validation + step components
(`use-visitor-request-wizard.ts`) — so the config-driven renderer follows
the same shape instead of introducing a second one:
- `buildZodSchemaForStep(fields: EffectiveFormField[])`: maps each active
  field's type + validation rules + conditional-visibility to a Zod schema
  piece, replacing the hand-written per-step Zod schemas
  (`staff-visit-request-schema.ts` / `visit-request-schema.ts`) for the
  fields those steps now source from `form-builder`.
- `FIELD_COMPONENT_REGISTRY`: one renderer component per `fieldType`
  (text/email/phone/number/dropdown-select/date-picker/time-picker/
  toggle-switch/checkbox-list/file-upload/textarea/dynamic-table/
  rich-text-block/signature-pad), swapped in by the step renderer in field
  order, respecting `width` (`half`/`full` → Tailwind grid span) and
  `visibilityCondition` (skip rendering, and skip Zod validation, when
  unmet).
- **New dependencies, kept minimal and isolated**:
  - `@dnd-kit/core` + `@dnd-kit/sortable` for the admin field/step
    reorder list (`react-beautiful-dnd` is unmaintained; `react-dnd` is a
    heavier API for a simple sortable-list use case).
  - `react-signature-canvas` for the Signature Pad field type — small,
    canvas-based, the standard choice; no existing alternative in the repo.
  - A lightweight rich-text editor (e.g. Tiptap) **only** for the admin Form
    Builder's authoring of a Rich Text Block field's content — on the
    visitor-facing side, a Rich Text Block is rendered read-only (sanitized
    HTML the admin authored), not an input, so no editor library ships to
    the public bundle. Both the admin builder route and Tiptap are
    code-split so the public/staff wizard bundles don't grow.
  - Date/time pickers use native `<input type="date">`/`<input
    type="time">` — zero new dependency, consistent across evergreen
    browsers; flagged as an assumption since the mockup doesn't show the
    open picker UI in detail.
  - Dynamic Table field type is built with plain React state (add/remove
    row against an admin-authored column list stored in the field's
    `options`) — no grid library needed for this scope.
- Admin menu/routing follows the existing `AdminSidebar.tsx` pattern:
  add `'form-builder'` to `AdminSidebarActiveItem`, a `NAV_ITEMS` entry, and
  a branch in the `navigate()` if-chain, plus new routes in `App.tsx` for
  the steps-overview page and the per-step field editor — the same shape as
  the existing `admin-visitor-categories`/`admin-workflows` pages.

### Decision 9: `VisitorCategory.form_schema` removal is a column drop, not a silent ignore, after a burn-in migration
Per the `visitors` delta spec, `form_schema` stops being read or written at
the API layer immediately; the column itself is dropped in a follow-up
`alembic_tenant` migration (not the same one that ships the API change) —
consistent with `database-architecture.md`'s migration discipline, and
low-risk since (per the delta spec) no code path has ever consumed it.

## Risks / Trade-offs

- **Dynamic + Pydantic validation split is two places to look for "why was
  this rejected"** → Mitigated by keeping the dynamic layer to exactly the
  branch-configurable concerns (required/active/options/validation-rules/
  conditional-visibility) and nothing structural; `invitations/service.py`
  calls it as one explicit step right after Pydantic validation, not
  scattered across the file.
- **Effective-form cache could serve stale config immediately after a
  failed invalidation** → Mitigated by invalidating synchronously inside the
  publish request (not via a background task) plus a short TTL as a backstop.
- **Consent storage migration (3 booleans → JSONB) touches existing rows**
  → Mitigated by an additive-then-destructive two-migration sequence
  (Migration Plan below); any reporting/audit code referencing the old
  column names is a required grep-and-update task, not an afterthought.
- **Branch-level override multiplies "which config is actually live"**
  → Mitigated by one documented, unit-tested resolution order (branch →
  tenant default → error), and the admin UI always showing which scope
  (workspace) is being edited, matching the mockup's workspace selector.
- **New frontend dependencies (`@dnd-kit`, `react-signature-canvas`,
  Tiptap)** → Mitigated by scoping Tiptap to the code-split admin route only;
  `@dnd-kit`/`react-signature-canvas` are small and single-purpose.

## Migration Plan

1. `alembic_tenant/` migration: add `form_steps`, `form_fields`,
   `form_config_versions` tables; add `consents` (JSONB) and
   `custom_field_values` (JSONB) to `invitations`; add `custom_field_values`
   (JSONB) to `invitation_vehicles`. Additive only — no drops.
2. Data-migration step (in the same or an immediately-following revision,
   idempotent, following the repo's hand-written-migration pattern): seed
   every tenant schema's tenant-default `form_steps`/`form_fields` rows from
   today's fixed field set with the correct locked/toggleable tiers, backfill
   `invitations.consents` from the three existing boolean columns, and
   publish a `version = 1` `form_config_versions` row (`branch_id = NULL`)
   from that seed — so every existing branch's effective form matches
   current behavior exactly, with zero admin action required.
3. Add `form-builder:manage`/`form-builder:view` to `PERMISSION_CODES` and
   `ROLE_PERMISSIONS["admin"]` in `auth/rbac_catalog.py`
   (`seed_default_roles()` backfills existing tenants idempotently — no new
   seed script).
4. Ship the `form_builder` feature package and the `invitations/service.py`
   dynamic-validation integration together, so the cutover point where
   `InvitationCreate` starts consulting the effective form is the same
   deploy that guarantees a seeded, behavior-preserving effective form
   exists for every branch.
5. Ship frontend: Form Builder admin pages first (usable, but not yet the
   thing the public/staff forms render from), then cut
   `visitor-request`/`staff-visitor-registration` over to the config-driven
   renderer once parity-tested against the seeded default configuration.
6. Follow-up migration (separate PR, after a burn-in period): drop the
   three superseded consent boolean columns on `invitations` and the
   `form_schema` column on `visitor_categories`.
