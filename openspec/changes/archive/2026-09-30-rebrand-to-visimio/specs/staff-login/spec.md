## MODIFIED Requirements

### Requirement: Staff login screen is visually distinct from the visitor portal
The system SHALL render the staff login screen with its own dark-themed header, carrying the Visimio on-dark logo (mark plus white wordmark), an "Admin Gateway" badge, and a system-status indicator. It SHALL NOT reuse the visitor portal's light header component.

#### Scenario: Staff screen does not show the visitor header
- **WHEN** the staff login screen renders
- **THEN** the visitor portal's light header is not present, and the dark Admin Gateway header is shown instead, with the Visimio on-dark logo
