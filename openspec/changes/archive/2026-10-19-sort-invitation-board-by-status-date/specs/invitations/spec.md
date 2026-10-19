## MODIFIED Requirements

### Requirement: Employee Lists Invitations at Their Authorized Branches
The system SHALL let an authenticated caller holding `invitations:view-all`
list invitations, paginated, sorted, and filterable by `status`,
`registrationType`, and `source`. A request supplying `X-Branch-ID` SHALL be
narrowed to that one branch, rejected with 404/403 the same way other
branch-scoped endpoints reject an unknown or unauthorized branch id. A
request omitting `X-Branch-ID` SHALL return invitations across every branch
the caller holds `invitations:view-all` at, rejected with 403 only if that
set is empty. Holding `invitations:view` alone (without
`invitations:view-all`) SHALL NOT grant access to this branch-wide listing:
such a caller (e.g. a `host`) finds their own work only through
`relevantToMe=true` ("Caller Lists Invitations Relevant to Themselves via
relevantToMe"). Each row in the response SHALL include enough detail to
identify and triage the invitation (tracking ID, registration type, source,
status, `visitorCategoryId`, primary contact name, primary contact photo
URL, purpose of visit, expiry/submission timestamps, `statusChangedAt`)
without the per-row visitor/vehicle detail the single-invitation tracking
lookup returns.

`sortBy` SHALL accept `submitted_at` (the default), `created_at`, and
`status_changed_at`, each with `sortOrder` `asc` or `desc` (default
`desc`). Each row's **status-changed time** is when the invitation entered
its current status:

| Current status | Status-changed time |
|---|---|
| `submitted` | the latest of `submittedAt`, the approval-revert time, and — only for an invitation that came back from `archived` via reschedule — the reschedule time |
| `approved` | `approvedAt` |
| `checked_in` | the latest check-in time |
| `checked_out` | the latest check-out time |
| `denied` | the denial time |
| `archived` | `archivedAt` |

When that timestamp is missing, the status-changed time SHALL fall back to
`submittedAt`, then to the creation time, so it is never null.
`sortBy=status_changed_at` SHALL order rows by this value, and every row
SHALL expose it as `statusChangedAt`. Every sort SHALL break ties
deterministically, so walking consecutive pages of an unchanged result set
returns each invitation exactly once. The default sort and every existing
field SHALL keep their current meaning.

#### Scenario: Caller with company-wide access lists across all their branches
- **WHEN** a caller with `invitations:view-all` granted company-wide requests
  `GET /invitations` without an `X-Branch-ID` header
- **THEN** the response includes invitations from every branch, paginated
  per the requested page/pageSize

#### Scenario: X-Branch-ID narrows the result to one branch
- **WHEN** a caller with `invitations:view-all` at a specific branch requests
  `GET /invitations` with that branch's `X-Branch-ID`
- **THEN** the response includes only that branch's invitations

#### Scenario: Unauthorized branch id rejected
- **WHEN** a caller requests `GET /invitations` with an `X-Branch-ID` for a
  branch they do not hold `invitations:view-all` at
- **THEN** the system returns 403 and no invitation data

#### Scenario: Caller lacks permission everywhere
- **WHEN** a caller with no `invitations:view-all` grant at any branch
  requests `GET /invitations` without an `X-Branch-ID` header
- **THEN** the system returns 403

#### Scenario: A host holding only invitations:view cannot use the branch-wide listing
- **WHEN** a caller holding the `host` role (which grants `invitations:view`
  but not `invitations:view-all`) at a branch requests `GET /invitations`
  without `relevantToMe`, with or without that branch's `X-Branch-ID`
- **THEN** the system returns 403 and no invitation data, even though
  invitations exist at that branch

#### Scenario: Reception, Security, and Admin keep the branch-wide listing
- **WHEN** a caller holding the `reception`, `security`, or `admin` role at
  a branch requests `GET /invitations` without `relevantToMe`
- **THEN** the response includes every invitation at that branch, since
  each of those roles grants `invitations:view-all`

#### Scenario: Filtering by status, registration type, and source
- **WHEN** a caller requests `GET /invitations` with `status`,
  `registrationType`, and/or `source` query parameters set
- **THEN** the response includes only invitations matching every supplied
  filter

#### Scenario: Sorting is validated against a whitelist
- **WHEN** a caller requests `GET /invitations` with a `sortBy` value that
  is not one of the endpoint's documented sortable fields
- **THEN** the system rejects the request with a validation error rather
  than passing the value through to the database

#### Scenario: List rows omit visitor and vehicle detail
- **WHEN** a caller lists invitations via `GET /invitations`
- **THEN** each row includes tracking ID, registration type, source,
  status, `visitorCategoryId`, primary contact name, primary contact photo
  URL, purpose of visit, and expiry/submission timestamps, and does not
  include the per-visitor or per-vehicle detail that `GET /invitations/track`
  returns for a single invitation

#### Scenario: List row surfaces the primary contact's photo URL when one was captured
- **WHEN** a caller lists invitations via `GET /invitations` and an
  invitation's primary contact has a stored photo
- **THEN** that row includes a resolvable URL for the photo, matching the
  URL the tracking/detail endpoints return for the same invitation

#### Scenario: List row omits the photo field when no photo was captured
- **WHEN** a caller lists invitations via `GET /invitations` and an
  invitation's primary contact has no stored photo
- **THEN** that row's photo URL field is null, and the row is otherwise
  unaffected

#### Scenario: Default sort is unchanged
- **WHEN** a caller requests `GET /invitations` without `sortBy`
- **THEN** rows are ordered newest first by `submittedAt`, exactly as
  before this change

#### Scenario: Checked-in column orders by most recent check-in
- **WHEN** invitation A was submitted three days ago and checked in five
  minutes ago, invitation B was submitted yesterday and checked in two
  hours ago, and a caller requests
  `GET /invitations?status=checked_in&sortBy=status_changed_at`
- **THEN** A is listed before B, and each row's `statusChangedAt` equals
  its check-in time

#### Scenario: Each status column orders by its own status time
- **WHEN** a caller requests `GET /invitations?status=<s>&sortBy=status_changed_at`
  for each `s` in `approved`, `checked_out`, `denied`, and `archived`
- **THEN** rows are ordered newest first by, respectively, the approval,
  latest check-out, denial, and archive time

#### Scenario: An invitation whose approval was reverted returns to the top of Requested
- **WHEN** an invitation submitted a week ago is approved and then has its
  approval reverted just now, and a caller requests
  `GET /invitations?status=submitted&sortBy=status_changed_at`
- **THEN** that invitation is ordered by the revert time, ahead of
  invitations submitted earlier today

#### Scenario: An archived invitation rescheduled back into approval is ordered by the reschedule
- **WHEN** an archived invitation is rescheduled, returning it to
  `submitted`, and a caller requests
  `GET /invitations?status=submitted&sortBy=status_changed_at`
- **THEN** that invitation is ordered by the reschedule time rather than
  its original submission time

#### Scenario: Ascending order is supported
- **WHEN** a caller requests
  `GET /invitations?sortBy=status_changed_at&sortOrder=asc`
- **THEN** rows are ordered oldest status-changed time first

#### Scenario: Mixed-status list orders by each row's own status time
- **WHEN** a caller requests `GET /invitations?sortBy=status_changed_at`
  without a `status` filter
- **THEN** rows of different statuses are interleaved by their own
  status-changed time, newest first

#### Scenario: Equal sort keys page stably
- **WHEN** more invitations than one page holds share the same sort
  timestamp, and a caller walks every page of
  `GET /invitations?status=<s>&sortBy=<any>` with no data changes in between
- **THEN** every matching invitation appears exactly once across the pages
