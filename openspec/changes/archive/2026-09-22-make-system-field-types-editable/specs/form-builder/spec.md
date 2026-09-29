## ADDED Requirements

### Requirement: A System Field's Type Is Editable Unless Its Value Backs a Structurally-Typed Consumer
The Field Properties panel's Field Type control SHALL be editable for a
system-seeded (`isSystem: true`) field unless that field's key is one
whose value is consumed elsewhere in the system as a specific structured
type rather than rendered as a plain form input: `email`, `phone`,
`preferredContactMethod`, `registrationType`, `preferredVisitDate`,
`preferredVisitTime`, `idProofUpload`, `profilePhoto`, and
`visitorCategory`. For every other system field, changing its type SHALL
re-validate the field's resulting state against the same type-dependent
constraints already enforced for an admin-authored field's type change
(a resulting option-required type needs a non-empty `options` list; a
resulting `static_text` type cannot be required and needs body content;
changing away from an option-bearing type clears stored `options`).

#### Scenario: Admin changes a retypeable system field's type
- **WHEN** an admin changes an existing system field such as "Purpose of
  Visit" from `text` to `dropdown_select` and supplies a non-empty
  `options` list in the same request
- **THEN** the field's type and options are updated and persisted

#### Scenario: Admin changes a retypeable, already option-bearing system field's type
- **WHEN** an admin changes "ID Proof Type" or "Vehicle Type" (already
  `dropdown_select`) to `checkbox_list`, keeping their existing options
- **THEN** the field's type is updated

#### Scenario: Changing a retypeable system field to an option-required type without options is rejected
- **WHEN** an admin changes a retypeable system field's type to
  `dropdown_select` or `checkbox_list` and it has no non-empty `options`
  list, neither already saved nor supplied in the same update
- **THEN** the request is rejected, matching the rule already enforced for
  admin-authored fields and for field creation

#### Scenario: Admin attempts to change an excluded system field's type
- **WHEN** an admin attempts to change the `field_type` of `email`,
  `phone`, `preferredContactMethod`, `registrationType`,
  `preferredVisitDate`, `preferredVisitTime`, `idProofUpload`,
  `profilePhoto`, or `visitorCategory`
- **THEN** the request is rejected and the field's type is unchanged

#### Scenario: A toggleable retypeable system field's type is editable without unlocking
- **WHEN** an admin opens the Field Properties panel for a toggleable
  (not locked), retypeable system field such as "ID Proof Type" or
  "Additional Notes"
- **THEN** the Field Type control is enabled without any unlock step,
  consistent with that field's other properties already being editable
  without unlocking

### Requirement: A Locked System Field's Field Type Control Is Gated Behind the Unlock Affordance
For a locked, retypeable system field, the Field Properties panel's Field
Type control SHALL be disabled by default and SHALL become editable only
once the admin selects "Unlock to Edit" on that field, the same way the
panel already gates that field's Label, Placeholder, Description, and
Options controls.

#### Scenario: A locked field's Field Type control starts disabled
- **WHEN** an admin opens the Field Properties panel for a locked,
  retypeable system field (e.g. "Full Name") that has not been unlocked
  for editing
- **THEN** the Field Type control is disabled

#### Scenario: Unlocking a locked field enables its Field Type control
- **WHEN** an admin selects "Unlock to Edit" on a locked, retypeable
  system field
- **THEN** the Field Type control becomes enabled alongside that field's
  Label, Placeholder, Description, and Options controls

#### Scenario: Re-locking discards an unsaved type change
- **WHEN** an admin has unlocked a locked field, changed its Field Type
  selection, and then re-locks the field or selects a different field
  without saving
- **THEN** the unsaved Field Type change is discarded and the panel
  returns to its default disabled state for that field

### Requirement: The Field Type Explanation Names the Specific Reason a Field's Type Is Fixed
When the Field Type control is disabled because the field is one of the
excluded structurally-typed system fields, the Field Properties panel
SHALL show inline text explaining the specific reason for that field,
rather than one generic "default system field" message applied uniformly
to every system field.

#### Scenario: Admin opens an excluded field's properties
- **WHEN** an admin opens the Field Properties panel for `email` (or any
  other excluded field)
- **THEN** the Field Type control is disabled and the inline text
  explains the specific reason (e.g. that the value must remain a
  deliverable email address for notification dispatch to reach the
  visitor), not a generic system-field message

#### Scenario: Admin opens a retypeable system field's properties
- **WHEN** an admin opens the Field Properties panel for a retypeable
  system field, whether locked or toggleable
- **THEN** no "type can't be changed" explanatory text renders, since the
  control is either directly editable or editable once unlocked
