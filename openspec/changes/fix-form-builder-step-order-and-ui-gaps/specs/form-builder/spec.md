## MODIFIED Requirements

### Requirement: Fields and Steps Are Explicitly Ordered
Each step SHALL have an explicit order among its tenant/branch siblings, and
each field an explicit order among its step siblings. Reordering SHALL
persist the new order without requiring a delete/recreate of any field or
step. A step or field with `isLocked = true` SHALL keep its position
relative to every other locked sibling unchanged by any reorder request; a
reorder request that would change a locked step's or locked field's
position relative to its locked siblings SHALL be rejected with 422 and
leave the current order unchanged. Non-locked steps/fields MAY be freely
reordered among themselves and around the locked ones' fixed positions. A
newly created custom step SHALL be positioned immediately before the
locked trailing run of steps (e.g. before Review & Confirm), never after
it — a locked step's "first two / last" position is an invariant every
step-creating operation upholds, not only something reordering enforces
after the fact.

#### Scenario: Reordering fields persists across reads
- **WHEN** an admin reorders the fields of a step and saves
- **THEN** a subsequent read of that step's fields returns them in the new
  order

#### Scenario: Reordering non-locked steps around locked ones succeeds
- **WHEN** an admin reorders the non-locked steps (e.g. moves Vehicle Info
  before Carried Items) while leaving Visitor Info, Visit Details, and
  Review & Confirm in their existing relative positions
- **THEN** the request succeeds and a subsequent read reflects the new order

#### Scenario: Reorder that repositions a locked step is rejected
- **WHEN** a reorder request would move a locked step (Visitor Info, Visit
  Details, or Review & Confirm) ahead of or behind another locked step
  relative to their current order — including moving a locked step out of
  its current position entirely
- **THEN** the request is rejected with 422 and the steps' order is
  unchanged

#### Scenario: Reorder that repositions a locked field is rejected
- **WHEN** a reorder request for a step's fields would move a locked field
  (e.g. full name) relative to another locked field's current position
- **THEN** the request is rejected with 422 and the fields' order is
  unchanged

#### Scenario: A new custom step lands before the locked trailing run
- **WHEN** an admin creates a new custom step, whether or not any other
  custom step already exists
- **THEN** the new step's position places it immediately before Review &
  Confirm (or before whichever locked step(s) currently form the trailing
  run), never after it, and the locked steps' first-two/last positions are
  unaffected

#### Scenario: A scope whose step order was corrupted before this fix is repaired
- **WHEN** a branch or tenant-default scope has a custom step positioned
  after a locked trailing-run step from before this requirement was
  enforced
- **THEN** the scope's step order is corrected (locked steps returned to
  their first-two/last positions, existing custom steps kept in their
  relative order to each other, positioned before the locked trailing run)
  without any step or field being deleted or its configuration otherwise
  changed

## ADDED Requirements

### Requirement: Only Fully Configurable Steps Accept New Admin-Authored Fields
Creating a new field SHALL be accepted only for a "fully configurable" step
— Carried Items, Vehicle Info, Consent Agreement, or any custom step.
Visitor Info and Visit Details carry only their fixed, seeded set of
locked/toggleable fields (per "System Fields Are Seeded With a Locked or
Toggleable Tier"); a request to create a new field on either SHALL be
rejected with 422, distinct from the existing per-field locked-field
update rejection.

#### Scenario: Creating a field on Visitor Info is rejected
- **WHEN** an admin submits a field-creation request targeting the Visitor
  Info step
- **THEN** the request is rejected with 422 and no field is created

#### Scenario: Creating a field on Visit Details is rejected
- **WHEN** an admin submits a field-creation request targeting the Visit
  Details step
- **THEN** the request is rejected with 422 and no field is created

#### Scenario: Creating a field on a fully configurable step still succeeds
- **WHEN** an admin submits a field-creation request targeting Carried
  Items, Vehicle Info, Consent Agreement, or a custom step
- **THEN** the request succeeds as before, unaffected by this restriction
