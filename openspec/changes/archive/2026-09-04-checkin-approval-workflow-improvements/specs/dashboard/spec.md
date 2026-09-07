## MODIFIED Requirements

### Requirement: Dashboard Overview Summary
The system SHALL provide `GET /admin/dashboard/overview` returning, for the
resolved branch scope: the count of visits created today, the count
currently checked in (status `checked_in`), the count of invitations awaiting
approval (status `submitted`), the count of upcoming visitors (status
`approved`, not yet checked in, not expired), and a bounded preview list of
those upcoming visitors ordered by soonest expiry. "Today" SHALL be
evaluated in the resolved tenant's configured timezone, not UTC or server
local time. The endpoint SHALL accept an optional `branchId` query
parameter: when supplied, the caller SHALL hold `invitations:view` at that
branch and the response SHALL be scoped to it alone; when omitted, the
response SHALL aggregate across every branch the caller holds
`invitations:view` at. Each row in the upcoming-visitors preview SHALL
include that invitation's `trackingId`, so the caller can act on it (e.g.
check it in) directly through the canonical invitation endpoint without a
separate lookup — see the removal and migration note for "Check In an
Upcoming Visitor From the Dashboard" below.

#### Scenario: Overview scoped to one branch via branchId
- **WHEN** a caller holding `invitations:view` at Branch A requests the
  overview with `branchId` set to Branch A
- **THEN** every count and the upcoming-visitors preview reflect only Branch
  A's invitations

#### Scenario: Overview aggregates across authorized branches when branchId is omitted
- **WHEN** a caller holding `invitations:view` at two branches requests the
  overview with no `branchId`
- **THEN** every count reflects invitations from both branches combined, and
  no invitation from a branch the caller is not authorized at is included

#### Scenario: branchId names a branch the caller is not authorized at
- **WHEN** a caller requests the overview with `branchId` set to a branch
  they do not hold `invitations:view` at
- **THEN** the system returns 403 and no data is returned

#### Scenario: Upcoming-visitors preview excludes checked-in and expired invitations
- **WHEN** the overview is computed for a branch with invitations in
  `submitted`, `approved`, `checked_in`, `checked_out`, and `denied` status,
  including an `approved` invitation whose `expiresAt` has already passed
- **THEN** the upcoming-visitors preview includes only the non-expired
  `approved` invitations, ordered soonest-expiry first

#### Scenario: "Today" boundary follows tenant timezone
- **WHEN** the overview is requested for a tenant configured with a
  non-UTC timezone, at a moment where UTC and that timezone disagree on the
  calendar date
- **THEN** the "visits created today" count reflects the tenant's local
  calendar date, not UTC's

#### Scenario: Upcoming-visitors preview rows carry trackingId
- **WHEN** the overview's upcoming-visitors preview is returned
- **THEN** every row includes that invitation's `trackingId`

## REMOVED Requirements

### Requirement: Check In an Upcoming Visitor From the Dashboard
**Reason**: `PATCH /admin/dashboard/upcoming-visitors` duplicated the same
business rule (approved-only, watchlist-block, `invitations:checkin`
permission) as the canonical check-in endpoint through a second, body-keyed
contract — one of the redundant check-in endpoints this change consolidates
away (see the `invitations` capability's "Staff Check-In Has One Canonical
Endpoint").
**Migration**: The admin portal's dashboard "check in" action SHALL call
`PATCH /api/v2/invitations/{trackingId}/check-in` directly, using the
`trackingId` now included on each upcoming-visitors preview row (see
"Dashboard Overview Summary" above), instead of `PATCH
/admin/dashboard/upcoming-visitors` with `invitationId`. The
`Idempotency-Key` header and resulting audit-trail behavior are unchanged —
the canonical endpoint already supports both.
