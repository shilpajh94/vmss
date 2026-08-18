## ADDED Requirements

### Requirement: Submission outcome also triggers a notification
The system SHALL, in addition to the existing confirmation or inline error, trigger a success notification when a staff-initiated registration is submitted successfully, and an error notification when submission fails.

#### Scenario: Successful submission
- **WHEN** the staff member confirms submission and the request is accepted
- **THEN** the system shows the confirmation with a tracking reference and also triggers a success notification

#### Scenario: Submission failure
- **WHEN** the staff member confirms submission and the request is rejected or cannot be completed
- **THEN** the system shows the inline error message on the Review & Confirm step and also triggers an error notification
