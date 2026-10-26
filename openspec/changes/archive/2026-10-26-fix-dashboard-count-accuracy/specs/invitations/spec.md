## ADDED Requirements

### Requirement: Invitation List Supports Dashboard Drill-Down Filters
`GET /invitations` and `GET /invitations/export` SHALL accept these optional
query parameters, so that a dashboard figure can open a list containing
exactly the invitations it counted. Each one SHALL be ANDed with every other
filter, with the branch scope, and with `relevantToMe`:

- `visitDateFrom` and `visitDateTo` (calendar dates, inclusive): keep
  invitations whose visit day falls in the range. The visit day is the
  scheduled visit date or, when there is none, the tenant-local creation
  date — the same rule the `dashboard` capability uses. Either bound MAY be
  given alone. `visitDateFrom` later than `visitDateTo` SHALL be rejected
  with a validation error.
- `upcoming=true`: keep only invitations in status `approved` that have
  never been checked in and whose `expiresAt` is in the future — the same
  filter as the dashboard's upcoming count and preview.
- `excludeExpired=true`: keep only invitations whose `expiresAt` is in the
  future.
- `branchId`: keep only invitations at that branch. The branch SHALL lie
  inside the endpoint's own branch scope (`invitations:view-all` for the
  list's default mode, `invitations:export` for the export); otherwise the
  system SHALL return 403. In the list's `relevantToMe` mode it
  SHALL only narrow the caller's relevant set and SHALL NOT make any
  invitation visible that the caller could not already see.

Omitting all of them SHALL leave the list's existing behaviour unchanged.
The export SHALL apply them exactly as the list does, so exporting a
drilled-down list yields the same invitations.

#### Scenario: Visits on one day
- **WHEN** a caller requests `GET /invitations?visitDateFrom=2026-10-26&visitDateTo=2026-10-26`
- **THEN** only invitations whose visit day is 26 October 2026 in the
  tenant's timezone are returned, and `total` counts only those

#### Scenario: Undated invitation dated by its creation day
- **WHEN** an invitation with no scheduled visit date was created at 23:30
  on 25 October tenant-local time (already 26 October in UTC) and the list
  is requested with `visitDateFrom=visitDateTo=2026-10-25`
- **THEN** that invitation is included

#### Scenario: Reversed date range is rejected
- **WHEN** a caller requests `visitDateFrom=2026-10-27&visitDateTo=2026-10-26`
- **THEN** the system returns a validation error

#### Scenario: Upcoming only
- **WHEN** a branch has an `approved` invitation not yet checked in, an
  `approved` invitation whose `expiresAt` has passed, and a `checked_in`
  invitation, and the list is requested with `upcoming=true`
- **THEN** only the first invitation is returned

#### Scenario: Expired pending requests excluded
- **WHEN** the list is requested with `status=submitted&excludeExpired=true`
  and one of two `submitted` invitations has an `expiresAt` in the past
- **THEN** only the other one is returned

#### Scenario: Narrowing to an authorized branch
- **WHEN** a caller holding `invitations:view-all` at Branches A and B
  requests the list with `branchId` set to Branch A
- **THEN** only Branch A's invitations are returned

#### Scenario: branchId outside the caller's authorization
- **WHEN** a caller in the default branch-scoped mode requests the list
  with `branchId` set to a branch where they don't hold
  `invitations:view-all`
- **THEN** the system returns 403 and no data

#### Scenario: branchId never widens the relevantToMe set
- **WHEN** a host requests `GET /invitations?relevantToMe=true` with
  `branchId` set to a branch where they hold no role
- **THEN** only invitations already relevant to that host at that branch
  are returned, and no other invitation is revealed

#### Scenario: Export honours the drill-down filters
- **WHEN** a caller exports with `status=submitted&excludeExpired=true` and
  `branchId` set to Branch A
- **THEN** the file contains exactly the invitations the list returns for
  the same parameters
