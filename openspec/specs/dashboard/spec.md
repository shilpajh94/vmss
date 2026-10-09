# dashboard Specification

## Purpose

Backs the admin portal's dashboard page — summary counts and an
upcoming-visitors preview, the check-in action triggered from that preview,
a paginated check-ins log, and topbar visitor search — all read from (or
acting on) the existing `invitations` capability's data, with no table of
its own.

## Requirements

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
check it in) directly through the canonical invitation endpoint
(`PATCH /api/v2/invitations/{trackingId}/check-in` — see the `invitations`
capability) without a separate lookup.

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

### Requirement: Dashboard Endpoints Require Branch-Wide Invitation Visibility
`GET /admin/dashboard/overview`, `GET /admin/dashboard/checkins`, and
`GET /admin/dashboard/search` SHALL resolve their branch scope against
`invitations:view-all` rather than `invitations:view`: wherever the
"Dashboard Overview Summary", check-ins, and "Dashboard Topbar Search"
requirements say the caller SHALL hold `invitations:view` at a branch (or
aggregate across every branch they hold it at), the permission consulted
SHALL be `invitations:view-all`. These endpoints aggregate or search across
every invitation at a branch, which only a branch-wide viewer (Reception,
Security, Admin) may see; a caller holding only `invitations:view` (e.g. a
`host`) SHALL be rejected the same way a caller with no grant is today.

#### Scenario: A host cannot search visitor names branch-wide
- **WHEN** a caller holding only the `host` role at a branch requests
  `GET /admin/dashboard/search?query=carter`
- **THEN** the system returns 403 and no invitation data

#### Scenario: A host cannot read branch-wide dashboard counts
- **WHEN** a caller holding only the `host` role at a branch requests
  `GET /admin/dashboard/overview` or `GET /admin/dashboard/checkins`
- **THEN** the system returns 403

#### Scenario: Branch-wide viewers keep the dashboard
- **WHEN** a caller holding the `admin`, `reception`, or `security` role at
  a branch requests any of the three dashboard endpoints scoped to it
- **THEN** the system returns the same data it returned before this change
