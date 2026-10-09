## Why

Manual testing after `fix-form-builder-config-gaps` surfaced four more
issues, all traced to concrete root causes:

1. **Reordering steps throws "Something went wrong reordering steps."**
   `form_builder/service.py::create_step` computes a new custom step's
   position as `max(all order_index) + 1` — i.e. unconditionally *after*
   Review & Confirm, the locked step that's supposed to always be last.
   Once two custom steps exist (the reporter's "test"/"test 2"), Review &
   Confirm is no longer positionally last; the admin UI's step-partitioning
   logic (added in `fix-form-builder-config-gaps`, which scans for a
   contiguous run of locked steps at the *end* of the list) then
   misidentifies Review & Confirm as part of the freely-reorderable middle
   group. Any drag submits a payload that moves Review & Confirm relative to
   its actual current position, which the backend's locked-position guard
   (also from `fix-form-builder-config-gaps`) correctly rejects with 422 —
   surfaced to the admin as a generic reorder failure. This is a pre-existing
   step-ordering bug from the original `form-builder` change; it was never
   observable before because nothing validated reorder positions until
   `fix-form-builder-config-gaps` shipped that guard.
2. **8 configured steps, only 5 shown on the visitor form.** Consistent with
   #1: two custom steps created after Review & Confirm, and (per the
   screenshot) never published — `GET /form-builder/effective` only ever
   reflects the last published snapshot, and nothing in the reporter's
   screenshots shows a successful publish after creating them. Fixing #1
   (so a new custom step always lands *before* the locked trailing run, not
   after it) also removes the confusing "Review & Confirm isn't actually
   last" state that would otherwise persist even after publishing.
3. **No wrapping/scrolling on the staff wizard's step bar.**
   `RegistrationStepper.tsx` renders every step's number + label in one
   `flex` row with `whitespace-nowrap` and no wrap or horizontal-scroll
   fallback. It happens to fit for five or six steps; with eight (or more,
   once an admin adds custom steps) labels get crowded/cut off with no
   layout escape hatch — the "no spacing" the reporter is seeing. The public
   wizard's `StepSidebar.tsx` is a vertical list and has no equivalent
   problem.
4. **A custom field added to Visitor Info is silently accepted, never
   shown, anywhere.** `form_builder/service.py::create_field` has no
   restriction on which step a custom field can be added to — it happily
   creates a field on Visitor Info or Visit Details, even though those two
   steps were designed (per the original `form-builder` spec) to only ever
   carry their fixed set of locked/toggleable fields; only Carried Items,
   Vehicle Info, Consent Agreement, and custom steps are "fully
   configurable." Because Visitor Info/Visit Details render fixed JSX driven
   by known field keys (not the generic field-list renderer), an
   admin-authored field there has nowhere to ever appear — not a visibility
   bug, a structurally unsupported operation the UI/API currently pretend to
   support. Confirmed with the user: the fix is to make this explicit
   (reject it) rather than build full dynamic-field support for these two
   steps, which would be a much larger change touching invitation storage
   and the wizard's rendering model.

A fifth reported symptom — "I haven't seen active/inactive buttons for the
fields" — traces to real code (`FieldPropertiesPanel.tsx`'s `Active` toggle,
rendered for any non-locked field), but its placement buried inside a
"Validation Rules" section, with no visual treatment resembling the
step-level Active/Inactive control the reporter already recognizes from the
Steps overview page, is a legitimate discoverability problem independent of
whether it technically renders. Addressed by giving it the same visual
treatment as the step-level toggle, pulled out of "Validation Rules" into
its own clearly-labeled control.

## What Changes

- **Backend — insert new custom steps before the locked trailing run.**
  `create_step` computes its `order_index` as one past the last *non-locked*
  step (or, if none exist, before the first locked step in the trailing
  run) instead of past every step — new custom steps land immediately
  before Review & Confirm, preserving "locked steps stay first-two/last" as
  an invariant `create_step` itself upholds, not just something reorder
  enforces after the fact.
- **Backend — one-time backfill for already-corrupted step orders.** Any
  tenant/branch scope that already has a custom step positioned after a
  locked step (the state the reporter is in right now) gets its step
  `order_index` values renumbered on next access so locked steps return to
  their correct first-two/last positions and existing custom steps sort
  immediately before Review & Confirm, preserving their relative order to
  each other. No data is lost — this only touches ordering.
- **Backend — reject a custom field on Visitor Info or Visit Details.**
  `create_field` gains a check: for a step whose `key` is `visitor_info` or
  `visit_details` (locked-tier steps, not "fully configurable"), only
  updating existing seeded fields is allowed — creating a *new* field is
  rejected with 422 and a clear message. Carried Items, Vehicle Info,
  Consent Agreement, and any custom step are unaffected.
- **Frontend — disable "Add New Custom Field" on Visitor Info/Visit
  Details.** The Field Editor page hides (or disables, with an explanatory
  tooltip) the add-field affordance when the current step is one of these
  two, matching the new backend rejection instead of only discovering it
  after a failed/silently-ignored submit.
- **Frontend — flag, don't auto-delete, the already-created orphaned "test"
  field.** An existing field on Visitor Info/Visit Details that isn't part
  of `defaults.py`'s seeded set (i.e., one that slipped through before this
  fix) gets a visible "this field can't be shown on this step" label in the
  Field Editor, so the admin can delete it themselves via the existing
  per-field delete control — deleting admin-created data automatically as a
  side effect of this deploy isn't something to do without an explicit
  action from the admin, even though the field is functionally inert.
- **Frontend — fix the step drag-and-drop partition to not assume strict
  contiguity.** `partitionSteps` (from `fix-form-builder-config-gaps`)
  is corrected to identify locked steps by their actual positions rather
  than a "trailing contiguous run" scan, so it stays correct even before the
  backfill runs or if some other future state briefly violates the
  invariant — defense in depth alongside the backend fix, not a replacement
  for it.
- **Frontend — make the staff wizard's step bar handle more steps.**
  `RegistrationStepper.tsx` gets a horizontal-scroll fallback (matching how
  the public wizard's page already handles arbitrarily many steps by being
  vertical) so an 8+ step configuration degrades to "scroll to see more,"
  not "crowd everything into unreadable overlap."
- **Frontend — make the field-level Active toggle visually match the
  step-level one.** Move it out of the "Validation Rules" box in
  `FieldPropertiesPanel.tsx` into its own small, clearly-labeled
  Active/Inactive control at the top of the panel, the same visual language
  the Steps overview page's `StepCard` already uses.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `form-builder`: adds a requirement that a newly created step is
  positioned before the locked trailing run (not merely that reordering it
  later is rejected); adds a requirement that only "fully configurable"
  steps (Carried Items, Vehicle Info, Consent Agreement, custom steps)
  accept new admin-authored fields — Visitor Info and Visit Details do not.

## Impact

- **API**: `src/vmss_api/form_builder/service.py` (`create_step`,
  `create_field`, a small backfill helper), `src/vmss_api/form_builder/tests.py`.
  No schema/migration changes — ordering backfill is a data fix via existing
  columns, not a new column.
- **Web**: `admin-form-builder.tsx` (`partitionSteps`),
  `admin-form-builder-step-editor.tsx`/`AddFieldModal` (disable add-field for
  Visitor Info/Visit Details), `RegistrationStepper.tsx` (scroll fallback),
  `FieldPropertiesPanel.tsx` (Active toggle placement).
- **No breaking changes**: the field-creation restriction only blocks an
  operation that already didn't work (silently discarded data); the step
  reordering fix is corrective, not a new constraint beyond what
  `fix-form-builder-config-gaps` already established.
