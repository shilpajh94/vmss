## ADDED Requirements

### Requirement: A Captured Custom Field Value Is Displayed Back To The Submitter
For a fully configurable step (Carried Items, Vehicle Info, Consent
Agreement, or any custom step), an active custom field's submitted value
SHALL be visible to the submitter at two points in the registration wizard
after it is captured: in that step's own summary/list presentation (if the
step presents entries in a list, e.g. Vehicle Info's added-vehicle table),
and in the Review & Confirm step's summary of that step's data. A field
with no value entered SHALL be shown as explicitly empty (e.g. an em dash),
distinguishable from the field not existing at all. This applies equally to
the staff-facing and self-service registration wizards, since both present
the same step components.

#### Scenario: A custom field on a repeatable Vehicle Info entry is shown in the vehicle list
- **WHEN** a user adds a vehicle on the Vehicle Info step, filling in an
  admin-configured custom field for that step
- **THEN** the vehicle list table shows a column for that custom field, and
  the value the user entered appears in that vehicle's row

#### Scenario: A custom field with no value is shown as empty, not omitted
- **WHEN** a vehicle is added without a value for an optional custom field
- **THEN** the vehicle list table still shows the column for that field, with
  an explicit empty indicator for that vehicle's row

#### Scenario: Custom field values appear in the Review & Confirm summary
- **WHEN** a user reaches the Review & Confirm step after entering
  custom field values on Vehicle Info and/or Carried Items
- **THEN** the Review & Confirm summary for each of those steps includes
  every active custom field's label and the value the user submitted
