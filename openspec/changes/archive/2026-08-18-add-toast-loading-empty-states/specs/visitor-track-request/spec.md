## ADDED Requirements

### Requirement: Lookup failure also triggers a notification
The system SHALL, in addition to the inline error message, trigger an error notification when a tracking-ID lookup fails or no request matches.

#### Scenario: No matching request or lookup error
- **WHEN** the visitor looks up a tracking ID that has no matching visit request, or the lookup cannot be completed
- **THEN** the system shows the inline error message and also triggers an error notification
