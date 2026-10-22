## ADDED Requirements

### Requirement: SMS-Preferred Approved Invitation Gets a Numeric Check-In Code
When an invitation is approved and its primary contact's `preferredContactMethod` is `sms`, the system SHALL issue a numeric check-in code of 8 digits, unique among the tenant's invitations and generated from a cryptographically secure source. The code SHALL be issued once and reused on any later read; it SHALL NOT be issued for contacts preferring email or WhatsApp.

#### Scenario: Code issued on approval for an SMS contact
- **WHEN** an invitation whose primary contact prefers `sms` is approved
- **THEN** an 8-digit check-in code is stored for that invitation

#### Scenario: No code for other contact methods
- **WHEN** an invitation whose primary contact prefers `email` or `whatsapp` is approved
- **THEN** no check-in code is issued and QR delivery is unchanged

#### Scenario: Approval redelivery does not change the code
- **WHEN** the approval notification task runs a second time for the same invitation
- **THEN** the same code is used and no new code is generated

### Requirement: Approval SMS Carries the Check-In Code Instead of a QR
The approval notification sent by SMS SHALL include the tracking ID and the check-in code, and SHALL NOT reference a QR code. The code SHALL NOT appear in any log line.

#### Scenario: SMS contains code
- **WHEN** the approval notification is dispatched to an SMS-preferred contact
- **THEN** the message sent through the approval-with-code DLT template contains the tracking ID and the check-in code

#### Scenario: SMS template not configured
- **WHEN** the approval-with-code template ID is not configured
- **THEN** the send fails as a not-configured error (not retried), consistent with other SMS templates, and the invitation approval itself is not rolled back

### Requirement: Public Check-In by Code
The system SHALL expose an unauthenticated `PATCH /api/v2/invitations/code/check-in` taking `{"code": "<8 digits>"}` in the body. It SHALL apply the same rules as QR check-in: transition `unused`/`checked_out` to `checked_in`, be an idempotent success when already `checked_in`, reject with 410 once expired, reject with 425 before `preferredVisitDate`, and reject with 409 when watchlist-flagged or not approved. It SHALL return the same response shape as QR check-in and record host notification and audit entries as QR check-in does.

#### Scenario: Valid code checks in
- **WHEN** a valid code for an approved, in-window invitation is submitted
- **THEN** the response is 200, `checkInStatus` is `checked_in` and the host is notified

#### Scenario: Repeat check-in is a no-op
- **WHEN** the same code is submitted while already checked in
- **THEN** the response is 200 with unchanged data and no second audit entry or host notification

#### Scenario: Unknown or malformed code
- **WHEN** a code that is not 8 digits, or matches no invitation, is submitted
- **THEN** the response is 400 with a generic "invalid code" message that does not reveal which part failed

#### Scenario: Expired or too early
- **WHEN** the code belongs to an expired invitation, or to one whose visit date is in the future
- **THEN** the response is 410 or 425 respectively, matching QR check-in

### Requirement: Public Check-Out by Code
The system SHALL expose an unauthenticated `PATCH /api/v2/invitations/code/check-out` taking `{"code": "<8 digits>"}`. It SHALL transition `checked_in` to `checked_out`, ignore expiry, and return 409 when the invitation is not currently `checked_in`, matching QR check-out.

#### Scenario: Valid code checks out
- **WHEN** the code of a currently checked-in invitation is submitted
- **THEN** the response is 200 and `checkInStatus` is `checked_out`

#### Scenario: Not checked in
- **WHEN** the code of an invitation that is not `checked_in` is submitted
- **THEN** the response is 409

#### Scenario: Re-entry
- **WHEN** a visitor has checked out and submits the same code to check in again
- **THEN** check-in succeeds, as it does for QR re-entry

### Requirement: Code Endpoints Resist Brute Force
Both code endpoints SHALL be rate limited per IP, and the tenant SHALL be protected against code guessing: after repeated failed attempts from one IP within a window, further attempts from that IP SHALL be rejected with 429 until the window passes, even if a later attempt would have been valid. Failed attempts SHALL be logged at WARNING without the submitted code.

#### Scenario: Rate limit trips
- **WHEN** one IP exceeds the per-minute limit on either endpoint
- **THEN** the response is 429

#### Scenario: Lockout after failures
- **WHEN** one IP submits more than the allowed number of wrong codes within the window and then submits a valid code
- **THEN** the response is 429 and no check-in occurs

### Requirement: QR Check-In Remains Available for SMS-Preferred Invitations
Issuing a check-in code SHALL NOT disable QR check-in, check-out or badge QR for the same invitation.

#### Scenario: QR still works
- **WHEN** staff or a kiosk uses the QR token of an SMS-preferred invitation
- **THEN** check-in and check-out succeed as before
