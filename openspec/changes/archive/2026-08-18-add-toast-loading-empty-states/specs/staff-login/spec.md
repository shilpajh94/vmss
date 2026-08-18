## ADDED Requirements

### Requirement: SSO initiation failure also triggers a notification
The system SHALL, in addition to the inline error message, trigger an error notification when SSO initiation fails.

#### Scenario: Initiation request fails
- **WHEN** the SSO initiation request fails (network error or non-success response)
- **THEN** the system shows an inline error message on the login screen and also triggers an error notification
