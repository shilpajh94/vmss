## ADDED Requirements

### Requirement: Staff Registration Renders a Published Configuration That Is Older Than the Client or Contains Unknown Field Types
The staff Register Visitor form SHALL render the published form
configuration even when it lacks keys added after it was published, or
contains a field whose type the client doesn't support. Missing keys
SHALL take their defaults: a field's `hideLabel` is `false`, and a
group's `visibilityCondition` is absent. A field of an unsupported type
SHALL be omitted from rendering, the step count and the submission.
Every other field and step SHALL render as configured.

#### Scenario: Register Visitor with an old default form
- **WHEN** a staff user opens Register Visitor and the effective
  configuration lacks `hideLabel` and `visibilityCondition` keys and
  contains a `signature_pad` field
- **THEN** the stepper lists the configured steps, the visitor-info step
  renders its supported fields, and no load error is shown
