## ADDED Requirements

### Requirement: A Field May Suppress Its Label From the Visitor-Facing Render
A field SHALL declare a `hideLabel` boolean, defaulting to `false`, settable
at creation and editable afterward for any field type. A field's `label`
remains mandatory at creation regardless of `hideLabel` — it is still used
as the field's accessible name and in validation error messages — but the
effective-form snapshot the visitor-facing renderer consumes SHALL carry
`hideLabel` alongside the field's other display properties so the renderer
can omit the visible label text when it is `true`. `hideLabel` has no effect
on submission validation.

#### Scenario: Admin creates a field with its label hidden
- **WHEN** an admin creates a custom field with `hideLabel` set to `true`
- **THEN** the field is created successfully, `label` is stored as given,
  and the field's entry in `GET /form-builder/steps` and in the published
  effective-form snapshot reports `hideLabel: true`

#### Scenario: A field defaults to a visible label
- **WHEN** an admin creates a field without specifying `hideLabel`
- **THEN** the field is created with `hideLabel: false`, matching today's
  behavior of every field's label always rendering

#### Scenario: Admin toggles an existing field's label visibility
- **WHEN** an admin updates an existing field's `hideLabel` from `false` to
  `true`, or back
- **THEN** the field's `hideLabel` value is updated and reflected the next
  time the branch's form is published

#### Scenario: A hidden label still enforces required-field validation by key
- **WHEN** a visitor submits a form omitting a required value for a field
  whose `hideLabel` is `true`
- **THEN** the submission is rejected the same way a missing required value
  is rejected for any other field — `hideLabel` does not exempt a field
  from its own `isRequired` rule
