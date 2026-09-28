## Context

See `proposal.md` - Why for the bug report and the investigation that
surfaced the real gap. Relevant current state:

- `form_builder/service.py:375-389` (`_FIXED_FIELD_SET_STEP_KEYS`) rejects
  `create_field` for `visitor_info`/`visit_details`.
- `FormField` (`form_builder/models.py:57-96`) stores only field
  *definitions* (key, label, type, options, validation, visibility
  condition) — never a submitted value. `resolve_effective_form`
  (`service.py:630-650`) already returns arbitrary field definitions
  generically for every step, including "fully configurable" ones.
- No generic answer-storage exists anywhere yet. `Invitation` has
  `carried_items: list[str]` and `consents: dict[str, bool]` — two
  fixed-shape columns each of which happens to fit one specific
  already-built step's value shape, not a generic mechanism.
  `CarriedItemsStep.tsx` special-cases `field.key === 'items'` and
  misbinds any other field to a `description` slot.
  `GenericConfiguredStep.tsx` (custom steps) keeps answers in wizard-only
  UI state and never submits them.
- `InvitationVisitor` (`invitations/models.py:208-231`) and
  `InvitationVehicle` have only fixed typed columns, no JSONB escape
  hatch. Visitor Info's existing fields (full name, email, category) are
  already per-visitor; Vehicle Info's existing field (license plate) is
  already per-vehicle; Visit Details/Carried Items/Consent fields are
  invitation-level.

## Goals / Non-Goals

**Goals:**
- Every step (locked or not) can have new admin-authored fields added, and
  every admin-authored field's answer is actually captured on submission —
  closing the gap for Carried Items/custom steps too, not only extending
  the same broken mechanism to Visitor Info/Visit Details.
- A custom field's answer is scoped to the same entity (visitor, vehicle,
  or invitation) its step's existing fields are already scoped to, so
  group-registration semantics stay consistent between seeded and
  admin-authored fields on the same step.

**Non-Goals:**
- Changing how locked/seeded fields themselves are configured, ordered, or
  rendered — only new admin-authored fields and their answers are in scope.
- Cross-field validation *between* a custom field and a seeded field (e.g.
  "this custom field is required only if ID-proof type is X") beyond what
  `form-builder`'s existing per-field visibility-condition/validation-rule
  mechanism already supports.
- A query/reporting UI over custom field answers (e.g. "list all
  invitations where custom field X = Y"). JSONB is fine to store and
  round-trip; ad-hoc querying is left for a future change if a real need
  shows up.
- Retroactively fixing already-submitted invitations that predate this
  change — there is nothing to fix; they simply have no custom field
  answers, same as today.

## Decisions

### Decision 1: `custom_field_values: dict[str, Any]` JSONB, on three models plus one extra column, not a normalized table
Store answers as a JSONB map keyed by field `key`, added to `Invitation`
(invitation-level fields), `InvitationVisitor` (co-visitor's Visitor Info
fields), and `InvitationVehicle` (Vehicle Info fields beyond license
plate). The primary contact is the fourth per-visitor case: its fields
(`primary_contact_full_name`, etc.) already live directly on `Invitation`,
not a child row, so its Visitor Info custom-field answers need their own
column there too — `primary_contact_custom_field_values` — kept separate
from `Invitation.custom_field_values` (which holds only invitation-level
Visit Details/Carried Items/custom-step answers — Consent Agreement is
excluded, see Decision 6) so the two scopes never share a key namespace on
the same row. This is a storage-layout
detail only; the request/response contract (Decision 3) already scopes the
primary contact's answers to its own `customFieldValues` map, identical in
shape to a co-visitor's.

**Alternative considered**: a normalized `invitation_field_answers` table
(one row per answer, FK to whichever entity, field key, typed/JSON value
column). Rejected for now — no current requirement needs to query "which
invitations have custom field X = Y" across the table, and three JSONB
columns keep the read path identical to how `carried_items`/`consents`
already round-trip through `model_validate`/`CamelModel`, with no new join.
Revisit if a reporting requirement on custom-field answers materializes.

### Decision 2: answer scope follows the step's own existing field scope, not a per-field configurable setting
A field's answer scope (visitor/vehicle/invitation) is derived entirely
from which step it belongs to — Visitor Info → visitor, Vehicle Info →
vehicle, everything else → invitation — not a property an admin sets
per-field.

**Alternative considered**: let an admin choose a field's scope explicitly
in the Step Editor. Rejected — it would let an admin create a
Visitor-Info field that's invitation-level (answered once regardless of
visitor count) or a Carried-Items field that's per-visitor, which has no
sensible UI (Carried Items has no per-entity list to attach a per-visitor
answer to) and no product requirement asked for it. Deriving scope from
the step keeps the mental model identical to the step's own seeded fields.

### Decision 3: request contract nests `customFieldValues` at the matching level, not one flat top-level map
`primaryContact`/each `visitors` entry and each `vehicles` entry each get
their own optional `customFieldValues` map; a third map sits at the
request's top level for invitation-scoped fields. All three are validated
against the same branch's effective form, each restricted to only the
field keys belonging to that entity's step-scope.

**Alternative considered**: one flat `customFieldValues: dict[str, Any]` at
the request's top level, disambiguating visitor/vehicle-scoped answers by
namespacing the key (e.g. `visitor_0_employeeId`). Rejected — it leaks an
implementation detail (array index) into the wire contract and makes
per-visitor validation error messages ("visitor 2, field employeeId,
required") awkward to construct; nesting the map inside the existing
per-visitor/per-vehicle payload objects is a direct, obvious extension of
the contract that's already visitor/vehicle-shaped.

### Decision 4: `create_field` drops the fixed-step guard outright, no replacement constraint
`_FIXED_FIELD_SET_STEP_KEYS` is deleted, not replaced by a narrower guard
(e.g. "no more than N custom fields per step" or "no file-upload fields on
Visitor Info"). No product requirement asked for such a limit, and adding
an arbitrary one now would be inventing a constraint the proposal doesn't
call for. If a real limit is needed later (storage size, UI density), it's
a separate change with its own rationale.

### Decision 5: reuse `form-builder`'s existing field-type/validation-rule machinery for answer validation; no new validation DSL
An admin-authored field's answer is validated using the exact same
type/required/`options`/`validationRules` structures `form-builder`
already defines per field (`Requirement: A Field Declares Validation Rules
and Display Width`, `Requirement: Field Types Are Constrained To a
Supported Set`) — the same validation Carried Items/Consent Agreement
answers are already checked against. No new validation concept is
introduced for this change.

### Decision 6: Consent Agreement is excluded from the generic `customFieldValues` invitation-level scope
Discovered during implementation: `form_builder_validation.allowed_consent_keys`/
`required_consent_keys` already iterate *every* field on the Consent
Agreement step — system or admin-authored — and validate it through the
request's existing `consents` map (this is how "Admin adds a custom
consent statement" already worked, unchanged, before this change). If
`custom_fields_for_invitation_scope` also included Consent Agreement's
non-system fields, the same field key would need an answer in both
`consents` and `customFieldValues` at once — an outright contract bug, not
a design tradeoff. `custom_fields_for_invitation_scope` therefore excludes
`consent_agreement` alongside `visitor_info`/`vehicle_info`, leaving that
step's existing mechanism untouched. Every other invitation-scoped step
(Visit Details, Carried Items beyond its own `items` field, any custom
step) has no such pre-existing per-field mechanism, so they route through
`customFieldValues` as originally planned.

## Risks / Trade-offs

- **[Risk]** A tenant with a very large number of custom fields per
  visitor/vehicle could grow `custom_field_values` JSONB rows large enough
  to matter for row size or index bloat. → **Mitigation**: no index is
  placed on the JSONB column (it's never queried by key, only round-tripped
  by the owning invitation/visitor/vehicle id); if this becomes a real
  problem, it surfaces as a storage/perf issue addressable independently of
  this change's contract.
- **[Risk]** `GenericConfiguredStep.tsx`'s answers, previously
  UI-state-only, now flow into a real request payload for the first time —
  any latent type-mismatch between what that component collects and what
  the field's configured type expects (e.g. a date field collected as a
  raw string) would previously have been invisible (nothing consumed the
  value) and could now surface as a 422 at submission time. →
  **Mitigation**: covered by adding an end-to-end test per field type
  through a custom step, per `testing-standards.md` §2's endpoint-level
  coverage expectation, before relying on this path in production.
- **[Risk]** `CarriedItemsStep.tsx`'s existing special-cased `items`
  field key is a real, in-use field on every tenant's seeded Carried Items
  step. Replacing its special-case with the same generic binding every
  other field uses must not change how that field's value is shaped on the
  wire (still the `carried_items: list[str]` column, not routed into the
  new `custom_field_values` map) — the fix is to the *second-field*
  misbinding bug, not to the seeded field's own storage. →
  **Mitigation**: `items` stays hard-mapped to the existing `carried_items`
  column; only a field whose key is anything else routes through
  `custom_field_values`. Covered by a regression test asserting the seeded
  `items` field's request/response shape is unchanged.

## Migration Plan

1. Alembic migration (tenant tree, `alembic_tenant/`) adds
   `custom_field_values` (JSONB, nullable, server default `'{}'`) to
   `invitations`, `invitation_visitors`, and `invitation_vehicles`, applied
   to every existing tenant schema per `database-architecture.md` §5 — pure
   addition, no backfill (existing rows get the default empty map).
2. Backend: remove the `create_field` guard; add answer-validation and
   persistence in `invitations/service.py::create_invitation` and the
   walk-in registration path; extend response schemas.
3. Frontend: fix `CarriedItemsStep.tsx`'s second-field misbinding, wire
   `GenericConfiguredStep.tsx`'s answers into the submission payload, add
   the generic field section to `VisitorInfoStep` (per visitor) and
   `VisitDetailsStep`, extend Vehicle Info's existing per-vehicle section;
   remove the Visitor Info/Visit Details add-field gate in the Step Editor.
4. No feature flag or staged rollout — every change here is additive
   (new optional request fields, a lifted rejection) except the two bug
   fixes (Carried Items second-field misbinding, custom-step answers not
   submitted), which were already producing incorrect/silently-dropped
   behavior, so there is no previously-correct behavior to preserve behind
   a flag.
5. **Rollback**: revert the backend/frontend commits; the added JSONB
   columns can remain in place unused (nullable, defaulted) without further
   migration if a rollback is needed before the next release — no
   destructive down-migration is required for a clean revert.
