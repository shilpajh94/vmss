## MODIFIED Requirements

### Requirement: Invitation Creation's Initial Approval State Follows the Company's Auto-Approve Setting
The system SHALL resolve a newly created invitation's initial status from
the tenant's `Company.autoApprovePreRegisteredVisitors` setting: `approved`
when it is enabled, or `submitted` (awaiting approval) when it is disabled
or when no `Company` profile is configured yet for the tenant. WHEN the
resulting status is `approved`, the system SHALL dispatch the approval
notification — the tracking ID and a QR code encoding an
authenticated-encrypted check-in token (see "QR Check-In Token Is
Encrypted and Tamper-Evident") — to the primary contact. WHEN the
resulting status is `submitted`, the system SHALL dispatch a
tracking-only notification — the tracking ID and current status, with no
QR code — and SHALL NOT dispatch the QR-bearing notification until the
invitation is later approved (see "A Submitted Invitation Can Be Manually
Approved").

#### Scenario: Auto-approve enabled creates an already-approved invitation
- **WHEN** the tenant's `Company.autoApprovePreRegisteredVisitors` is
  `true` and an employee creates an invitation
- **THEN** the invitation's status is `approved`, its `approvedAt`
  timestamp is set, and the dispatched notification includes the tracking
  ID and a QR code encoding an encrypted check-in token — not the plain
  tracking ID

#### Scenario: Auto-approve disabled creates an awaiting-approval invitation
- **WHEN** the tenant's `Company.autoApprovePreRegisteredVisitors` is
  `false` and an employee creates an invitation
- **THEN** the invitation's status is `submitted`, its `approvedAt` is
  unset, and the dispatched notification includes only the tracking ID and
  current status — no QR code

#### Scenario: No configured company profile defaults to awaiting approval
- **WHEN** an invitation is created for a tenant with no `Company` profile
  configured yet
- **THEN** the invitation is treated the same as auto-approve disabled —
  status `submitted`, tracking-only notification, no QR code

## ADDED Requirements

### Requirement: QR Check-In Token Is Encrypted and Tamper-Evident
The QR code issued for an approved invitation SHALL encode an
authenticated-encryption token of the invitation's internal id under a
server-side key — never the plain, human-readable tracking ID
and never the invitation id in cleartext. The token SHALL be generated
once, at the point the invitation becomes `approved`, and the same token
SHALL be reused for any later resend of the approval notification or
badge reprint for that invitation, rather than a new token being minted
on each resend. A token that fails authentication (invalid or tampered
ciphertext) SHALL be rejected without revealing which part of the token
was invalid.

#### Scenario: Token is generated once at approval
- **WHEN** an invitation transitions to `approved` (auto-approved at
  creation, or via manual approval)
- **THEN** the system generates one encrypted check-in token for that
  invitation and persists it alongside its rendered QR image

#### Scenario: Resending the approval notification reuses the issued token
- **WHEN** the approval notification for an already-approved invitation is
  resent
- **THEN** the QR code attached encodes the same token issued at approval
  time, not a newly generated one

#### Scenario: A tampered token is rejected
- **WHEN** the check-in endpoint receives a token whose ciphertext or
  authentication tag has been altered
- **THEN** the request is rejected as an invalid token, with no invitation
  detail disclosed

### Requirement: QR Check-In Drives a Cycling Checked-In/Checked-Out Lifecycle
An invitation's check-in lifecycle SHALL be tracked by a `checkInStatus`
value of `unused`, `checked_in`, or `checked_out`, defaulting to `unused`.
Scanning an invitation's QR check-in token SHALL toggle `checkInStatus`:
from `unused` or `checked_out` (the visitor is currently outside) to
`checked_in` on a valid scan, and from `checked_in` to `checked_out` on
the next valid scan — repeating for as many entry/exit cycles as the
visitor makes over the course of their visit (e.g. leaving for lunch and
returning, or moving between buildings on a multi-building site), not
limited to one round trip. There is no terminal state short of the
invitation's own expiry: a scan is never rejected merely because the
visitor has already completed an earlier visit/exit cycle.

#### Scenario: First scan checks the visitor in
- **WHEN** a QR check-in token is scanned for an invitation whose
  `checkInStatus` is `unused`, and the invitation is otherwise eligible
- **THEN** `checkInStatus` becomes `checked_in`, `checkedInAt` is
  recorded, and the response indicates a successful check-in

#### Scenario: A scan while checked in checks the visitor out
- **WHEN** the same QR check-in token is scanned again for an invitation
  whose `checkInStatus` is `checked_in`
- **THEN** `checkInStatus` becomes `checked_out`, `checkedOutAt` is
  recorded, and the response indicates a successful check-out

#### Scenario: A later scan re-admits a previously checked-out visitor
- **WHEN** a QR check-in token is scanned for an invitation whose
  `checkInStatus` is `checked_out`, and the invitation is otherwise
  eligible
- **THEN** `checkInStatus` becomes `checked_in` again, `checkedInAt` is
  updated, and the response indicates a successful check-in — exactly as
  it would from `unused`

### Requirement: QR Check-In Enforces Invitation Expiry on Every Entry
Every transition into `checked_in` — whether from `unused` (the first
entry) or from `checked_out` (a re-entry) — SHALL be rejected when the
invitation's `expires_at` has already passed at scan time. The
`checked_in` → `checked_out` transition SHALL NOT be subject to this
expiry check, so a visit that legitimately continues past `expires_at`
can still be closed out.

#### Scenario: First entry scan after expiry is rejected
- **WHEN** a QR check-in token is scanned for an invitation whose
  `checkInStatus` is `unused` and whose `expires_at` is in the past
- **THEN** the request is rejected as expired and `checkInStatus` remains
  `unused`

#### Scenario: Re-entry scan after expiry is rejected
- **WHEN** a QR check-in token is scanned for an invitation whose
  `checkInStatus` is `checked_out` and whose `expires_at` is in the past
- **THEN** the request is rejected as expired and `checkInStatus` remains
  `checked_out`

#### Scenario: Exit scan after expiry still succeeds
- **WHEN** a QR check-in token is scanned for an invitation whose
  `checkInStatus` is `checked_in` and whose `expires_at` is in the past
- **THEN** the transition to `checked_out` succeeds

### Requirement: QR Check-In Response Surfaces Full Invitation Detail
A successful or rejected QR check-in response SHALL include enough
invitation detail for a scanning client to display it without a
follow-up lookup: the visitor's contact details, the resolved host's
display name, purpose of visit and department, the submitted/approved/
checked-in/checked-out timeline, the invitation's `expiresAt`, and its
current `checkInStatus`.

#### Scenario: Successful check-in response includes visitor and host detail
- **WHEN** a QR check-in scan succeeds
- **THEN** the response includes the visitor's name and contact details,
  the host's display name, purpose of visit, department, the relevant
  timeline timestamps, `expiresAt`, and `checkInStatus`
