## Purpose

Gives staff a date-ranged calendar feed of invitations and walk-in visits.
Each caller sees exactly the visits their role entitles them to, so the
staff portal can lay out who is visiting when, without paging through the
invitation list.

## ADDED Requirements

### Requirement: Calendar Feed Returns Visits in a Local Date Range
The system SHALL expose `GET /invitations/calendar` to any authenticated
staff user. It SHALL take required `from` and `to` query parameters, each an
ISO calendar date (`YYYY-MM-DD`) interpreted in the visit timezone (the
company's default timezone, falling back to the tenant's, then UTC — the
same zone that decides when an invitation expires), and
SHALL return every non-deleted invitation whose event date falls on or
between them (inclusive).

The system SHALL reject the request with 422 when:
- `to` is earlier than `from`;
- the range spans more than 42 days; or
- either date is missing or malformed.

Walk-in registrations are invitations (`source: "visitor_walk_in"`) and
SHALL appear under the same rules as any other invitation.

#### Scenario: Visits inside the range are returned
- **WHEN** a caller requests `from=2026-10-01&to=2026-10-31` and visible
  invitations are scheduled for 2026-09-30, 2026-10-01, 2026-10-31 and
  2026-11-01
- **THEN** the response contains only the 2026-10-01 and 2026-10-31
  invitations

#### Scenario: Range longer than six weeks is rejected
- **WHEN** a caller requests `from=2026-10-01&to=2026-11-12` (43 days)
- **THEN** the response is 422 and no invitations are returned

#### Scenario: Reversed range is rejected
- **WHEN** a caller requests `from=2026-10-10&to=2026-10-01`
- **THEN** the response is 422

#### Scenario: Soft-deleted invitations never appear
- **WHEN** an invitation scheduled inside the range has been soft-deleted
- **THEN** it is absent from both the events and the day totals

#### Scenario: Walk-in appears on its visit date
- **WHEN** a walk-in was registered and checked in on 2026-10-14 at a
  branch the caller can see
- **THEN** it appears as an event on 2026-10-14 with source
  `visitor_walk_in`

### Requirement: Event Date Is the Scheduled Visit Date
An event's `date` SHALL be the invitation's scheduled visit date. Only when
an invitation has no scheduled visit date SHALL its `date` be the
calendar date of its check-in in the visit timezone. An invitation with neither a
visit date nor a check-in SHALL NOT appear.

Each event's `time` SHALL be the scheduled visit time, or null when none was
given. Its `checkedInAt` and `checkedOutAt` SHALL be the actual timestamps,
or null. A rescheduled invitation SHALL appear only on its current date, not
on its previous one.

#### Scenario: Scheduled date wins over actual check-in date
- **WHEN** an invitation is scheduled for 2026-10-14 but the visitor checked
  in late on 2026-10-15 (visit timezone)
- **THEN** the event's `date` is 2026-10-14 and its `checkedInAt` carries
  the 2026-10-15 timestamp

#### Scenario: Rescheduled visit moves to its new date
- **WHEN** an invitation originally scheduled for 2026-10-14 is rescheduled
  to 2026-10-20
- **THEN** a feed covering both dates lists it once, on 2026-10-20

#### Scenario: Legacy row without a visit date falls back to check-in date
- **WHEN** an invitation has no scheduled visit date and was checked in at
  2026-10-14T20:00Z where the visit timezone is Asia/Kolkata
- **THEN** its event `date` is 2026-10-15

### Requirement: Calendar Scope Is Resolved From the Caller's Permissions
The endpoint SHALL accept `scope` with values `auto` (the default), `mine`
and `branch`. The response SHALL state the scope it applied as `mine` or
`branch`.

- **`mine`** SHALL return exactly the invitations that
  `GET /invitations?relevantToMe=true` would return to the same caller. It
  SHALL ignore `X-Branch-ID`.
- **`branch`** SHALL require `invitations:view-all` and SHALL return
  invitations at the caller's authorized branches for that permission:
  - When `X-Branch-ID` is supplied, only that branch, with the same 404/403
    checks as the invitation list.
  - Otherwise every branch the caller holds the permission at (all branches
    for a company-wide grant).
  - A caller holding the permission at no branch SHALL receive 403.
- **`auto`** SHALL behave as `branch` when the caller holds
  `invitations:view-all` at one or more branches (or company-wide), and as
  `mine` otherwise.

The `tenant_id` and branch set SHALL come only from the access token and the
caller's role assignments. They SHALL NOT come from any request parameter
other than the authorized `X-Branch-ID`.

#### Scenario: Host sees only their own visitors
- **WHEN** a host (no `invitations:view-all`) requests the calendar with
  the default scope, and the range contains one invitation where they are
  the resolved host and one hosted by another employee at the same branch
- **THEN** `scope` is `mine` and only their own invitation is returned

#### Scenario: Host asking for branch scope is refused
- **WHEN** a host requests `scope=branch`
- **THEN** the response is 403 and the denial is logged at WARNING

#### Scenario: Reception sees the whole authorized branch
- **WHEN** a reception user authorized at branch A only requests the
  calendar with the default scope, and the range contains invitations at
  branches A and B
- **THEN** `scope` is `branch` and only branch A's invitations are returned

#### Scenario: Security sees the whole authorized branch
- **WHEN** a security user authorized at branch A requests the calendar
  with the default scope
- **THEN** `scope` is `branch` and every invitation at branch A in the
  range is returned, including ones they have no personal involvement in

#### Scenario: X-Branch-ID narrows branch scope
- **WHEN** an admin with a company-wide grant sends `X-Branch-ID` for
  branch B
- **THEN** only branch B's invitations are returned

#### Scenario: X-Branch-ID for an unauthorized branch is refused
- **WHEN** a reception user authorized at branch A sends `X-Branch-ID` for
  branch B
- **THEN** the response is 403

#### Scenario: Branch viewer can still ask for their personal set
- **WHEN** a reception user requests `scope=mine`
- **THEN** `scope` is `mine` and the result equals their `relevantToMe`
  invitation list restricted to the range

#### Scenario: Calendar and list never disagree for a host
- **WHEN** a host requests the calendar for a range, and separately lists
  `GET /invitations?relevantToMe=true`
- **THEN** every calendar event is present in that list, and every listed
  invitation whose event date is in the range is a calendar event

#### Scenario: Another tenant's invitations are unreachable
- **WHEN** two tenants each have an invitation on the same date
- **THEN** a caller of tenant 1 sees only tenant 1's invitation

### Requirement: Calendar Status Filter
The endpoint SHALL accept a repeatable `status` query parameter, each value
one of the invitation statuses. When it is omitted, the feed SHALL include
every status except `denied`. When it is supplied, the feed SHALL include
only the listed statuses. An unknown status SHALL be rejected with 422.

#### Scenario: Denied invitations hidden by default
- **WHEN** the range contains one `approved` and one `denied` invitation and
  no `status` is sent
- **THEN** only the `approved` invitation is returned

#### Scenario: Explicit status filter
- **WHEN** `status=checked_in&status=checked_out` is sent
- **THEN** only invitations in those two statuses are returned, and the day
  totals count only those

#### Scenario: Missed visits are shown by default
- **WHEN** an invitation in the range was archived by the lifecycle sweep
  without the visitor arriving
- **THEN** it is returned with status `archived`

### Requirement: Day Totals Are Exact and the Event List Is Bounded
The response SHALL include `days`: one entry per date in the requested range,
in ascending order, each with that date's `total` event count under the
applied scope and status filter. A date with no events SHALL be present with
`total: 0`.

`events` SHALL be ordered by date, then scheduled time (nulls last), then
primary contact name. It SHALL hold at most 1,000 events. When more match,
the first 1,000 in that order SHALL be returned and `truncated` SHALL be
true. Otherwise `truncated` SHALL be false.

`days` totals SHALL always reflect every matching invitation, whether or not
`events` was truncated.

#### Scenario: Empty days are present with zero
- **WHEN** a seven-day range has visits on only two of the days
- **THEN** `days` has seven entries and five of them have `total` 0

#### Scenario: Totals stay exact when events are truncated
- **WHEN** 1,200 invitations match the range
- **THEN** `events` has 1,000 entries, `truncated` is true, and the sum of
  `days[].total` is 1,200

### Requirement: Calendar Events Carry Only Display Fields
Each event SHALL carry:
- `id` and `trackingId`;
- `status`;
- `source`;
- `date`, `time` and `expectedDuration`;
- `checkedInAt` and `checkedOutAt`;
- `primaryContactFullName` and `visitorCount` (the primary contact plus
  co-visitors);
- `hostId` and `hostFullName`;
- `branchId`, `branchName` and `buildingName`;
- `purposeOfVisit`;
- `visitorCategoryName` and `visitorCategoryBadgeColor`.

An event SHALL NOT carry a phone number, an email address, an identity
document type or number, a photo or document storage key, or a custom field
value.

The response SHALL also carry `scope`, `timezone` (the visit timezone's IANA name),
`from`, `to` and `generatedAt`. All fields SHALL be camelCase.

#### Scenario: Event shape excludes contact and identity data
- **WHEN** an invitation whose primary contact has a phone, email and ID
  proof appears in the feed
- **THEN** its event contains the contact's full name and none of the
  phone, email, ID-proof or photo data

#### Scenario: Host name resolved without per-row queries
- **WHEN** the feed returns events for many different hosts
- **THEN** every event with a resolved host carries `hostFullName`, and the
  endpoint issues a bounded number of queries regardless of event count

#### Scenario: Unassigned host is null
- **WHEN** an invitation's ownership step has not been delegated yet
- **THEN** its `hostId` and `hostFullName` are null

### Requirement: Calendar Endpoint Is Documented and Unauthenticated Access Is Refused
The route SHALL declare `response_model=Envelope[CalendarFeedOut]` and be
secured with the bearer scheme in the OpenAPI schema. A request without a
valid access token SHALL receive 401 through the standard error envelope.

#### Scenario: No token
- **WHEN** `GET /invitations/calendar` is called without an Authorization
  header
- **THEN** the response is 401 with the standard error envelope

#### Scenario: Swagger shows the typed response
- **WHEN** `/openapi.json` is fetched in a non-production environment
- **THEN** the calendar route's 200 response references the camelCase
  `CalendarFeedOut` schema
