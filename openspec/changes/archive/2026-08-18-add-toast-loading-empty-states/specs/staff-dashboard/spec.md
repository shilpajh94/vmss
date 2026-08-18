## ADDED Requirements

### Requirement: Dashboard load failure also triggers a notification
The system SHALL, in addition to the inline error message, trigger an error notification when the visit-requests list fails to load or a refresh fails.

#### Scenario: Initial load fails
- **WHEN** the visit-requests list fails to load
- **THEN** the system shows an error message on the dashboard and also triggers an error notification

#### Scenario: Refresh fails
- **WHEN** a staff member activates a refresh action and the re-fetch fails
- **THEN** the system triggers an error notification and the previously loaded board remains visible
