## ADDED Requirements

### Requirement: Submission confirmation reflects the server's confirmed primary contact name
The system SHALL, after a successful submission (`POST /invitations`), look up the invitation's public tracking record using the returned tracking reference and display that record's primary contact name on the confirmation screen as the confirmed name of record for the request. A failure of that lookup SHALL NOT be treated as a submission failure — the confirmation screen still shows the tracking reference regardless. This wizard has no pre-submit lookup to detect whether the typed primary contact matches a prior invitation, so this confirmed-name display is the only place the staff member can see that the backend silently overwrote the typed name with the name on file for a matched contact.

#### Scenario: Confirmed name differs from what staff typed
- **WHEN** the staff member submits a primary contact whose email (or, when no email is submitted, phone) matches a prior invitation under a different name, the request is accepted, and the subsequent tracking lookup succeeds
- **THEN** the confirmation screen shows the primary contact name from that lookup, which may differ from the name the staff member typed

#### Scenario: Confirmed name matches a first-time contact
- **WHEN** the staff member submits a primary contact that matches no prior invitation, the request is accepted, and the subsequent tracking lookup succeeds
- **THEN** the confirmation screen shows the primary contact name from that lookup, matching what the staff member typed
