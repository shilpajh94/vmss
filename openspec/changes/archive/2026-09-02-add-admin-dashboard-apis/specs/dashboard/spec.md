## Purpose

Backs the admin portal's dashboard page — summary counts and an
upcoming-visitors preview, the check-in action triggered from that preview,
a paginated check-ins log, and topbar visitor search — all read from (or
acting on) the existing `invitations` capability's data, with no table of
its own.

## ADDED Requirements

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
`invitations:view` at.

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

### Requirement: Check In an Upcoming Visitor From the Dashboard
The system SHALL provide `PATCH /admin/dashboard/upcoming-visitors`, taking
an `invitationId` in the request body, applying the same business rule as
checking in an invitation directly: only an `approved` invitation may
transition to `checked_in`; an invitation with `watchlistFlagged` set and not
yet overridden SHALL be rejected with 409. The caller SHALL hold
`invitations:checkin` at the invitation's branch. The endpoint SHALL accept
an optional `Idempotency-Key` header; a retried request with the same key
SHALL return the original response without checking the visitor in again.
Every successful check-in through this endpoint SHALL produce the same audit
trail record as checking in through the invitation-scoped endpoint.

#### Scenario: Approved invitation is checked in
- **WHEN** a caller holding `invitations:checkin` at the invitation's branch
  submits `invitationId` for an `approved`, non-watchlisted invitation
- **THEN** the invitation's status becomes `checked_in`, `checkedInAt` and
  `checkedInByUserId` are set, and an audit log entry is recorded

#### Scenario: Non-approved invitation is rejected
- **WHEN** the named invitation's status is not `approved` (e.g. already
  `checked_in`, or still `submitted`)
- **THEN** the system rejects the request with 409 and the invitation's
  status is unchanged

#### Scenario: Watchlist-flagged invitation blocks check-in
- **WHEN** the named invitation has `watchlistFlagged` set and has not been
  overridden
- **THEN** the system rejects the request with 409 and does not check the
  visitor in

#### Scenario: Caller lacks permission at the invitation's branch
- **WHEN** a caller without `invitations:checkin` at the invitation's branch
  submits a check-in request
- **THEN** the system returns 403 and the invitation's status is unchanged

#### Scenario: Retried request with the same Idempotency-Key does not double check-in
- **WHEN** a request that already succeeded is retried with the same
  `Idempotency-Key` value
- **THEN** the system returns the original response and does not re-run the
  check-in (no duplicate audit entry, invitation state unchanged by the
  retry)

### Requirement: Paginated Check-Ins Log
The system SHALL provide `GET /admin/dashboard/checkins`, a paginated list
of every invitation that has been checked in at least once (status
`checked_in` or `checked_out`), using the standard `page`/`pageSize`
pagination envelope. The endpoint SHALL accept the same optional `branchId`
query parameter and branch-scope resolution as the overview endpoint, and
SHALL support sorting by check-in time.

#### Scenario: List includes both currently-inside and already-checked-out visitors
- **WHEN** the check-ins log is requested for a branch with invitations in
  `checked_in` and `checked_out` status, alongside invitations that have
  never been checked in
- **THEN** the response includes every `checked_in` and `checked_out`
  invitation for that branch, and excludes invitations that have never been
  checked in

#### Scenario: Pagination metadata reflects the full result count
- **WHEN** a branch has more checked-in invitations than one page size
- **THEN** the response's pagination metadata reports the correct total
  count and total page count, and each page returns only that page's slice

#### Scenario: branchId narrows the list the same way as the overview endpoint
- **WHEN** the check-ins log is requested with `branchId` set to one branch
  the caller is authorized at
- **THEN** only that branch's checked-in invitations are returned

### Requirement: Dashboard Topbar Search
The system SHALL provide `GET /admin/dashboard/search`, a `query` parameter
(minimum 2 characters) that returns invitations whose primary contact's full
name matches (case-insensitively, partial match) within the caller's
resolved branch scope, capped at a bounded result count. The endpoint SHALL
accept the same optional `branchId` query parameter as the overview
endpoint.

#### Scenario: Partial, case-insensitive name match
- **WHEN** an invitation's primary contact is named "John Carter" and the
  caller searches `query=carter`
- **THEN** that invitation appears in the results

#### Scenario: Query below the minimum length is rejected
- **WHEN** a caller requests the search with a `query` shorter than 2
  characters
- **THEN** the system rejects the request with a validation error and runs
  no search

#### Scenario: No matches returns an empty list, not an error
- **WHEN** no invitation in the caller's branch scope matches the query
- **THEN** the system returns 200 with an empty results list

#### Scenario: Results are limited to the caller's authorized branches
- **WHEN** a caller authorized at Branch A only searches with no `branchId`,
  and a matching invitation exists at Branch B (which the caller is not
  authorized at)
- **THEN** that Branch B invitation is excluded from the results
