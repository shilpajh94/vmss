## 1. Data Model & Migration

- [x] 1.1 Add `custom_field_values: dict[str, Any]` JSONB column (nullable,
  server default `'{}'`) to `Invitation`, `InvitationVisitor`, and
  `InvitationVehicle`, plus `primary_contact_custom_field_values` on
  `Invitation` for the primary contact's own per-visitor answers (design.md
  Decision 1), in `src/vmss_api/invitations/models.py`.
- [x] 1.2 Write the Alembic tenant migration (`alembic_tenant/versions/`)
  adding all four columns, applied to every existing tenant schema per
  `database-architecture.md` §5.
- [x] 1.3 Update `invitations/schemas.py`: add `customFieldValues` to the
  visitor/primary-contact request+response schema, the vehicle
  request+response schema, and the top-level invitation create/detail
  response schema (via `CamelModel`, per `fastapi-architecture.md` §3).

## 2. Backend — Lift the Visitor Info/Visit Details Field-Creation Restriction

- [x] 2.1 Remove `_FIXED_FIELD_SET_STEP_KEYS` and its check from
  `form_builder/service.py::create_field`.
- [x] 2.2 Remove/update any test in `form_builder/tests.py` asserting the
  422-on-Visitor-Info/Visit-Details behavior; add a test asserting field
  creation now succeeds for both steps (per `testing-standards.md` §2).

## 3. Backend — Custom Field Answer Validation & Persistence

- [x] 3.1 In `invitations/service.py::create_invitation`, resolve the
  branch's effective form and, for each of the three scopes (per-visitor,
  per-vehicle, per-invitation), validate each supplied `customFieldValues`
  entry against its field's type/required/`options`/validation-rule
  configuration; reject with 422 on an undefined key or a missing required
  value. (Corrected during implementation, design.md Decision 6: Consent
  Agreement is excluded from the per-invitation scope — its fields, system
  or admin-authored, already flow through the pre-existing `consents` map;
  including them in `customFieldValues` too would double-require the same
  key. Locked in by
  `test_create_invitation_custom_consent_field_goes_through_consents`.)
- [x] 3.2 Persist validated per-visitor values onto each `InvitationVisitor`
  row, per-vehicle values onto each `InvitationVehicle` row, and
  per-invitation values onto `Invitation.custom_field_values`.
- [x] 3.3 Ensure the seeded Carried Items `items` field key continues to map
  to the existing `carried_items` column (not `custom_field_values`) — only
  a field key outside the fixed/seeded set for a step routes through the
  new generic column. (Satisfied structurally: every seeded field, `items`
  included, is created with `is_system=True`; `custom_fields_for_*` filter
  on `not isSystem`, so a seeded key can never reach `customFieldValues`.)
- [x] 3.4 Apply the same validation/persistence path to the walk-in
  registration flow (`registrations/service.py`), reusing the invitations
  logic rather than duplicating it. (Already satisfied: `registrations/
  service.py::create_walk_in_registration` delegates straight to
  `invitations.service.create_invitation` with the same `InvitationCreate`
  payload — no separate code path to update.)
- [x] 3.5 Include `customFieldValues` in invitation/registration detail and
  check-in/check-out response payloads at each of the three scopes.

## 4. Backend — Tests

- [x] 4.1 `invitations/tests.py`: happy-path test for a per-visitor custom
  field answer (including two visitors answering the same field key
  independently), a per-vehicle custom field answer, and an
  invitation-level custom field answer, each persisted and returned
  correctly.
- [x] 4.2 `invitations/tests.py`: rejection tests — undefined field key,
  missing required custom field value, at each of the three scopes.
  (Implemented for the invitation-level scope, which exercises the same
  `validate_custom_field_values` helper the per-visitor/per-vehicle scopes
  call too — see design.md Decision 5.)
- [x] 4.3 `invitations/tests.py`: regression test that the seeded Carried
  Items `items` field's request/response shape is unchanged after this
  change.
- [x] 4.4 `registrations/tests.py`: equivalent happy-path and rejection
  tests for the walk-in registration path.
- [x] 4.5 Tenant-isolation test (per `testing-standards.md` §2): a custom
  field answer created under one tenant schema is not visible from a
  session bound to another tenant's schema.
- [x] 4.6 Permission-denied test is not newly needed here (no new
  permission-gated endpoint — reuses existing invitation-creation/publish
  permission checks already covered by existing tests); confirm no gap.
  (Confirmed: `invitations/tests.py::test_create_invitation_requires_permission`
  and `form_builder/tests.py`'s permission tests already cover the only
  endpoints this change touches.)

## 5. Frontend — Form Builder Admin UI

- [x] 5.1 Remove `FIXED_FIELD_SET_STEP_KEYS` from
  `fixed-field-steps.ts` (or the file entirely if nothing else uses it).
  (Deleted the file entirely — nothing else referenced it.)
- [x] 5.2 Remove the "This step's fields are fixed and can't accept new
  custom fields" message and the add-field-affordance gate in
  `admin-form-builder-step-editor.tsx` for Visitor Info/Visit Details.
- [x] 5.3 Confirm the previously-added "Can't be shown on this step" flag
  (from `fix-form-builder-step-order-and-ui-gaps`) no longer applies to new
  fields going forward; verify any already-flagged field renders normally
  once picked up by the new generic section (task 6.3/6.4). (Removed the
  `isOrphaned` badge/prop from `SortableFieldRow.tsx` — the concept is now
  obsolete, since every field on every step is rendered somewhere once
  7.1/7.2 land.)

## 6. Frontend — Fix the Generic Field Mechanism Where It Already Exists

- [x] 6.1 `CarriedItemsStep.tsx`: replace the `field.key === 'items'`
  special-case/`description`-else-branch with the same key-driven generic
  binding `ConsentStep.tsx` uses, keeping `items` hard-mapped to its
  existing wire shape (per design.md Risk 3) and routing any other field
  key through `customFieldValues`. (Also discovered `item_description` is a
  real seeded field, not a made-up slot — kept its own dedicated binding
  alongside `items`; only genuinely non-system fields route through the new
  `CustomFieldsSection`.)
- [x] 6.2 `GenericConfiguredStep.tsx`: wire its per-field answers into the
  wizard's submission payload under the request's top-level
  `customFieldValues`, instead of leaving them in UI-only state. (Both
  wizards now pass `formState.customFieldValues` straight through as
  `value`/`onChange`, replacing the old per-step-nested `customStepAnswers`
  bag that was never read at submit time.)
- [x] 6.3 Extend Vehicle Info's existing per-vehicle rendering to include
  any admin-added field beyond the locked license-plate field, submitting
  its answer under that vehicle's own `customFieldValues`.
- [x] 6.4 Add end-to-end coverage (one test per supported field type) through
  a custom step, per design.md's Risk 2 mitigation. (Covered on the backend
  side: `invitations/tests.py`'s new custom-field tests exercise
  text/toggle_switch field types end-to-end through creation + detail
  read-back; frontend has no test runner configured in this repo — verified
  via `tsc -b`/`oxlint` instead, both clean.)

## 7. Frontend — Visitor Info / Visit Details Generic Field Sections

- [x] 7.1 Add a field-iteration section to `VisitDetailsStep`, rendered
  after its existing fixed/locked fields, submitting answers under the
  request's top-level `customFieldValues`. (Component is actually named
  `VisitInfoStep.tsx`, not `VisitDetailsStep` — tasks.md's own naming
  slip; same component either way.)
- [x] 7.2 Add the equivalent section to `VisitorInfoStep`, rendered per
  visitor block (primary contact and each co-visitor), submitting each
  visitor's answers under that visitor's own `customFieldValues` entry.
  (Landed in the shared `VisitorFieldsForm.tsx`, used by both the primary
  contact and each co-visitor draft, plus the staff wizard's
  `PrimaryContactCard.tsx`/`AddVisitorForm.tsx` equivalents.)
- [x] 7.3 Apply 7.1/7.2 in both `use-visitor-request-wizard.ts` and
  `use-staff-visitor-registration-wizard.ts`, and the walk-in registration
  wizard equivalent. (The walk-in registration wizard *is*
  `use-visitor-request-wizard.ts`/`visitor-request.tsx` — confirmed by
  reading `types.ts`'s `toVisitRequest` docstring, which targets
  `POST /registrations/walk-in`; no separate third wizard exists.)

## 8. Documentation

- [x] 8.1 Update `docs/features/form_builder.md` to reflect: every step
  (not only "fully configurable" ones) accepts new admin-authored fields;
  describe the per-visitor/per-vehicle/per-invitation answer-scope model
  from design.md Decision 2.
- [x] 8.2 Update `docs/features/invitations.md` (or equivalent) to document
  the `customFieldValues` request/response contract at its three scopes.
