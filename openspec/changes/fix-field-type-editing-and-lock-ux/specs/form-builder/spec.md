## ADDED Requirements

### Requirement: A Content-Only Field's List Row Shows No Required Control
A step's field list SHALL NOT render a Required control for a field whose
type is content-only (`static_text`) — such a field collects no answer and
can never be marked required, so no row-level control should imply
otherwise.

#### Scenario: A static_text field's row has no Required checkbox
- **WHEN** an admin views a step's field list containing an active
  `static_text` field
- **THEN** that field's row renders no Required checkbox or toggle,
  consistent with the "Add New Custom Field" modal and Field Properties
  panel already omitting it for this type

#### Scenario: Every other field type's row is unaffected
- **WHEN** an admin views a step's field list containing fields of any
  type other than `static_text`
- **THEN** each of those rows continues to render its Required
  checkbox exactly as before

### Requirement: An Admin-Authored Field's Type Can Be Changed After Creation
The Field Properties panel SHALL let an admin change an existing,
admin-authored (non-system) field's type after creation, re-validating the
field's other properties against the resulting type using the same rules
enforced at field creation. A system-seeded field's type (whether locked or
toggleable) SHALL remain fixed — it is not offered as an editable control —
since it is keyed into fixed, structural application code and database
columns that a type switch cannot safely repoint.

#### Scenario: Admin changes an existing custom field's type
- **WHEN** an admin selects a different field type for an existing,
  admin-authored field in the Field Properties panel and saves
- **THEN** the field's type is updated to the new value

#### Scenario: A system field's type cannot be changed
- **WHEN** an admin opens the Field Properties panel for a system-seeded
  field (locked or toggleable)
- **THEN** the Field Type control is disabled, and no field-type change for
  it can be submitted

#### Scenario: Changing a field's type to an option-required type without options is rejected
- **WHEN** an admin changes an existing field's type to `dropdown_select` or
  `checkbox_list` and the field has no non-empty `options` list (neither
  already saved nor supplied in the same update)
- **THEN** the request is rejected, matching the same rule enforced at
  field creation

#### Scenario: Changing a field's type away from an option-bearing type clears its options
- **WHEN** an admin changes an existing `dropdown_select` or
  `checkbox_list` field to a type that isn't option-bearing
- **THEN** the field's `options` are cleared, since they no longer apply to
  the new type

#### Scenario: Changing a field's type to static_text re-checks its required/content constraints
- **WHEN** an admin changes an existing field's type to `static_text` while
  it is still marked required, or while it has no description/body content
- **THEN** the request is rejected, matching the same constraints enforced
  when a `static_text` field is created

#### Scenario: Changing a field's type away from static_text lifts those constraints
- **WHEN** an admin changes an existing `static_text` field to a different
  type
- **THEN** the field may subsequently be marked required and no longer
  needs a description, the same as any other field of the new type

### Requirement: The Lock/Unlock Control Reads as a Single Unambiguous Action
The Field Properties panel's Lock/Unlock control for a locked field SHALL
be a single button whose label states only the action it performs: "Unlock
to Edit" while the field's editable controls are disabled, and "Lock" once
the admin has unlocked them for editing.

#### Scenario: A newly-opened locked field's control reads "Unlock to Edit"
- **WHEN** an admin opens the Field Properties panel for a locked field
  that has not yet been unlocked for editing
- **THEN** the control shows a single button labeled "Unlock to Edit"

#### Scenario: An unlocked-for-editing field's control reads "Lock"
- **WHEN** an admin has selected "Unlock to Edit" on a locked field
- **THEN** the same control now shows a single button labeled "Lock"
