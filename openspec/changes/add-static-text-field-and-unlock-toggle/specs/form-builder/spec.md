## ADDED Requirements

### Requirement: A `static_text` Field Renders Admin-Authored Content With No Input Control
The system SHALL support a `static_text` field type whose `label` is
displayed as a heading and whose `help_text`/description is displayed as
its full body content, on both the staff and visitor registration forms.
A `static_text` field SHALL NOT present any input control, and SHALL NOT
be included in what a visitor/staff submission is expected or permitted to
supply a value for.

#### Scenario: Admin creates a static_text field for Terms & Conditions
- **WHEN** an admin creates a field of type `static_text` on the Consent
  Agreement step with a label of "Terms & Conditions" and a description
  containing the agreement text, and publishes
- **THEN** the field appears in the branch's effective form as a
  `static_text` field carrying that label and description, with no options
  and `isRequired` set to `false`

#### Scenario: A static_text field renders as a heading and body, not an input
- **WHEN** a visitor or staff member reaches a step containing an active
  `static_text` field
- **THEN** the field's label renders as a heading and its description
  renders as body content beneath it, and no text box, checkbox, dropdown,
  or other input control renders for that field

#### Scenario: A submission is not expected to supply a value for a static_text field
- **WHEN** a visitor or staff member submits a step containing a
  `static_text` field without including any value for that field's key
- **THEN** the submission is accepted on the same terms as if the
  `static_text` field were absent — its presence does not cause a
  "missing required field" rejection

### Requirement: A `static_text` Field Cannot Be Marked Required and Must Declare Body Content
Since a `static_text` field collects no answer, the system SHALL reject
any attempt to create or update one with `isRequired` set to `true`, and
SHALL require a non-empty description at creation time (a content block
with a heading and no body serves no purpose).

#### Scenario: Creating a static_text field as required is rejected
- **WHEN** an admin attempts to create a field of type `static_text` with
  `isRequired` set to `true`
- **THEN** the request is rejected and no field is created

#### Scenario: Marking an existing static_text field as required is rejected
- **WHEN** an admin attempts to update an existing `static_text` field's
  `isRequired` to `true`
- **THEN** the request is rejected and the field's `isRequired` remains
  `false`

#### Scenario: Creating a static_text field with no description is rejected
- **WHEN** an admin attempts to create a field of type `static_text` with
  no description (or a blank one)
- **THEN** the request is rejected

### Requirement: A Locked Field Can Be Unlocked to Edit Its Label, Placeholder, Description, and Options
The Field Properties panel SHALL provide a Lock/Unlock control for any
`isLocked` field, defaulting to locked (matching today's behavior: Label,
Placeholder, Description, and — for an option-bearing field — the Options
editor are disabled). Selecting "Unlock to Edit" SHALL enable those same
controls for that field, allowing the admin to change and save its label,
placeholder, description, and (if applicable) its options, the same as an
unlocked field.

#### Scenario: Admin unlocks a locked field to edit its label
- **WHEN** an admin opens the Field Properties panel for a locked field,
  selects "Unlock to Edit," changes the field's label, and saves
- **THEN** the field's label is updated to the new value

#### Scenario: A locked field's editable controls stay disabled until explicitly unlocked
- **WHEN** an admin opens the Field Properties panel for a locked field and
  does not select "Unlock to Edit"
- **THEN** the Label, Placeholder, Description, and (if applicable) Options
  controls remain disabled, matching today's behavior

#### Scenario: Admin unlocks a locked option-bearing field to edit its options
- **WHEN** an admin unlocks a locked `dropdown_select` or `checkbox_list`
  field and adds, removes, or renames one of its options, then saves
- **THEN** the field's option list reflects the change

#### Scenario: Re-locking or switching fields discards unsaved edits and resets to locked
- **WHEN** an admin has unlocked a field, made unsaved changes, and either
  re-locks it or selects a different field in the step's field list without
  saving
- **THEN** the panel discards the unsaved changes and, if the same field is
  reopened, shows its last-saved values with its editable controls disabled
  again by default

### Requirement: Unlocking a Field Never Changes Its Required, Active State, or Field Type
Unlocking a locked field for editing SHALL NOT extend to its `isRequired`
or `isActive` state or its field type — those remain governed by the
existing locked-field restriction (an `isActive`/`isRequired` change to
`false`, or any field-type change, on a locked field is rejected) whether
or not the admin has unlocked it for editing its other properties.

#### Scenario: An unlocked-for-editing field still rejects becoming optional
- **WHEN** an admin unlocks a locked, required field for editing and
  attempts to save it with `isRequired` set to `false`
- **THEN** the request is rejected and the field remains required

#### Scenario: An unlocked-for-editing field still rejects being deactivated
- **WHEN** an admin unlocks a locked field for editing and attempts to save
  it with `isActive` set to `false`
- **THEN** the request is rejected and the field remains active

#### Scenario: A locked field's type cannot be changed regardless of unlock state
- **WHEN** an admin unlocks a locked field for editing
- **THEN** no control is offered to change that field's field type, whether
  locked or unlocked

### Requirement: Published Form Changes Render Identically on the Staff and Visitor Registration Forms
A branch's published form configuration — including a `static_text`
field's content and any edit made to a locked field's label, placeholder,
description, or options through the unlock flow — SHALL render identically
on the staff/walk-in registration wizard and the visitor self-registration
wizard, since both resolve the same effective form for that branch.

#### Scenario: A newly published static_text field appears on both forms
- **WHEN** an admin adds a `static_text` field to an active step and
  publishes
- **THEN** the field's heading and body content appear on both the staff
  wizard and the visitor wizard's rendering of that step

#### Scenario: An edit made through the unlock flow appears on both forms after publish
- **WHEN** an admin unlocks a locked field, changes its label, and
  publishes
- **THEN** the updated label appears on both the staff wizard and the
  visitor wizard's rendering of that field

## MODIFIED Requirements

### Requirement: An Admin Can Update an Existing Field's Description
The Field Properties panel SHALL let an admin add, change, or clear an
existing field's description, subject to the same locked-field restriction
already applied to that field's label and placeholder — a locked field's
description is only editable once the admin has explicitly unlocked it for
editing.

#### Scenario: Admin edits the description of an unlocked field
- **WHEN** an admin changes the description of an existing, unlocked field
  in the Field Properties panel and saves
- **THEN** the field's description is updated to the new value

#### Scenario: A locked field's description cannot be edited
- **WHEN** an admin opens the Field Properties panel for a locked field and
  has not selected "Unlock to Edit"
- **THEN** the description input is disabled, consistent with that field's
  label and placeholder inputs, and no description change can be submitted
  for it

### Requirement: An Admin Can Edit an Existing Option-Bearing Field's Options
The Field Properties panel SHALL let an admin add, remove, rename, and
reorder the options of an existing `checkbox_list`, `dropdown_select`, or
optioned `toggle_switch` field after it has been created — not only at
field-creation time — subject to the same locked-field restriction already
applied to that field's label and placeholder: a locked field's options are
only editable once the admin has explicitly unlocked it for editing.

#### Scenario: Admin adds an option to an existing unlocked checkbox list field
- **WHEN** an admin adds a new option to an existing, unlocked
  `checkbox_list` field in the Field Properties panel and saves
- **THEN** the new option is added to the field's option list and appears
  as a selectable choice on the visitor-facing form

#### Scenario: Admin removes or renames an option on an existing unlocked field
- **WHEN** an admin removes or renames an option of an existing, unlocked
  `checkbox_list` or `dropdown_select` field and saves
- **THEN** the field's option list reflects the removal or rename

#### Scenario: Clearing every option from an option-required field type is rejected
- **WHEN** an admin removes all options from a `checkbox_list` or
  `dropdown_select` field and attempts to save
- **THEN** the save is rejected and the admin UI surfaces the "must declare
  a non-empty options list" error, and the field's previously saved options
  are left unchanged

#### Scenario: A locked field's options cannot be edited
- **WHEN** an admin opens the Field Properties panel for a locked,
  option-bearing field and has not selected "Unlock to Edit"
- **THEN** the options editor is disabled, consistent with that field's
  label and placeholder inputs, and no option change can be submitted for it
