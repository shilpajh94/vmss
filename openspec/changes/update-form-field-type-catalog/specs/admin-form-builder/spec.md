## ADDED Requirements

### Requirement: The "Select Field Type" picker only offers backend-accepted field types
The system SHALL offer, in the "Select Field Type" picker (used both when
creating a field and when changing an existing field's type), only the
`fieldType` values the Form Builder API currently accepts on create/update.
The system SHALL NOT offer `dynamic_table`, `rich_text_block`, or
`signature_pad` as choices.

#### Scenario: Removed types are absent from the create-field picker
- **WHEN** a tenant admin opens the "Select Field Type" picker while adding
  a new field to a step
- **THEN** no tile for Dynamic Table, Rich Text Block, or Signature Pad is
  shown

#### Scenario: Removed types are absent from the change-type picker
- **WHEN** a tenant admin opens the field type selector in the Field
  Properties panel for an existing field
- **THEN** no option for Dynamic Table, Rich Text Block, or Signature Pad is
  shown

### Requirement: Checkbox Single and Radio Button are available field types
The system SHALL offer `checkbox_single` (a single boolean checkbox, no
options) and `radio_button` (a mutually-exclusive single-select rendered as
radio buttons, requiring a non-empty options list) as choices in the
"Select Field Type" picker, and SHALL support creating, editing, and
publishing fields of these types the same as any other field type.

#### Scenario: Admin adds a Checkbox Single field
- **WHEN** a tenant admin picks "Checkbox Single" while adding a new field
- **THEN** the field is created with `fieldType` `checkbox_single` and no
  options editor is shown for it

#### Scenario: Admin adds a Radio Button field
- **WHEN** a tenant admin picks "Radio Button" while adding a new field
- **THEN** the field is created with `fieldType` `radio_button` and the
  admin must provide at least one option before the field can be saved

### Requirement: Field Properties options editor covers Radio Button
The system SHALL show the Field Properties panel's options editor (add,
remove, and reorder options) for a field whose type is `radio_button`, the
same as it already does for `dropdown_select` and `checkbox_list`. The
system SHALL NOT show the options editor for a field whose type is
`checkbox_single`.

#### Scenario: Options editor shown for Radio Button
- **WHEN** a tenant admin opens the Field Properties panel for a field of
  type `radio_button`
- **THEN** the add/remove/reorder options editor is shown, pre-populated
  with the field's current options

#### Scenario: Options editor hidden for Checkbox Single
- **WHEN** a tenant admin opens the Field Properties panel for a field of
  type `checkbox_single`
- **THEN** no options editor is shown

### Requirement: Visitor-facing form renders Checkbox Single and Radio Button fields
The system SHALL render an active `checkbox_single` field as a single
checkbox bound to a boolean answer, and an active `radio_button` field as a
group of mutually-exclusive radio inputs bound to the field's configured
options, wherever a step's fields are rendered for a visitor filling out a
registration/invitation form.

#### Scenario: Visitor answers a Checkbox Single field
- **WHEN** a visitor-facing registration step includes an active
  `checkbox_single` field
- **THEN** the visitor sees a single checkbox for that field and can toggle
  it on or off

#### Scenario: Visitor answers a Radio Button field
- **WHEN** a visitor-facing registration step includes an active
  `radio_button` field with configured options
- **THEN** the visitor sees one radio input per option, arranged so
  selecting one option deselects any other for that field
