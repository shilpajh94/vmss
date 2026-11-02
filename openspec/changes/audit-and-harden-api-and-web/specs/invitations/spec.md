## ADDED Requirements

### Requirement: The Approval-Revert Notice Reliably Reaches the Primary Contact
When an invitation's approval is reverted, the primary-contact notice that
"An Approved, Not-Yet-Checked-In Invitation Can Have Its Approval Reverted"
requires SHALL actually be delivered. A run of the notification task SHALL
NOT fail on its own inputs. Delivery SHALL follow the contact's preferred
method when an approved message template exists for that channel. When the
preferred channel has no approved revert template, the notice SHALL go by
email if the contact has an email address. If it has neither, the notice is
skipped and a WARNING is logged naming the tenant and invitation. A
redelivered task SHALL NOT send the notice a second time.

#### Scenario: Email-preferring contact receives the notice
- **WHEN** an invitation whose primary contact prefers email has its
  approval reverted
- **THEN** exactly one "approval withdrawn" email reaches that contact

#### Scenario: SMS-preferring contact without an approved revert template
- **WHEN** the primary contact prefers SMS, no approved revert SMS
  template is configured, and the contact has an email address
- **THEN** the notice is delivered by email

#### Scenario: Redelivered revert task does not resend
- **WHEN** the revert-notification task runs a second time for the same
  revert after a successful first send
- **THEN** no second notice is sent

### Requirement: Invitation List Items Surface the Preferred Visit Date and Time
Each item returned by `GET /invitations` SHALL include `preferredVisitDate`
and `preferredVisitTime` (null when not captured), plus
`currentApprovalStep` in the same shape the detail view returns (null when
no step is pending). A board card can then show the schedule and its
approval level without fetching the detail. The list SHALL still be served
with a bounded number of queries per page, independent of the page size.
Every existing list-item field SHALL be unchanged.

#### Scenario: Scheduled invitation in the list
- **WHEN** a caller lists invitations and one has a preferred visit date
  and time
- **THEN** that item carries both values

#### Scenario: Pending approval level is in the list item
- **WHEN** a listed invitation is `submitted` with a pending approval step
  at level 2 of 3
- **THEN** that item's `currentApprovalStep` identifies the level-2 step

#### Scenario: Walk-in with no schedule
- **WHEN** an invitation has no preferred visit date or time
- **THEN** both fields are null

### Requirement: Invitation Detail Surfaces the Check-In and Check-Out Devices
`GET /invitations/{id}` SHALL include `checkInDevice` and `checkOutDevice`,
in the same shape the check-in responses already return. Each is null when
the transition did not happen through a registered device, or has not
happened yet.

#### Scenario: Kiosk check-in is visible in detail
- **WHEN** an invitation was checked in through a registered device and a
  permitted caller fetches its detail
- **THEN** `checkInDevice` identifies that device

#### Scenario: Not yet checked in
- **WHEN** a permitted caller fetches the detail of an approved invitation
  that has not been checked in
- **THEN** `checkInDevice` and `checkOutDevice` are null

## MODIFIED Requirements

### Requirement: Staff Check-In Has One Canonical Endpoint
The system SHALL expose exactly one staff/desk-facing endpoint for
transitioning an invitation into `checked_in` by an authenticated caller:
`PATCH /api/v2/invitations/{trackingId}/check-in`. The legacy `PATCH
/api/v1/invitations/{id}/check-in` endpoint SHALL be removed outright, not
merely deprecated. Staff check-out remains a separate endpoint (`PATCH
/api/v1/invitations/{id}/check-out`), unchanged by this requirement, and is
authorized by `invitations:checkout` at the invitation's branch.

#### Scenario: Legacy v1 check-in route no longer exists
- **WHEN** a caller sends `PATCH /api/v1/invitations/{id}/check-in` for any
  invitation
- **THEN** the system returns 404, since the route itself is removed
- **AND** the check-in endpoint `PATCH /api/v2/invitations/{trackingId}/check-in` continues to function exactly as it did before this change

#### Scenario: Check-out is unaffected
- **WHEN** a caller with `invitations:checkout` at the invitation's branch
  calls `PATCH /api/v1/invitations/{id}/check-out` for a `checked_in`
  invitation
- **THEN** the check-out succeeds exactly as it did before this change
