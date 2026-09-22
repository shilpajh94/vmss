## ADDED Requirements

### Requirement: A Retyped System Field's Submitted Value Is Validated Against Its Currently Configured Type
When a system field that Form Builder allows to be retyped (`fullName`,
`purposeOfVisit`, `departmentToVisit`, `licensePlate`, `expectedDuration`,
`additionalNotes`, `idProofType`, `vehicleType`) is currently configured
as an option-bearing type (`dropdown_select` or `checkbox_list`), a
submitted value for that field SHALL be validated against the calling
branch's currently published options for that field, the same way
`idProofType`/`vehicleType` submissions are already validated. When the
field is configured as a non-option-bearing type, the submitted value
SHALL be validated as ordinary free text (existing length/format rules),
unchanged from today. `host` is excluded from this requirement: its
submitted value (`hostNameOrEmail`) is always discarded before
persistence (an invitation's host is resolved exclusively through
delegation — see the `approvals` capability), so there is no stored value
for a retyped-`host`-field constraint to apply to.

#### Scenario: Submission matches a retyped field's configured options
- **WHEN** a branch's "Purpose of Visit" field has been retyped to
  `dropdown_select` with options `["Meeting", "Delivery", "Interview"]`
  and a visitor submits `purposeOfVisit: "Meeting"`
- **THEN** the submission is accepted

#### Scenario: Submission does not match a retyped field's configured options
- **WHEN** a branch's "Purpose of Visit" field has been retyped to
  `dropdown_select` with options `["Meeting", "Delivery", "Interview"]`
  and a visitor submits `purposeOfVisit: "Sightseeing"`
- **THEN** the submission is rejected with a validation error, mirroring
  the existing `idProofType`/`vehicleType` unknown-option rejection

#### Scenario: Submission for a field still configured as free text is unaffected
- **WHEN** a branch's "Purpose of Visit" field remains its default `text`
  type
- **THEN** any non-empty string within the existing length limit is
  accepted, exactly as before this change
