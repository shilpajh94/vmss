# form-builder Specification

## Purpose

The form-builder capability lets a tenant admin configure, per branch,
which registration steps and custom fields a visitor registration or
invitation form presents, and enforces that configuration's constraints
when a registration/invitation is submitted.

## Requirements

### Requirement: A Custom Field's Key Is Unique Across a Branch's Entire Active Form
A custom field's key SHALL be unique across every step of a branch's
active form, not only within the step it is being added to — since
submission-time validation resolves a submitted value's field definition
by key across all of a branch's active steps at once, a key reused across
two steps would otherwise have one step's field definition silently
shadow the other's when validating a submitted value.

#### Scenario: Creating a field with a key already used on another step is rejected
- **WHEN** an admin creates a custom field with a key that already exists
  on a different active step of the same branch's form
- **THEN** the request is rejected with a 409 conflict, and no field is
  created

#### Scenario: Creating a field with a key already used on the same step is still rejected
- **WHEN** an admin creates a custom field with a key that already exists
  on the same step
- **THEN** the request is rejected with a 409 conflict, matching today's
  existing per-step uniqueness check

#### Scenario: Distinct keys across different steps are allowed
- **WHEN** an admin creates custom fields with distinct keys on different
  steps of the same branch's form
- **THEN** both fields are created successfully

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
reorder the options of an existing `checkbox_list`, `dropdown_select`,
`radio_button`, or optioned `toggle_switch` field after it has been created
— not only at field-creation time — subject to the same locked-field
restriction already applied to that field's label and placeholder.

#### Scenario: Admin adds an option to an existing unlocked checkbox list field
- **WHEN** an admin adds a new option to an existing, unlocked
  `checkbox_list` field in the Field Properties panel and saves
- **THEN** the new option is added to the field's option list and appears
  as a selectable choice on the visitor-facing form

#### Scenario: Admin removes or renames an option on an existing unlocked field
- **WHEN** an admin removes or renames an option of an existing, unlocked
  `checkbox_list`, `dropdown_select`, or `radio_button` field and saves
- **THEN** the field's option list reflects the removal or rename

#### Scenario: Clearing every option from an option-required field type is rejected
- **WHEN** an admin removes all options from a `checkbox_list`,
  `dropdown_select`, or `radio_button` field and attempts to save
- **THEN** the save is rejected and the admin UI surfaces the "must declare
  a non-empty options list" error, and the field's previously saved options
  are left unchanged

#### Scenario: A locked field's options cannot be edited
- **WHEN** an admin opens the Field Properties panel for a locked,
  option-bearing field
- **THEN** the options editor is disabled, consistent with that field's
  label and placeholder inputs, and no option change can be submitted for it

### Requirement: Field Types Are Constrained To a Supported Set
A field's type SHALL be one of: `text`, `email`, `phone`, `number`,
`dropdown_select`, `date_picker`, `time_picker`, `toggle_switch`,
`checkbox_list`, `checkbox_single`, `radio_button`, `file_upload`,
`textarea`, `static_text`. `dynamic_table`, `rich_text_block`, and
`signature_pad` are not part of the supported set.

`checkbox_single` is a single, option-free field (e.g. a consent
checkbox) and SHALL NOT declare an `options` list, matching how an
option-free `toggle_switch` field is treated today. `radio_button` is a
single-select field rendered as mutually-exclusive choices and SHALL
declare a non-empty `options` list, matching `dropdown_select` and
`checkbox_list` in the option-required rule.

#### Scenario: Unsupported field type rejected
- **WHEN** a field is created or updated with a `fieldType` outside the
  supported set, including `dynamicTable`, `richTextBlock`, or
  `signaturePad`
- **THEN** the request is rejected with 422 before any draft write

#### Scenario: A radio_button field with no options is rejected
- **WHEN** a `radio_button` field is created or updated with an empty or
  absent `options` list
- **THEN** the request is rejected with 422, matching `dropdown_select`
  and `checkbox_list`

#### Scenario: A checkbox_single field does not require options
- **WHEN** a `checkbox_single` field is created with no `options` list
- **THEN** the field is created successfully

#### Scenario: A submitted radio_button value must be one of its declared options
- **WHEN** a visitor submits a value for a `radio_button` field that is not
  one of the field's declared `options`
- **THEN** the submission is rejected with 422, matching how an invalid
  `dropdown_select` value is rejected

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
