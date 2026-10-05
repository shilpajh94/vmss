## ADDED Requirements

### Requirement: The Wizard Renders a Published Configuration That Is Older Than the Client or Contains Unknown Field Types
The wizard SHALL render the published form configuration even when it
lacks keys added to the field or group shape after it was published, or
contains a field whose type the client doesn't support. A missing field
`hideLabel` SHALL be treated as `false`. A missing group
`visibilityCondition` SHALL be treated as absent (no condition). A field
of an unsupported type SHALL be omitted: it SHALL NOT render, SHALL NOT
affect the step count, and SHALL NOT be submitted. Every other field and
step SHALL render as configured. The "Something went wrong loading the
registration form" state SHALL be reserved for a failed request or a
response that isn't a form configuration at all.

#### Scenario: Old default form with a removed field type
- **WHEN** the effective configuration's fields lack `hideLabel`, its
  groups lack `visibilityCondition`, and one field has type
  `signature_pad`
- **THEN** the wizard shows its steps with "Step 1 of N" (N being the
  number of configured steps), every supported field renders with its
  label visible, and the `signature_pad` field is not shown
