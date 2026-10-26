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
resolved branch scope:

- `scheduledTodayCount`: invitations whose visit day (see "Branch-Wide
  Dashboard Analytics") is today and whose status is `approved`,
  `checked_in` or `checked_out`;
- `scheduledTodayCheckedInCount`: those of the `scheduledTodayCount`
  invitations that have been checked in at least once. It SHALL never
  exceed `scheduledTodayCount`;
- `checkedInTodayCount`: invitations whose most recent check-in time falls
  today, whatever their visit day. It SHALL equal the sum of
  `hourlyCheckInsToday` from the analytics endpoint for the same scope;
- `checkedInCount`: invitations currently checked in (status `checked_in`);
- `openPendingApprovalCount`: invitations awaiting approval (status
  `submitted`) whose `expiresAt` is still in the future;
- `oldestOpenPendingSubmittedAt`: the submission time of the oldest of
  those open pending invitations, or null when there are none;
- `pendingApprovalCount`: every `submitted` invitation, including expired
  ones. It is kept unchanged for existing clients and is **deprecated** in
  favour of `openPendingApprovalCount`;
- `oldestPendingSubmittedAt`: the submission time of the oldest of those
  `submitted` invitations, or null when there are none. **Deprecated** in
  favour of `oldestOpenPendingSubmittedAt`;
- `upcomingVisitorCount`: upcoming visitors (status `approved`, never
  checked in, not expired). It SHALL use exactly the same filter as the
  upcoming-visitors preview;
- `upcomingVisitors`: a bounded preview list of those upcoming visitors,
  ordered by soonest expiry;
- `visitsTodayCount`: the count of invitations created today. It is kept
  unchanged for existing clients and is **deprecated** in favour of
  `scheduledTodayCount`;
- `today`: the tenant-local calendar date the figures were computed for;
- `generatedAt`: the UTC time the response was computed.

"Today" SHALL be evaluated in the visit timezone (see "Branch-Wide
Dashboard Analytics"), not UTC or server local time.

Every count except the deprecated ones SHALL equal the `total` that
`GET /invitations` returns for the same caller, the same branch scope and
the matching drill-down filters (see the `invitations` capability's
"Invitation List Supports Dashboard Drill-Down Filters"):

| Count | Matching list filters |
|---|---|
| `scheduledTodayCount` | `visitDateFrom` = `visitDateTo` = `today`, summed over statuses `approved`, `checked_in`, `checked_out` |
| `checkedInCount` | `status=checked_in` |
| `openPendingApprovalCount` | `status=submitted&excludeExpired=true` |
| `upcomingVisitorCount` | `upcoming=true` |

The endpoint SHALL accept an optional `branchId` query parameter. When it
is supplied, the caller SHALL hold `invitations:view` at that branch and
the response SHALL be scoped to that branch alone. When it is omitted, the
response SHALL aggregate across every branch the caller holds
`invitations:view` at.

Each row in the upcoming-visitors preview SHALL include:
- the invitation's `trackingId`, so the caller can act on it directly
  through the canonical invitation endpoint
  (`PATCH /api/v2/invitations/{trackingId}/check-in`, see the
  `invitations` capability) without a separate lookup;
- the resolved host's full name (`hostFullName`, null when no host is
  resolved);
- the scheduled visit date and time (`preferredVisitDate`,
  `preferredVisitTime`, each null when not set).

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

#### Scenario: Upcoming count agrees with the preview filter
- **WHEN** a branch has three non-expired `approved` invitations, one of
  which has already been checked in and checked out once
- **THEN** `upcomingVisitorCount` is 2 and the preview lists the same 2
  invitations

#### Scenario: "Today" boundary follows tenant timezone
- **WHEN** the overview is requested for a tenant configured with a
  non-UTC timezone, at a moment where UTC and that timezone disagree on the
  calendar date
- **THEN** `scheduledTodayCount`, `scheduledTodayCheckedInCount`,
  `checkedInTodayCount` and `visitsTodayCount` reflect the tenant's local
  calendar date, and `today` is that local date

#### Scenario: Scheduled-today counts visits, not creations
- **WHEN** an invitation created last week is `approved` for a visit today,
  and another invitation created today is `approved` for a visit next week
- **THEN** `scheduledTodayCount` counts the first and not the second, while
  the deprecated `visitsTodayCount` counts the second and not the first

#### Scenario: Checked in so far never exceeds expected today
- **WHEN** two visits are scheduled for today and one of them has checked
  in, and a visitor scheduled for tomorrow also checked in today
- **THEN** `scheduledTodayCount` is 2, `scheduledTodayCheckedInCount` is 1
  and `checkedInTodayCount` is 2

#### Scenario: Oldest pending submission is reported
- **WHEN** a branch has two `submitted` invitations, submitted at 09:00 and
  11:00 today, both still inside their visit window
- **THEN** `openPendingApprovalCount` and the deprecated
  `pendingApprovalCount` are both 2, and `oldestOpenPendingSubmittedAt` and
  the deprecated `oldestPendingSubmittedAt` are both the 09:00 submission
  time

#### Scenario: Expired pending requests are left out of the open count
- **WHEN** a branch has two `submitted` invitations still inside their
  visit window, submitted at 09:00 and 11:00 today, and one `submitted`
  invitation whose `expiresAt` passed three days ago
- **THEN** `openPendingApprovalCount` is 2 and
  `oldestOpenPendingSubmittedAt` is the 09:00 submission time, while the
  deprecated `pendingApprovalCount` is 3 and `oldestPendingSubmittedAt` is
  the expired request's submission time

#### Scenario: Counts equal the totals of their drill-down lists
- **WHEN** a caller requests the overview with `branchId` set to Branch A,
  then requests `GET /invitations` with `branchId` set to Branch A and the
  matching filters for each count
- **THEN** each list's `total` (summed over statuses for
  `scheduledTodayCount`) equals the corresponding count

#### Scenario: Upcoming-visitors preview rows carry trackingId
- **WHEN** the overview's upcoming-visitors preview is returned
- **THEN** every row includes that invitation's `trackingId`, `hostFullName`,
  `preferredVisitDate` and `preferredVisitTime`

### Requirement: Paginated Check-Ins Log
The system SHALL provide `GET /admin/dashboard/checkins`, a paginated list
of every invitation that has been checked in at least once (status
`checked_in` or `checked_out`), using the standard `page`/`pageSize`
pagination envelope. The endpoint SHALL accept the same optional `branchId`
query parameter and branch-scope resolution as the overview endpoint, and
SHALL support sorting by check-in time. Each row SHALL include the resolved
host's full name (`hostFullName`, null when no host is resolved) alongside
`hostId`.

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

#### Scenario: Rows carry the host's name
- **WHEN** a checked-in invitation's resolved host is "Priya Nair"
- **THEN** that row's `hostFullName` is "Priya Nair"

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
`GET /admin/dashboard/overview`, `GET /admin/dashboard/checkins`,
`GET /admin/dashboard/search`, and `GET /admin/dashboard/analytics` SHALL
resolve their branch scope against `invitations:view-all` rather than
`invitations:view`. Wherever the "Dashboard Overview Summary", check-ins,
"Dashboard Topbar Search" and "Branch-Wide Dashboard Analytics"
requirements say the caller SHALL hold `invitations:view` at a branch (or
aggregate across every branch they hold it at), the permission consulted
SHALL be `invitations:view-all`.

These endpoints aggregate or search across every invitation at a branch,
which only a branch-wide viewer (Reception, Security, Admin) may see. A
caller holding only `invitations:view` (e.g. a `host`) SHALL be rejected
the same way as a caller with no grant.

#### Scenario: A host cannot search visitor names branch-wide
- **WHEN** a caller holding only the `host` role at a branch requests
  `GET /admin/dashboard/search?query=carter`
- **THEN** the system returns 403 and no invitation data

#### Scenario: A host cannot read branch-wide dashboard counts
- **WHEN** a caller holding only the `host` role at a branch requests
  `GET /admin/dashboard/overview` or `GET /admin/dashboard/checkins`
- **THEN** the system returns 403

#### Scenario: A host cannot read branch-wide analytics
- **WHEN** a caller holding only the `host` role at a branch requests
  `GET /admin/dashboard/analytics`
- **THEN** the system returns 403 and no data

#### Scenario: Branch-wide viewers keep the dashboard
- **WHEN** a caller holding the `admin`, `reception`, or `security` role at
  a branch requests any of the four dashboard endpoints scoped to it
- **THEN** the system returns 200 with that branch's data

### Requirement: Personal Dashboard Overview Scoped to the Caller's Relevant Invitations
The system SHALL provide `GET /admin/dashboard/my-overview` to any
authenticated user of the tenant. No branch-level permission is required,
the same gate as `GET /invitations?relevantToMe=true`. It returns counts
and a preview computed **only** over the invitations relevant to the
caller. That is exactly the set `GET /invitations?relevantToMe=true` would
return for the same caller at the same moment. It SHALL ignore
`X-Branch-ID` and SHALL NOT accept a `branchId` parameter. The response
SHALL contain:

- `visitsToday`: relevant invitations whose visit day (see "Branch-Wide
  Dashboard Analytics") is today and whose status is `approved`,
  `checked_in` or `checked_out`;
- `insideNow`: relevant invitations currently `checked_in`;
- `openAwaitingApproval`: relevant invitations in status `submitted` whose
  `expiresAt` is still in the future;
- `awaitingApproval`: every relevant invitation in status `submitted`,
  including expired ones. It is kept unchanged for existing clients and is
  **deprecated** in favour of `openAwaitingApproval`;
- `upcoming`: relevant invitations in status `approved` that have never
  been checked in and have not expired;
- `upcomingPreview`: up to 5 of those upcoming invitations, soonest
  scheduled visit first. Each row carries `trackingId`, the visitor's name,
  scheduled date and time, and purpose;
- `today`: the tenant-local calendar date the figures were computed for;
- `generatedAt`: the UTC time the response was computed.

"Today" SHALL be evaluated in the visit timezone, the same as the
branch-wide overview. `archived` and `denied` invitations SHALL count
toward none of the figures. The response SHALL be read-only and SHALL NOT
reveal any invitation outside the caller's relevant set.

Every count except the deprecated one SHALL equal the `total` of
`GET /invitations?relevantToMe=true` for the same caller with the matching
drill-down filters: `visitsToday` with `visitDateFrom` = `visitDateTo` =
`today` (summed over `approved`, `checked_in`, `checked_out`), `insideNow`
with `status=checked_in`, `openAwaitingApproval` with
`status=submitted&excludeExpired=true`, and `upcoming` with `upcoming=true`.

#### Scenario: A host sees only their own visits
- **WHEN** host H, who holds only the `host` role, requests
  `my-overview` at a branch with 10 invitations, 3 of which name H as
  resolved host
- **THEN** every count and the preview reflect only those 3 invitations,
  and the request succeeds with 200

#### Scenario: Counts agree with the relevantToMe list
- **WHEN** a caller requests `my-overview` and then
  `GET /invitations?relevantToMe=true&status=submitted&excludeExpired=true`
- **THEN** `openAwaitingApproval` equals that list's total

#### Scenario: Expired requests are left out of the open count
- **WHEN** a caller's relevant set contains one `submitted` invitation
  inside its visit window and one whose `expiresAt` has passed
- **THEN** `openAwaitingApproval` is 1 and the deprecated
  `awaitingApproval` is 2

#### Scenario: Archived and denied visits are excluded
- **WHEN** a caller's relevant set contains one `archived` and one
  `denied` invitation, both scheduled for today
- **THEN** neither is counted in `visitsToday`, `upcoming` or any other
  figure

#### Scenario: Unauthenticated request is rejected
- **WHEN** `my-overview` is requested without a valid access token
- **THEN** the system returns 401 and no data

#### Scenario: Branch header does not widen the scope
- **WHEN** a host sends `my-overview` with `X-Branch-ID` set to a branch
  where they hold no role
- **THEN** the response still reflects only the host's own relevant
  invitations

#### Scenario: Preview is bounded and ordered
- **WHEN** a caller has 8 upcoming relevant invitations
- **THEN** `upcoming` is 8 and `upcomingPreview` lists the 5 with the
  soonest scheduled visit, soonest first

#### Scenario: Response names the tenant-local date
- **WHEN** `my-overview` is requested for a tenant whose timezone is
  already on the next calendar day relative to UTC
- **THEN** `today` is the tenant's local date

### Requirement: Branch-Wide Dashboard Analytics
The system SHALL provide `GET /admin/dashboard/analytics`, accepting the
same optional `branchId` query parameter and branch-scope resolution as the
overview endpoint, and a `range` query parameter of `7d` or `30d`
(default `7d`). Any other `range` value SHALL be rejected with a validation
error.

The range SHALL cover today and the preceding 6 (for `7d`) or 29 (for
`30d`) calendar days. Every dashboard endpoint SHALL compute every day and
hour boundary, and report `timezone`, in the **visit timezone**: the
company's default timezone, else the tenant's timezone, else UTC (an
invalid name is skipped). This is the same zone that decides each
invitation's visit day and `expiresAt`, so "today" on the dashboard is the
same day the rest of the system uses. "Tenant-local" below means local to
the visit timezone.

An invitation's **visit day** is its scheduled visit date or, when it has
none, the tenant-local date it was created. Every dashboard figure that
dates a visit (the overview's scheduled-today counts, the personal
overview's `visitsToday`, and every series below except
`hourlyCheckInsToday`) SHALL use the visit day, and so SHALL the
`visitDateFrom`/`visitDateTo` list filters.

Throughout this requirement, a **scheduled visit** is an invitation in
status `approved`, `checked_in`, `checked_out` or `archived`, dated by its
visit day. The response SHALL contain:

- `range`, `timezone` (the IANA name actually used), `today` and
  `generatedAt`;
- `dailyTrend`: exactly one row per day in the range, oldest first, with
  zero counts for days without visits. Each row carries:
  - `date`;
  - `scheduled`: scheduled visits for that day;
  - `checkedIn`: those of them that have been checked in at least once;
  - `noShow`: those of them in status `archived`;
- `hourlyCheckInsToday`: exactly 24 rows (`hour` 0–23), each counting the
  invitations whose most recent check-in time falls in that tenant-local
  hour of today;
- `statusBreakdown`: one row for each of `submitted`, `approved`,
  `checked_in`, `checked_out`, `denied` and `archived` (zero counts
  included), counting invitations whose visit day falls in the range. Each
  row's count SHALL equal the `total` of `GET /invitations` for the same
  scope with that `status` and `visitDateFrom`/`visitDateTo` set to the
  range's first and last day;
- `topPurposes` and `topDepartments`: the top 5 labels by scheduled-visit
  count in the range, highest first, ties broken alphabetically. A further
  `Other` row SHALL sum every remaining label and SHALL appear only when
  that sum is above zero. Labels are resolved in this order:
  1. the configured purpose or department name;
  2. otherwise the free-text value entered on the invitation, grouped
     case-insensitively;
  3. otherwise `Not specified`.

#### Scenario: Seven-day trend is zero-filled and ordered
- **WHEN** a branch had scheduled visits on only two of the last seven
  local days and `range=7d` is requested
- **THEN** `dailyTrend` has 7 rows, oldest first, ending with today, and the
  five days without visits carry zero counts

#### Scenario: Trend separates attended visits from no-shows
- **WHEN** yesterday had 4 scheduled visits, of which 3 were checked in and
  1 was archived by the no-show sweep
- **THEN** yesterday's row reports `scheduled` 4, `checkedIn` 3 and
  `noShow` 1

#### Scenario: Today's trend point agrees with the overview
- **WHEN** the overview and the analytics are requested for the same scope
  on the same day
- **THEN** today's `dailyTrend` row reports `checkedIn` equal to the
  overview's `scheduledTodayCheckedInCount`, and `scheduled` equal to the
  overview's `scheduledTodayCount` plus today's `noShow`

#### Scenario: An undated visit is dated by its creation day everywhere
- **WHEN** an `approved` invitation with no scheduled visit date was
  created today
- **THEN** it is counted in the overview's `scheduledTodayCount`, in
  today's `dailyTrend` row, and in the `approved` row of `statusBreakdown`

#### Scenario: Dashboard uses the company's timezone, not only the tenant's
- **WHEN** the tenant's timezone is `UTC`, the company's default timezone is
  `Asia/Kolkata`, and the overview and analytics are requested at 02:00 IST
  (20:30 UTC the previous day)
- **THEN** `today` is the IST date, `timezone` is `Asia/Kolkata`, and a
  check-in at 01:30 IST is counted in the `hour` 1 row of
  `hourlyCheckInsToday`

#### Scenario: Hourly arrivals use the tenant's local hours
- **WHEN** a tenant in `Asia/Kolkata` has visitors checked in at 09:10 and
  09:50 local time today
- **THEN** the `hour` 9 row of `hourlyCheckInsToday` reports 2, and the list
  has 24 rows

#### Scenario: Status breakdown includes zero rows
- **WHEN** a branch has only `approved` and `checked_out` invitations
  scheduled in the range
- **THEN** `statusBreakdown` still lists all six statuses, with zero for the
  four that have no invitations

#### Scenario: Status breakdown equals its drill-down list
- **WHEN** the `denied` row of `statusBreakdown` for `range=7d` reports 3
- **THEN** `GET /invitations?status=denied` with `visitDateFrom` set to the
  first day of the range and `visitDateTo` set to today, in the same scope,
  returns a `total` of 3

#### Scenario: Top purposes roll the remainder into Other
- **WHEN** scheduled visits in the range span 7 distinct purposes
- **THEN** `topPurposes` lists the 5 most frequent purposes followed by one
  `Other` row whose count is the sum of the remaining two

#### Scenario: Unknown range is rejected
- **WHEN** the analytics endpoint is requested with `range=90d`
- **THEN** the system returns a validation error and computes nothing

#### Scenario: Analytics respect branch scope
- **WHEN** a caller authorized at Branch A only requests analytics with no
  `branchId`, and Branch B has visits in the range
- **THEN** no figure includes any Branch B invitation

### Requirement: Personal Dashboard Analytics
The system SHALL provide `GET /admin/dashboard/my-analytics` to any
authenticated user of the tenant, under the same gate and relevance rule as
`GET /admin/dashboard/my-overview`. It SHALL ignore `X-Branch-ID`, SHALL
NOT accept a `branchId` parameter, and SHALL accept the same `range` values
as the branch-wide analytics endpoint.

It SHALL return `range`, `timezone`, `today`, `generatedAt`, `dailyTrend`
and `statusBreakdown`. These are defined as in "Branch-Wide Dashboard
Analytics", but computed only over the invitations relevant to the caller.

#### Scenario: A host's analytics contain only their own visits
- **WHEN** host H, who holds only the `host` role, requests `my-analytics`
  at a branch where 3 of 10 invitations in the range name H as resolved host
- **THEN** the `dailyTrend` and `statusBreakdown` totals add up to those 3
  invitations only, and the request succeeds with 200

#### Scenario: Unauthenticated request is rejected
- **WHEN** `my-analytics` is requested without a valid access token
- **THEN** the system returns 401 and no data
