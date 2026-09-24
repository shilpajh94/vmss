## ADDED Requirements

### Requirement: Field Properties panel supports hiding a field's visible label
The system SHALL offer a "Hide Label" control in the Field Properties panel
for any field whose type is not content-only (`static_text`), and SHALL
persist the admin's choice as the field's `hideLabel` property when saved.
`hideLabel` SHALL default to `false` for a newly created field.

#### Scenario: Admin turns on Hide Label for a field
- **WHEN** a tenant admin enables "Hide Label" in the Field Properties panel
  for a field and saves
- **THEN** the field's `hideLabel` is persisted as `true`

#### Scenario: New fields default to a visible label
- **WHEN** a tenant admin creates a new field
- **THEN** the field's `hideLabel` is `false` until the admin explicitly
  turns "Hide Label" on

### Requirement: A required field's validation is unaffected by Hide Label
The system SHALL enforce a required field's required-value rule identically
whether `hideLabel` is `true` or `false` — `hideLabel` SHALL affect only
whether the field's label renders visibly, never validation behavior.

#### Scenario: A required, label-hidden field still blocks submission when empty
- **WHEN** a visitor leaves a required field with `hideLabel: true` empty
  and attempts to proceed
- **THEN** the same required-field validation error appears as it would for
  an otherwise-identical field with a visible label

### Requirement: Visitor-facing rendering hides a field's label while keeping it accessible
The system SHALL NOT render a field's label as visible text when the
field's `hideLabel` is `true`, wherever a step's fields are rendered for a
visitor filling out a registration/invitation form. The system SHALL still
expose that label as the field's accessible name (e.g. for a screen
reader), so the field remains identifiable to assistive technology even
though no visible label text appears.

#### Scenario: A label-hidden field shows no visible label text
- **WHEN** a visitor-facing registration step includes an active field with
  `hideLabel: true`
- **THEN** no visible label text appears for that field, only its input
  control (and, for a checkbox/toggle-style field, its inline option text)

#### Scenario: A label-hidden field's label remains available to assistive technology
- **WHEN** a screen reader user reaches a field with `hideLabel: true`
- **THEN** the field's label is announced as its accessible name, the same
  as it would be if the label were visible
