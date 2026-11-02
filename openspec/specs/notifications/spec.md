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
grants included). A recipient with no registered device SHALL receive no
push, and this is not an error condition for the dispatching action. Every
resolved recipient SHALL nevertheless receive an in-app notification (see
"Every Push Dispatch Is Also Recorded as an In-App Notification"). A
dispatch in which no recipient has a registered device SHALL be logged at
`INFO` as `push_no_registered_devices` with the recipient count, so that a
push reaching no device is distinguishable from a delivered one.

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
- **THEN** the dispatch completes without error, the triggering action's
  own outcome (e.g. the invitation's state transition) is unaffected, the
  recipient still gets an in-app notification, and an `INFO`
  `push_no_registered_devices` log line is written

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

### Requirement: Every Push Dispatch Is Also Recorded as an In-App Notification
For every push dispatch, the system SHALL store one in-app notification per
resolved recipient user. It SHALL do this regardless of whether that user
has any registered device, and regardless of whether the push send
succeeds. The stored notification SHALL carry the same title, body and
data payload as the push, so it is subject to the same "Push Payloads
Exclude Sensitive Visitor Data" rule. It SHALL start unread. Recording SHALL
be idempotent per dispatch and recipient: a redelivered or retried dispatch
SHALL NOT create a second notification for the same recipient. A failure
to record SHALL NOT fail the triggering action.

#### Scenario: Recipient without a device still gets an in-app notification
- **WHEN** an invitation is approved and its host has no registered device
- **THEN** the host has one unread in-app notification for that approval

#### Scenario: Role fan-out records one notification per holder
- **WHEN** a push is dispatched to a role with three holders at the branch
- **THEN** each of the three holders has exactly one new in-app
  notification

#### Scenario: Redelivered dispatch does not duplicate
- **WHEN** the same dispatch is processed twice (a broker redelivery or a
  retry after a transient send failure)
- **THEN** each recipient still has exactly one in-app notification for it

### Requirement: A Staff User Lists and Reads Their Own Notifications
The system SHALL expose, to any authenticated tenant user:

- `GET /api/v1/notifications`: the caller's own notifications, newest
  first, paginated by `page`/`pageSize` (default 20, max 100), with an
  optional `unreadOnly` boolean filter. Each item has `id`, `title`,
  `body`, `data`, `createdAt` and `readAt`.
- `GET /api/v1/notifications/unread-count`: the number of the caller's
  unread notifications.
- `PATCH /api/v1/notifications/{id}/read`: marks one of the caller's
  notifications read. Marking an already-read notification is a no-op that
  keeps the original `readAt`.
- `POST /api/v1/notifications/read-all`: marks every unread notification of
  the caller read, in one operation.

A notification about an invitation that has been deleted (soft-deleted or
no longer present) SHALL be excluded from the list, its `total`, and the
unread count. Notifications not about any invitation SHALL be unaffected.
The list `total`, the `unreadOnly` list, and the unread count SHALL always
agree with each other.

A caller SHALL only ever see or change their own notifications. A
notification id belonging to another user SHALL be answered with 404, the
same as an unknown id. An unauthenticated request SHALL get 401.

#### Scenario: Listing returns only the caller's notifications
- **WHEN** users A and B each have notifications and A calls
  `GET /api/v1/notifications`
- **THEN** only A's notifications are returned, newest first, with
  pagination metadata

#### Scenario: Unread filter and count agree
- **WHEN** a user has five notifications, two of them read
- **THEN** `GET /api/v1/notifications?unreadOnly=true` returns three items
  and `GET /api/v1/notifications/unread-count` returns 3

#### Scenario: A soft-deleted invitation's notifications are hidden
- **WHEN** a user has three unread notifications about invitation X and two
  about invitation Y, and X is soft-deleted
- **THEN** `GET /api/v1/notifications/unread-count` returns 2 and
  `GET /api/v1/notifications` lists only the two about Y, with
  `pagination.total` 2

#### Scenario: Marking another user's notification is a 404
- **WHEN** user A calls `PATCH /api/v1/notifications/{id}/read` for a
  notification belonging to user B
- **THEN** the response is 404 and B's notification stays unread

#### Scenario: Mark all read
- **WHEN** a user with three unread notifications calls
  `POST /api/v1/notifications/read-all`
- **THEN** their unread count becomes 0, and no other user's notifications
  change

### Requirement: Deleting an Invitation Deletes Its Notifications
When an invitation is permanently deleted, by any path (the retention
purge, an operational cleanup script, or direct SQL), every in-app
notification about it SHALL be deleted in the same transaction, for every
recipient. Notifications for other invitations, and notifications not about
any invitation, SHALL be untouched.

#### Scenario: Retention purge removes the invitation's notifications
- **WHEN** the invitation retention purge hard-deletes an invitation that
  produced notifications for three staff users
- **THEN** none of those three users has a notification about that
  invitation any more, and their notifications about other invitations
  remain

#### Scenario: Raw SQL delete of an invitation also removes its notifications
- **WHEN** an invitation row is deleted with a plain SQL `DELETE` outside
  the application (as the QA reset script does)
- **THEN** its notifications are gone too, with no extra step in that
  script

### Requirement: Existing Orphaned Notifications Are Removed on Upgrade
Upgrading a tenant schema to this change SHALL permanently delete every
notification whose `data.invitationId` names an invitation that no longer
exists in that schema. It SHALL keep all other notifications, including
their read state.

#### Scenario: Upgrade clears stale notifications
- **WHEN** a tenant schema holds 6,247 notifications, 5,883 of which name
  invitations that no longer exist, and the tenant is upgraded
- **THEN** 364 notifications remain, each naming an existing invitation,
  with `readAt` unchanged

### Requirement: In-App Notifications Are Retained for 90 Days
The system SHALL permanently delete in-app notifications older than 90 days,
read or unread, as part of a recurring background job. It SHALL NOT need
any user action to do so.

#### Scenario: Old notifications are purged
- **WHEN** the recurring job runs and a user has a notification created 91
  days ago and another created yesterday
- **THEN** the 91-day-old notification is deleted and yesterday's remains

### Requirement: The Staff Portal Shows the Notification Feed and Push State
The staff web portal's notification bell SHALL show the signed-in user's
in-app notifications from the server, with the unread count as its badge.
It SHALL refresh when a foreground push arrives, when the tab regains
focus, and at least once a minute while the tab is open. Selecting a
notification about an invitation SHALL mark it read and open that
invitation. "Mark all read" SHALL mark all of the user's notifications
read on the server.

The bell SHALL also show the browser's push state for this device:

- **enabled**: permission is granted and the device is registered;
- **off**: permission not yet decided. An "Enable notifications" control
  requests permission only in direct response to the user's click;
- **blocked**: permission denied, with guidance to re-allow it in browser
  settings;
- **unavailable**: an insecure context or an unsupported browser, with that
  reason shown.

The portal SHALL NOT request notification permission without a user click.
It SHALL re-register an already-permitted device on sign-in, on tab focus
and periodically. A failed registration SHALL be shown to the user, not
only logged to the console.

#### Scenario: Notifications show without browser push
- **WHEN** a host whose browser has never granted push permission signs in,
  after an invitation they host was approved
- **THEN** the bell shows an unread badge, and the panel lists the approval
  notification

#### Scenario: Enabling push from the bell
- **WHEN** a user whose push state is "off" clicks "Enable notifications"
  and grants permission
- **THEN** the device is registered with the API and the push state shows
  "enabled"

#### Scenario: Blocked permission is explained
- **WHEN** a user has denied notification permission for the portal
- **THEN** the push state shows "blocked" with guidance to re-allow
  notifications in browser settings, and no permission prompt is attempted

#### Scenario: Insecure context is explained
- **WHEN** the portal is opened over plain HTTP on a non-localhost address
- **THEN** the push state shows "unavailable" and states that push needs
  HTTPS or localhost, and the in-app feed still works

#### Scenario: Background push click opens the invitation
- **WHEN** a staff user clicks a system notification shown while no portal
  tab was focused
- **THEN** the portal opens that invitation on the staff invitations board,
  or the admin invitations page for an admin context
