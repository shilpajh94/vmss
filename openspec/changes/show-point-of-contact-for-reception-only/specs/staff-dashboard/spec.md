## ADDED Requirements

### Requirement: Visitor Info modal shows Point of Contact for reception-only invitations
The system SHALL, when an invitation's approval workflow is reception-only (exactly one total step), show a "Point of Contact" field with the value "Reception" in the Visitor Info modal.

#### Scenario: Reception-only invitation
- **WHEN** the Visitor Info modal is opened for an invitation whose approval workflow has exactly one total step
- **THEN** the "Visit details" section shows a "Point of Contact" field with the value "Reception"

#### Scenario: Multi-step workflow is unaffected
- **WHEN** the Visitor Info modal is opened for an invitation whose approval workflow has more than one total step
- **THEN** no "Point of Contact" field is shown
