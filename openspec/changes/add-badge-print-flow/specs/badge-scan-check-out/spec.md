## ADDED Requirements

### Requirement: Badge scan page works without login
The system SHALL provide a public page where a badge's QR token can be submitted for check-out or same-day re-entry, with no staff session required, and SHALL NOT submit automatically on load.

#### Scenario: Unauthenticated access
- **WHEN** a browser without a staff token opens the scan page
- **THEN** the page renders and does not redirect to login

### Requirement: Check-out via badge
The system SHALL call `POST /checkin/badge/check-out` with `{ "token": ... }` and show the visitor's tracking ID and resulting check-in status on success.

#### Scenario: Successful check-out
- **WHEN** a valid token is submitted for check-out
- **THEN** the system shows success with `trackingId` and `checkInStatus`

### Requirement: Re-enter via badge
The system SHALL call `POST /checkin/badge/re-enter` with `{ "token": ... }` for a visitor returning the same day.

#### Scenario: Successful re-entry
- **WHEN** a valid token is submitted for re-entry
- **THEN** the system shows success with the updated status

### Requirement: Scan failures are explained
The system SHALL show a clear invalid-badge message for 400 "Invalid badge token" and a slow-down message for 429, and SHALL NOT retry automatically or store the token.

#### Scenario: Invalid token
- **WHEN** the server returns 400 "Invalid badge token"
- **THEN** the system says the badge is not valid (wrong day, replaced, tampered, or already used)

#### Scenario: Rate limited
- **WHEN** the server returns 429
- **THEN** the system asks the user to wait before scanning again

#### Scenario: Feature off
- **WHEN** the server returns 404
- **THEN** the page shows the unavailable state
