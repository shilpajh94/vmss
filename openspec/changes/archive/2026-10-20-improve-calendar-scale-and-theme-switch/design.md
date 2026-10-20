## Context

See proposal.md for motivation. The web half's design (day columns, lazy
loading, theme switch, responsive work) is in VMMS_WEB
`openspec/changes/improve-calendar-scale-and-theme-switch/design.md`.

Current API state:

- **Feed path.** `get_calendar_feed` resolves the scope (`auto`/`mine`/
  `branch`), then builds `CalendarCriteria`.
  `InvitationRepository.calendar_events` runs one column-select ordered by
  `event_date, preferred_visit_time NULLS LAST,
  primary_contact_full_name, id`, with `LIMIT 1001`.
  `calendar_day_totals` runs one `GROUP BY` over a subquery.
- **Event date.** `_calendar_event_date(tz)` is
  `COALESCE(preferred_visit_date, timezone(tz, checked_in_at)::date)`.
  The filters use two OR arms so the visit-date arm stays indexed.

## Goals / Non-Goals

**Goals:**
- Serve any day's visits in pages, with the exact same order, scope and
  filters as the feed.
- Keep a busy month or week response small.

**Non-Goals:**
- Cursor pagination. Offset paging matches api-conventions.md §1, and a
  day's list is human-scrolled.
- Changing the feed's default (no-`perDayLimit`) behaviour.

## Decisions

### A1. One shared criteria builder; scope resolution extracted

`get_calendar_feed`'s scope and visit-timezone resolution moves into
`_calendar_criteria(tenant_db, tenant, user, *, date_from, date_to, scope,
statuses, x_branch_id) -> tuple[CalendarCriteria, applied_scope, ZoneInfo]`.
Both the feed and the new day service call it, so the two can't drift on
who sees what. The day endpoint passes `date_from = date_to = date`.

### A2. `perDayLimit` via a window function

When `per_day_limit` is set, `calendar_events` wraps its select:

```
SELECT … , row_number() OVER (PARTITION BY event_date
                              ORDER BY preferred_visit_time NULLS LAST,
                                       primary_contact_full_name, id) AS rn
… WHERE <filters>
```

The outer query keeps `rn <= :per_day_limit`, then orders as before and
applies `LIMIT 1001`. It is still one statement and still column-only, so
there's no per-row query (query-performance.md §2).

`event_date` inside the window is the same `_calendar_event_date`
expression. Postgres can't match a bound timezone parameter between the
select list and the window clause, so the window goes over a subquery
column, the same way `calendar_day_totals` already does.

### A3. Day page = the same ordered select with OFFSET/LIMIT + count

- `calendar_day_page(criteria, offset, limit)` reuses the `calendar_events`
  column select with the date bounds `date..date`, plus
  `OFFSET :offset LIMIT :limit`.
- The total comes from `calendar_day_totals(criteria)[date]`, which is
  already exact and indexed.
- That makes two statements in all.
- `pagination` is built with `core.responses.paginated_response`.
- The route `GET /invitations/calendar/day` is registered next to
  `/calendar` and before `/{invitation_id}`. It uses
  `response_model=PaginatedEnvelope[CalendarEventOut]`.
- The applied scope is returned in a `X-Calendar-Scope` response header,
  because the standard paginated envelope has no slot for it. *Alternative:*
  a custom envelope. Rejected so the endpoint matches every other list.

### A4. Ordering is total

The id tie-break already exists in `calendar_events`. The spec now states
it explicitly, and the window function and the day page use exactly the
same `ORDER BY`, which A2/A3 share through one helper
(`_calendar_order(event_date_expr)`).

## Risks / Trade-offs

- **Rows shift between page loads.** A new visit inserted earlier in the
  order between two page loads shifts later rows by one, so the web could
  see one duplicate or miss one row until the next refresh. → The web
  de-duplicates by id, and the column refreshes reconcile it (web design
  W3). This is acceptable for a human-scrolled list.
- **Window cost on wide ranges.** It's bounded by the 42-day range and the
  indexed date filter. Benchmark with the 181-visit QA day in the tests'
  statement-count check.

## Migration Plan

Additive. Deploy the API before the web change. Rollback: the web falls back
to not sending `perDayLimit`, and the day endpoint just goes unused.
