## ADDED Requirements

### Requirement: Calendar Feed Can Limit Events Per Day
`GET /invitations/calendar` SHALL accept an optional `perDayLimit` integer
from 1 to 100. A value outside that range SHALL be rejected with 422.

When `perDayLimit` is given, `events` SHALL contain, for each date, only the
first `perDayLimit` events of that date in the standard event order. The
other rules still apply:
- `days[].total` SHALL still count every matching event.
- The overall 1,000-event cap and the `truncated` flag SHALL still apply
  to the limited list.

When `perDayLimit` is omitted, the response SHALL be exactly as before.

#### Scenario: Busy day is limited, totals stay exact
- **WHEN** a week has 181 visits on Monday and 6 on Tuesday, and the feed
  is requested with `perDayLimit=10`
- **THEN** `events` holds the first 10 Monday visits and all 6 Tuesday
  visits, and `days` shows totals of 181 and 6

#### Scenario: Limit out of range
- **WHEN** the feed is requested with `perDayLimit=0` or `perDayLimit=101`
- **THEN** the response is 422

#### Scenario: Omitted limit keeps today's behaviour
- **WHEN** the feed is requested without `perDayLimit`
- **THEN** `events` is the same list the endpoint returned before this
  option existed

### Requirement: One Day's Visits Are Available Page by Page
The system SHALL expose `GET /invitations/calendar/day` to any
authenticated staff user. It SHALL take:
- a required `date` (`YYYY-MM-DD`, in the visit timezone);
- `page` (default 1) and `pageSize` (default 20, max 100);
- the same `scope` and repeatable `status` parameters as the feed;
- the optional `X-Branch-ID` header.

It SHALL return that date's events with the scope, branch, status,
event-date and display-field rules of the calendar feed, in the standard
event order. It SHALL use the standard pagination envelope (`data` plus
`pagination` with `page`, `pageSize`, `total` and `totalPages`).

The response SHALL also state the applied `scope`. Page N SHALL hold exactly
the events at positions `(N-1)·pageSize+1 … N·pageSize` of that order, so
`pageSize=10, page=1` equals the first 10 events the feed returns for that
date with `perDayLimit=10`.

- `total` SHALL equal that day's `days[].total` in the feed for the same
  scope, branch and statuses.
- A missing or malformed `date` SHALL be rejected with 422.
- `scope=branch` without `invitations:view-all` SHALL be refused with 403,
  as in the feed.

#### Scenario: Next page continues where the feed stopped
- **WHEN** Monday has 181 visits, the feed was requested with
  `perDayLimit=10`, and the day endpoint is then requested with
  `pageSize=10` and `page=2`
- **THEN** it returns visits 11–20 of Monday, with no visit repeated from
  the feed and none skipped

#### Scenario: Total agrees with the feed
- **WHEN** the day endpoint is requested for a date the feed reports with
  `total` 181
- **THEN** `pagination.total` is 181

#### Scenario: Host only pages through their own visits
- **WHEN** a host requests a day that has 30 visits at their branch, 4 of
  them theirs
- **THEN** `scope` is `mine` and `pagination.total` is 4

#### Scenario: Unauthorized branch
- **WHEN** a reception user authorized at branch A requests the day
  endpoint with `X-Branch-ID` for branch B
- **THEN** the response is 403

#### Scenario: Page past the end
- **WHEN** a page beyond `totalPages` is requested
- **THEN** `data` is empty and `pagination.total` is unchanged

## MODIFIED Requirements

### Requirement: Day Totals Are Exact and the Event List Is Bounded
The response SHALL include `days`: one entry per date in the requested range,
in ascending order, each with that date's `total` event count under the
applied scope and status filter. A date with no events SHALL be present with
`total: 0`.

`events` SHALL be ordered by date, then scheduled time (nulls last), then
primary contact name, then invitation id. The id makes the order total, so
paging through it never repeats or skips an event. That order is the
"standard event order" used by every calendar endpoint.

`events` SHALL hold at most 1,000 events. When more match, the first 1,000
in that order SHALL be returned and `truncated` SHALL be true. Otherwise
`truncated` SHALL be false.

`days` totals SHALL always reflect every matching invitation, whether or not
`events` was truncated or limited per day.

#### Scenario: Empty days are present with zero
- **WHEN** a seven-day range has visits on only two of the days
- **THEN** `days` has seven entries and five of them have `total` 0

#### Scenario: Totals stay exact when events are truncated
- **WHEN** 1,200 invitations match the range
- **THEN** `events` has 1,000 entries, `truncated` is true, and the sum of
  `days[].total` is 1,200

#### Scenario: Ties are broken by id
- **WHEN** two visits on the same day share the same time and primary
  contact name
- **THEN** they are always returned in the same relative order, by
  invitation id
