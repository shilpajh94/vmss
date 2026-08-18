## ADDED Requirements

### Requirement: Audit trail load failure also triggers a notification
The system SHALL, in addition to the inline error message, trigger an error notification when the audit trail data fails to load.

#### Scenario: Initial load fails
- **WHEN** the audit trail data fails to load
- **THEN** the system shows an error message on the page and also triggers an error notification
