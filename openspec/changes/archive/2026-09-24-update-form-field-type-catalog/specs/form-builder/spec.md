## MODIFIED Requirements

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

## ADDED Requirements

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
