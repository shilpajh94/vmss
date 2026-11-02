## MODIFIED Requirements

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

## ADDED Requirements

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
