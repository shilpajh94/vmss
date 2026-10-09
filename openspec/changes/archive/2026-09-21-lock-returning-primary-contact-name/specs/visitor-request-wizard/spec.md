## ADDED Requirements

### Requirement: Returning visitor's primary contact full name is locked after prefill
The system SHALL render the primary contact's "Full Name" field as read-only for the remainder of the wizard whenever it was pre-filled from a returning visitor's profile (visitor-return-history's prefill), since the invitation-creation API silently discards any edit to that field for a contact it matches by email (or, when no email is submitted, by phone) against a prior invitation. This lock applies only to the primary contact; it SHALL NOT apply to a first-time visitor with no prefill profile, and SHALL NOT apply to any additional visitor added to a group registration.

#### Scenario: Returning primary contact's name field is read-only
- **WHEN** the wizard's initial data includes a pre-filled full name for the primary contact from a returning visitor's profile
- **THEN** the "Full Name" field for the primary contact renders read-only and does not accept edits

#### Scenario: First-time visitor's name field stays editable
- **WHEN** the visitor is verified with no prior visits and the history lookup's prefill profile is null
- **THEN** the primary contact's "Full Name" field renders as a normal editable field

#### Scenario: Additional group visitor's name field is never locked
- **WHEN** the primary contact's full name is locked because their profile was pre-filled
- **THEN** every additional visitor added to the group registration still has a normal editable "Full Name" field

### Requirement: Submission confirmation reflects the server's confirmed primary contact name
The system SHALL, after a successful submission (`POST /registrations/walk-in`), look up the invitation's public tracking record using the returned tracking reference and display that record's primary contact name on the confirmation screen as the confirmed name of record for the request, rather than assuming the value the wizard submitted was retained unchanged. A failure of that lookup SHALL NOT be treated as a submission failure — the confirmation screen still shows the tracking reference regardless.

#### Scenario: Confirmation shows the tracking record's confirmed name
- **WHEN** a visit request is submitted successfully and the subsequent tracking lookup succeeds
- **THEN** the confirmation screen displays the primary contact name from that lookup, alongside the tracking reference

#### Scenario: Confirmed-name lookup failure doesn't affect the confirmation
- **WHEN** a visit request is submitted successfully but the subsequent tracking lookup fails
- **THEN** the confirmation screen still shows the tracking reference, without the confirmed-name display and without showing an error
