## ADDED Requirements

### Requirement: An Admin Can Attach a Static Description to Any Field at Creation
When creating a custom field, the admin UI SHALL accept an optional
free-text description for the field, regardless of field type, and submit
it as the field's description on creation. The description is for static,
admin-authored content (e.g. the body of a terms-and-conditions statement)
that a visitor sees alongside the field — not a value the visitor fills in.

#### Scenario: Admin creates a field with a description
- **WHEN** an admin fills in a description while creating a new custom
  field, for any field type, and submits the "Add New Custom Field" form
- **THEN** the field is created with that description attached

#### Scenario: Admin creates a field without a description
- **WHEN** an admin submits the "Add New Custom Field" form with the
  description left blank
- **THEN** the field is created with no description, and no description
  area renders for it later on the visitor-facing form

### Requirement: An Admin Can Update an Existing Field's Description
The Field Properties panel SHALL let an admin add, change, or clear an
existing field's description, subject to the same locked-field restriction
already applied to that field's label and placeholder.

#### Scenario: Admin edits the description of an unlocked field
- **WHEN** an admin changes the description of an existing, unlocked field
  in the Field Properties panel and saves
- **THEN** the field's description is updated to the new value

#### Scenario: A locked field's description cannot be edited
- **WHEN** an admin opens the Field Properties panel for a locked field
- **THEN** the description input is disabled, consistent with that field's
  label and placeholder inputs, and no description change can be submitted
  for it

### Requirement: An Admin Can Edit an Existing Option-Bearing Field's Options
The Field Properties panel SHALL let an admin add, remove, rename, and
reorder the options of an existing `checkbox_list`, `dropdown_select`, or
optioned `toggle_switch` field after it has been created — not only at
field-creation time — subject to the same locked-field restriction already
applied to that field's label and placeholder.

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
  option-bearing field
- **THEN** the options editor is disabled, consistent with that field's
  label and placeholder inputs, and no option change can be submitted for it

### Requirement: A Field's Description Renders to Visitors, Truncated With Expand/Collapse
The visitor-facing form SHALL render a field's description beneath that
field's input, for every field type and every step uniformly, truncated to
its first sentence by default with a "See more" control that reveals the
full description and a "See less" control that collapses it back.

#### Scenario: A field with a multi-sentence description renders truncated by default
- **WHEN** a visitor reaches a step containing a field whose description has
  more than one sentence
- **THEN** only the first sentence of the description is shown, followed by
  a "See more" control

#### Scenario: Visitor expands a truncated description
- **WHEN** a visitor selects "See more" on a truncated description
- **THEN** the full description is shown, and the control changes to
  "See less"

#### Scenario: Visitor collapses an expanded description
- **WHEN** a visitor selects "See less" on an expanded description
- **THEN** the description returns to showing only its first sentence, and
  the control changes back to "See more"

#### Scenario: A single-sentence description renders with no expand control
- **WHEN** a field's description is a single sentence (or otherwise fits
  without truncation)
- **THEN** the full description is shown and no "See more"/"See less"
  control appears

#### Scenario: A field with no description renders no description area
- **WHEN** a field has no description set
- **THEN** no description text or expand/collapse control renders for that
  field
