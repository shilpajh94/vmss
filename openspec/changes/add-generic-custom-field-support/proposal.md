## Why

An admin adding a custom field to the Visitor Info step gets "This step's
fields are fixed and can't accept new custom fields" (`form_builder/
service.py::create_field`'s `_FIXED_FIELD_SET_STEP_KEYS` guard, reported via
screenshot of the Step Editor). That restriction was deliberate — added in
the not-yet-archived `fix-form-builder-step-order-and-ui-gaps` change — on
the reasoning that Visitor Info/Visit Details render fixed JSX by known
field keys, not the generic field-list renderer, so a custom field there had
nowhere to appear. Investigating whether to simply lift that restriction
surfaced a bigger gap: the generic field mechanism it would reuse doesn't
actually work end-to-end for the steps that already have it. Carried Items
special-cases exactly one field key (`items`) and silently misbinds any
second custom field to a `description` slot; a custom step's field answers
are held in wizard UI state and are never included in the submission
payload at all; and no generic value-storage column exists anywhere — the
`custom_field_values` JSONB column planned for this in the original
`form-builder` change's design (Decision 4) was never built. So "every step
can add, edit, or delete non-mandatory custom fields" requires building the
generic custom-field value mechanism for real, not just removing one guard.

Custom field answers are scoped to the same entity their step's existing
fields already scope to, not lumped into one invitation-wide bag: Visitor
Info's existing fields (full name, email, category) are already
per-visitor — each entry in `visitors`/`primaryContact` carries its own —
so a new Visitor Info custom field is answered per-visitor too. Vehicle
Info's fields are already per-vehicle, so a new Vehicle Info custom field
(beyond the locked license-plate field) is answered per-vehicle. Visit
Details, Carried Items, Consent Agreement, and custom steps have no such
per-entity structure today, so their custom fields remain invitation-level,
one shared answer per invitation.

## What Changes

- **Backend — generic custom-field value storage, scoped per entity.** Add
  `custom_field_values: dict[str, Any]` (JSONB) to three models:
  `Invitation` (Visit Details/Carried Items/custom-step answers — Consent
  Agreement is excluded, see design.md Decision 6 — mirroring the abandoned
  Decision 4 plan), `InvitationVisitor` (Visitor
  Info answers, one map per visitor row — new, not part of the original
  Decision 4 plan), and `InvitationVehicle` (Vehicle Info answers, one map
  per vehicle row — matches Decision 4's original scope). Walk-in
  registration (`registrations/`) reuses the same columns via its shared
  invitation-record contract.
- **Backend — accept and validate custom-field answers on create.**
  `invitations/service.py::create_invitation` (and the walk-in registration
  path) resolves the branch's effective form and accepts three
  `customFieldValues` maps at the matching contract level: one per entry in
  `primaryContact`/`visitors` (Visitor Info fields), one per entry in
  `vehicles` (Vehicle Info fields), and one at the request's top level
  (Visit Details/Carried Items/custom-step fields — Consent Agreement's
  fields, including admin-authored ones, continue to flow through the
  existing `consents` map instead). Each supplied
  value is validated against its field's type/required/validation rules —
  including for Visitor Info and Visit Details fields, once admin-authored
  ones can exist there — and persisted onto the matching entity. A value for
  a field the effective form doesn't define at that entity's step, or a
  missing value for a currently-required custom field, is rejected with
  422.
- **Backend — lift the Visitor Info/Visit Details field-creation
  restriction.** Remove `_FIXED_FIELD_SET_STEP_KEYS` from
  `form_builder/service.py::create_field` — every step (locked or not)
  accepts new admin-authored fields the same way Carried Items/Vehicle
  Info/Consent Agreement/custom steps already do. The step's own *seeded*
  locked/toggleable fields (full name, email-or-phone, category, purpose,
  host, etc.) are unaffected — this only changes whether a *new* field can
  be added alongside them, not their own locked behavior.
- **Frontend — real generic field rendering for Carried Items and custom
  steps.** `CarriedItemsStep.tsx` drops its `field.key === 'items'`
  special-case/`description` else-branch in favor of the same
  key-driven-generic binding `ConsentStep.tsx` already uses.
  `GenericConfiguredStep.tsx`'s per-field answers stop being wizard-only UI
  state and get included in the submission payload under
  `customFieldValues`.
  `VisitDetailsStep` gains a field-iteration section, inserted after its
  existing fixed/locked fields, that renders any admin-added custom field
  and includes its answer in the request's top-level `customFieldValues`.
  `VisitorInfoStep` gains the equivalent section rendered per visitor
  (primary contact and each co-visitor block, matching how full
  name/email/category already render per visitor), with each visitor's
  answers included under that visitor's own `customFieldValues` entry.
  Vehicle Info's per-vehicle section (already generic) is extended the same
  way for any new admin-added field beyond the locked license-plate field.
- **Frontend — enable "Add New Custom Field" on Visitor Info/Visit
  Details.** `fixed-field-steps.ts`'s `FIXED_FIELD_SET_STEP_KEYS` is removed;
  `admin-form-builder-step-editor.tsx` no longer shows the "fields are
  fixed" message or hides the add-field affordance for these two steps.
- **Frontend — existing orphaned "flagged" field becomes normal.** The
  "Can't be shown on this step" label added by `fix-form-builder-step-order-
  and-ui-gaps` for a pre-existing orphaned field on Visitor Info/Visit
  Details no longer applies going forward (new fields render normally); any
  already-flagged field from before this change is unaffected by this
  change alone and continues to render once picked up by the new generic
  section, since it was always a validly-configured field — only its
  *rendering path* was missing, not its configuration.
- **Supersedes a pending requirement.** This change replaces the "Only Fully
  Configurable Steps Accept New Admin-Authored Fields" requirement added by
  `fix-form-builder-step-order-and-ui-gaps` (itself not yet archived) with
  the opposite: every step accepts new admin-authored fields, backed by a
  real value-storage/rendering mechanism instead of the fixed-JSX rendering
  that made the original restriction necessary.

No changes to step/field ordering, locking of *existing* seeded fields,
publish/draft semantics, or permission gating — this only concerns whether a
*new* custom field can be added to a step and whether its answer is actually
captured end-to-end.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `form-builder`: reverses "Only Fully Configurable Steps Accept New
  Admin-Authored Fields" (added by the not-yet-archived
  `fix-form-builder-step-order-and-ui-gaps`) — every step, including
  Visitor Info and Visit Details, now accepts new admin-authored fields.
  Strengthens "Fully Configurable Steps Accept Admin-Authored Fields" (from
  the not-yet-archived `form-builder` change) to require that an
  admin-authored field's answer is actually captured on submission, not only
  that its definition can be created and published.

  Note: as with the prior two form-builder fix changes, `form-builder` has
  not been archived yet, so `openspec/specs/form-builder/spec.md` does not
  exist in the main specs tree. This delta is written against the
  accumulated requirement text across `openspec/changes/form-builder/specs/
  form-builder/spec.md`, `openspec/changes/fix-form-builder-config-gaps/
  specs/form-builder/spec.md`, and `openspec/changes/
  fix-form-builder-step-order-and-ui-gaps/specs/form-builder/spec.md` — the
  closest available source of truth for what's actually implemented/pending
  — and will need all four form-builder changes archived together (in
  creation order) for `openspec archive` to apply cleanly.
- `invitations`: adds a requirement that invitation creation captures
  admin-defined custom field answers (`customFieldValues`) at the
  matching per-visitor, per-vehicle, or per-invitation scope, for any field
  the branch's published form defines beyond the fixed contract fields,
  validated against that field's configuration.
- `registrations`: notes that walk-in registration's shared payload shape
  (`Requirement: Walk-in registration accepts the same visit-record
  contract as staff pre-registration`) now also includes the same
  per-visitor/per-vehicle/per-invitation `customFieldValues` maps,
  consistent with invitation creation.

## Impact

- **API**: `src/vmss_api/invitations/models.py` (new `custom_field_values`
  JSONB column + migration on `Invitation`, `InvitationVisitor`, and
  `InvitationVehicle`), `invitations/service.py`, `invitations/schemas.py`
  (`customFieldValues` on the invitation, visitor, and vehicle
  request/response schemas), `form_builder/service.py` (`create_field`
  guard removed), `registrations/service.py` (shared validation path),
  `form_builder/tests.py`, `invitations/tests.py`, `registrations/tests.py`
  (new/updated test cases per `testing-standards.md`).
- **Web**: `admin-form-builder-step-editor.tsx`, `fixed-field-steps.ts`
  (remove the fixed-set gate); `CarriedItemsStep.tsx`, `ConsentStep.tsx`
  (shared generic binding), `GenericConfiguredStep.tsx` (wire answers into
  submission), `VisitorInfoStep`/`VisitDetailsStep` (new generic field
  section) in both `use-visitor-request-wizard.ts` and
  `use-staff-visitor-registration-wizard.ts`; the walk-in registration
  wizard equivalent.
- **Database**: new nullable JSONB column on `Invitation`,
  `InvitationVisitor`, and `InvitationVehicle` (Alembic migration, tenant
  schema tree per `database-architecture.md` §5) — additive, no
  backfill required (defaults to empty map).
- **No breaking changes**: `customFieldValues` is a new optional request/
  response field; existing submissions without it are unaffected. Lifting
  the Visitor Info/Visit Details field-creation restriction only permits an
  operation that previously returned 422 — no previously-succeeding request
  is affected.
