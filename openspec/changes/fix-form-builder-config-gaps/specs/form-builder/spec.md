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
reordered among themselves and around the locked ones' fixed positions.

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

## ADDED Requirements

### Requirement: Effective-Form Rendering Reflects Field-Level Active State For Every Step
The visitor-facing and staff-facing registration wizards SHALL render every
step — not only Carried Items and Consent Agreement — by consulting the
calling branch's published effective form for each toggleable field's active
state and requiredness. A toggleable field marked inactive in the published
configuration SHALL NOT be shown or required by the wizard for any step,
and a toggleable field marked active-but-optional SHALL be shown but not
required. Locked fields are unaffected by this requirement — they are
always shown and required regardless of published configuration, per
"System Fields Are Seeded With a Locked or Toggleable Tier."

#### Scenario: Deactivated Visitor Info field is hidden on the visitor form
- **WHEN** a branch's published configuration marks the profile-photo field
  (or ID-proof type/upload) inactive
- **THEN** the visitor-request and staff-registration wizards do not show or
  require that field for that branch, consistent with what the backend
  already accepts

#### Scenario: Deactivated Visit Details field is hidden on the visitor form
- **WHEN** a branch's published configuration marks the expected-duration or
  additional-notes field inactive
- **THEN** the wizards do not show or require that field for that branch

#### Scenario: A non-locked Vehicle Info field's active state is honored
- **WHEN** a branch's published configuration deactivates a non-locked
  Vehicle Info field, or an admin adds a new active field to Vehicle Info
- **THEN** the wizards reflect that field's current active state (hidden if
  inactive, shown if active) the same way Carried Items and Consent
  Agreement fields already do

#### Scenario: Locked field is unaffected
- **WHEN** a branch's published configuration is read for a step containing
  a locked field
- **THEN** the wizard shows and requires that field regardless of any
  attempted configuration, since locked fields cannot be deactivated

### Requirement: Admin UI Exposes Publish State and a Publish Action From Every Draft-Editing Screen
Any admin screen that creates, edits, deletes, or reorders a step's fields
SHALL expose both an indication that the current scope (branch or tenant
default) has unpublished draft changes and a Publish action that applies to
that same scope — not only a screen dedicated to the steps overview. Saving
a draft field or step change SHALL NOT present the caller with messaging
implying the visitor-facing form has already changed; messaging SHALL
distinguish "saved to draft" from "published."

#### Scenario: Field Editor screen shows a Publish action
- **WHEN** an admin is on the field editor screen for a step (having just
  created or edited a field) and the scope has unpublished draft changes
- **THEN** a Publish action for that scope is reachable from that same
  screen without navigating back to the steps overview

#### Scenario: Field save confirmation does not imply the form is already live
- **WHEN** an admin creates or updates a field and the save succeeds
- **THEN** the confirmation communicates the change was saved to the draft
  and that publishing is still required before it affects the visitor-facing
  form

#### Scenario: Publishing from the Field Editor screen updates the effective form
- **WHEN** an admin publishes from the Field Editor screen for a scope with
  unpublished field changes
- **THEN** the same publish behavior occurs as publishing from the steps
  overview screen — the draft is validated, snapshotted, and the scope's
  cached effective form is invalidated
