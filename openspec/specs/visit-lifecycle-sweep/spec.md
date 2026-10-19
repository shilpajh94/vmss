# visit-lifecycle-sweep Specification

## Purpose

Closes out visits nobody closed by hand. It checks out visitors who are
still checked in after their pass has expired, and archives approved
visitors who never arrived on their scheduled day. This keeps "who's
inside" and upcoming-visit data accurate without staff action.

## Requirements

### Requirement: Expired Check-Ins Are Checked Out Automatically
The system SHALL run a recurring scheduled sweep for every active tenant
that checks out each invitation still checked in after its `expiresAt` has
passed. An invitation counts as still checked in when its `status` or its
`checkInStatus` is `checked_in`. The sweep SHALL run at least every 15
minutes. For each such invitation, the system SHALL:

- set `status` and `checkInStatus` to `checked_out`;
- set `checkedOutAt` to the invitation's `expiresAt`, not to the time the
  sweep ran;
- leave `checkedOutByUserId` null;
- set `checkedOutAutomatically` to `true`.

`expiresAt` SHALL be read as currently stored. A staff expiry extension
therefore postpones the automatic check-out until the extended time. An
invitation whose `expiresAt` is still in the future SHALL NOT be changed.
Every manual check-out (staff or QR) SHALL leave `checkedOutAutomatically`
`false`.

#### Scenario: Forgotten check-out is closed after expiry
- **WHEN** an invitation was checked in on its visit day, was never checked
  out, and its `expiresAt` (23:59:59 of the visit day in the visit
  timezone) has passed
- **THEN** after the next sweep its `status` and `checkInStatus` are
  `checked_out`, `checkedOutAt` equals its `expiresAt`,
  `checkedOutByUserId` is null and `checkedOutAutomatically` is `true`

#### Scenario: A visitor still within their pass is left checked in
- **WHEN** the sweep runs while a checked-in invitation's `expiresAt` is
  still in the future
- **THEN** the invitation stays `checked_in`

#### Scenario: An extended pass postpones the automatic check-out
- **WHEN** staff extended a checked-in invitation's `expiresAt` to the
  following day at 12:00, and the sweep runs at 00:15 that day
- **THEN** the invitation stays `checked_in`, and it is checked out
  automatically by the first sweep after 12:00

#### Scenario: Manual check-out is not flagged as automatic
- **WHEN** staff or a QR scan checks out a visitor before the sweep reaches
  them
- **THEN** `checkedOutAutomatically` is `false` and the sweep does not
  change the invitation

#### Scenario: Auto-checked-out visitor can check in again while the pass is valid
- **WHEN** an auto-checked-out invitation later has its `expiresAt`
  extended into the future and the visitor scans their pass
- **THEN** check-in follows the same re-entry rule as any other
  `checked_out` invitation

### Requirement: Approved No-Shows Are Archived the Day After the Visit
The same sweep SHALL archive each invitation that has all of the following:
`status` `approved`, `checkInStatus` `unused`, and an `expiresAt` that has
passed. Archiving SHALL set `status` to `archived` and record `archivedAt`
as the time of the sweep. Because `expiresAt` is the end of the scheduled
visit day, a no-show is archived by the first sweep of the next day in the
visit timezone, or by the first sweep after an extended `expiresAt`.

The sweep SHALL NOT archive an invitation with any other status, including
a `submitted` invitation whose visit date has passed. It SHALL NOT archive
an invitation whose visitor was ever checked in. `expiresAt`, the visit
details, the approval steps and the issued QR pass SHALL be left unchanged.

#### Scenario: Approved visitor who never came is archived next day
- **WHEN** an invitation approved for 2026-10-20 is never checked in, and
  the first sweep after 2026-10-20 23:59:59 in the visit timezone runs
- **THEN** its `status` is `archived` and `archivedAt` is set

#### Scenario: Approved visit still upcoming is not archived
- **WHEN** the sweep runs before an approved invitation's `expiresAt`
- **THEN** the invitation stays `approved`

#### Scenario: Pending invitation past its date is not archived
- **WHEN** a `submitted` invitation's visit date has passed
- **THEN** the sweep leaves it `submitted`

#### Scenario: Visitor who checked in and out is not archived
- **WHEN** an invitation's `status` is `checked_out` after a real visit
- **THEN** the sweep leaves it `checked_out`

### Requirement: The Sweep Is Silent, Audited, and Safe to Repeat
The sweep SHALL NOT dispatch any email, SMS or push notification for an
automatic check-out or an archive. For every invitation it changes, it
SHALL write an audit-log entry with no actor: action
`invitation_auto_checked_out` or `invitation_archived` as appropriate,
entity type `invitation`, and the invitation's id. That entry SHALL be
committed together with the status change, so neither is recorded without
the other. Running the sweep again with no new expired rows, or
redelivering the same scheduled run, SHALL change nothing and SHALL write
no further audit entries. If two sweeps run concurrently for the same
tenant, each invitation SHALL be transitioned and audited exactly once.
Each tenant SHALL be processed independently. A failure for one tenant
SHALL NOT prevent the others from being swept in the same run, and a
failure that exhausts retries SHALL be logged at `ERROR` with the tenant.

#### Scenario: No notification on automatic check-out or archive
- **WHEN** the sweep auto-checks-out one invitation and archives another
- **THEN** no email, SMS or push notification is dispatched for either

#### Scenario: Each transition is audited once
- **WHEN** the sweep auto-checks-out an invitation
- **THEN** exactly one `invitation_auto_checked_out` audit entry with a
  null actor exists for it, and running the sweep again adds none

#### Scenario: One tenant's failure does not block another
- **WHEN** the sweep fails while processing tenant A
- **THEN** tenant B's expired check-ins and no-shows are still processed in
  that run

#### Scenario: Tenant isolation
- **WHEN** the sweep for tenant A runs
- **THEN** it changes only invitations stored in tenant A's schema
