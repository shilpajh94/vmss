## ADDED Requirements

### Requirement: Check-in blocked by unverified ID is explained
The system SHALL recognise a 409 from badge check-in whose message says the ID is not verified, SHALL show an "ID verification required" message instead of a generic error, and SHALL NOT retry automatically.

#### Scenario: ID not verified at check-in
- **WHEN** badge check-in returns 409 "ID not verified; verify ID before check-in if the visit has no idVerifiedAt"
- **THEN** the page tells the visitor their ID must be verified at reception before check-in

#### Scenario: Other 409
- **WHEN** a check-in returns a 409 that is not the ID-not-verified case
- **THEN** the server's message is shown as before

### Requirement: Staff can verify ID and retry check-in
The system SHALL, for a signed-in staff user who has the visit identified, offer a "Verify ID" action that calls `POST /checkin/{visitId}/verify-id` and then lets the user retry the check-in with an explicit action, treating a repeated verify as success.

#### Scenario: Verify then retry
- **WHEN** staff confirm "Verify ID" after the ID-not-verified 409 and the call succeeds
- **THEN** a "Check in" action is offered and, when chosen, the check-in is retried once

#### Scenario: Visit not identifiable
- **WHEN** the visit cannot be identified from the failed request (for example the unauthenticated badge scan page)
- **THEN** no Verify ID action is offered and the message directs the visitor to reception

### Requirement: Check-out and re-entry are never blocked by ID verification
The system SHALL leave badge check-out and re-enter behaviour unchanged by the ID verification setting.

#### Scenario: Check-out with unverified ID
- **WHEN** a visit without `idVerifiedAt` is checked out via badge
- **THEN** the request is sent and handled as before
