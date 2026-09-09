# Notifications Specification

## Purpose

Lets a staff user register a device to receive push notifications, and gives
other capabilities a single primitive to push a notification to a specific
user or to everyone holding a given role at a branch.

## Requirements

### Requirement: A Staff User Registers a Device for Push Notifications
An authenticated staff user SHALL be able to register a device token
(platform: web, android, or ios) against their own user account. Re-registering
the same token SHALL update its association rather than create a duplicate
row.

#### Scenario: First registration on a new browser
- **WHEN** an authenticated user submits a web push token that has never been
  registered before
- **THEN** the system stores a device record linking that token to the
  calling user and platform `web`

#### Scenario: Re-registering an existing token
- **WHEN** an authenticated user submits a token already registered to their
  own account
- **THEN** the system updates the existing record (e.g. its `last_seen_at`)
  rather than inserting a second row for the same token

#### Scenario: A token registered by one user cannot be silently reassigned to another
- **WHEN** a different authenticated user submits a token currently
  registered to someone else's account
- **THEN** the system reassigns that token to the calling user (a device is
  physically one browser/app install, so the newest registrant owns it) and
  the previous owner stops receiving push on that token

### Requirement: A Staff User Unregisters a Device
An authenticated staff user SHALL be able to remove one of their own
registered device tokens (e.g. on logout or uninstall). Removing a token that
is not registered, or not registered to the caller, SHALL be a no-op rather
than an error.

#### Scenario: Logout removes the device token
- **WHEN** an authenticated user submits their own previously-registered
  device token for removal
- **THEN** the system deletes that device record and it no longer receives
  push notifications

#### Scenario: Removing an unknown token is not an error
- **WHEN** a caller submits a token that was never registered, or was
  registered to a different user
- **THEN** the system responds success without deleting another user's
  device record

### Requirement: Push Dispatch Is Addressed by User or by Role at a Branch
The system SHALL provide a dispatch primitive, used by other capabilities,
that sends a push notification either to one or more specific user ids, or to
every user holding a specific role at a specific branch (company-wide role
grants included). A recipient with no registered device SHALL simply receive
nothing — this is not an error condition for the dispatching action.

#### Scenario: Dispatch to a specific user
- **WHEN** a triggering action resolves its recipient as a specific user id
  (e.g. an invitation's host)
- **THEN** every device currently registered to that user id receives the
  push payload

#### Scenario: Dispatch to a role at a branch
- **WHEN** a triggering action resolves its recipient as "every user holding
  role R at branch B"
- **THEN** every device registered to a user holding a `UserBranchRole` for
  role R scoped to branch B, or granted company-wide (`branch_id` null),
  receives the push payload

#### Scenario: Recipient has no registered device
- **WHEN** the resolved recipient (by user id or by role-at-branch) has zero
  registered devices
- **THEN** the dispatch completes without error and the triggering action's
  own outcome (e.g. the invitation's state transition) is unaffected

### Requirement: A Push Send Failure Does Not Block or Fail the Triggering Action
Push dispatch SHALL always run as a background task enqueued after the
triggering action's own database commit, never inline in the request path.
A push provider failure (including full retry exhaustion) SHALL never surface
as an error on the triggering action's HTTP response.

#### Scenario: FCM is unreachable when an invitation is submitted
- **WHEN** submitting an invitation succeeds but the subsequent push dispatch
  to the current approval step's approver(s) fails because the push provider
  is unreachable
- **THEN** the invitation-submission API call still returns its normal
  success response, and the push failure is only visible in the retried
  background task's own logs

### Requirement: An Invalid or Expired Device Token Is Removed on Delivery Failure
When the push provider reports a token as invalid/unregistered (the
provider's standard "this token no longer exists" response, not a transient
network error), the system SHALL delete that device record so future
dispatches stop attempting delivery to it.

#### Scenario: App uninstalled, token now invalid
- **WHEN** a push dispatch to a user's device token receives the provider's
  "token not registered" response
- **THEN** the system removes that device record and does not retry delivery
  to that token

### Requirement: Push Payloads Exclude Sensitive Visitor Data
A push notification payload SHALL be limited to what identifies the action to
a staff user (e.g. invitation tracking id, visitor's display name, action
type) and SHALL NOT include identity document numbers, raw OTP codes, or
other data `security-architecture.md` §2/§4 classifies as sensitive. An
invitation-related push payload SHALL additionally carry addressing
metadata so a client can distinguish how the recipient was targeted:
`assignedRoleId` (set when the recipient was reached because they hold a
given role at the invitation's branch, null otherwise), `assignedUserId`
(set when the recipient was reached as one specific named person — e.g. a
delegate or resolved host, null otherwise), and `reason`, one of
`role_assigned` (dispatched via role-at-branch fan-out) or `delegated`
(dispatched because the recipient was specifically delegated or named as
host). Exactly one of `assignedRoleId`/`assignedUserId` SHALL be set per
payload, matching how that particular push was addressed.

#### Scenario: Submission push omits ID proof data
- **WHEN** the system pushes a "new invitation awaiting your approval"
  notification
- **THEN** the payload includes the visitor's name and the invitation's
  tracking id, and never includes any identity-document number or storage key

#### Scenario: Role-fan-out push carries assignedRoleId and reason role_assigned
- **WHEN** the system pushes a notification to every holder of a role at a
  branch (e.g. invitation submission to the tenant's default host role)
- **THEN** each recipient's payload includes `assignedRoleId` set to that
  role's id, `assignedUserId` null, and `reason` set to `role_assigned`

#### Scenario: Delegation/host-assignment push carries assignedUserId and reason delegated
- **WHEN** the system pushes a notification to one specific named person
  (e.g. a step delegate, or a newly assigned host)
- **THEN** the payload includes `assignedUserId` set to that person's id,
  `assignedRoleId` null, and `reason` set to `delegated`
