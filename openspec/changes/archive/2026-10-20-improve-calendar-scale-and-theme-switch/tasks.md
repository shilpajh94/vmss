Web-side tasks live in VMMS_WEB `openspec/changes/improve-calendar-scale-and-theme-switch/tasks.md`.
Finish and deploy this API change first.

## 1. Shared criteria and ordering

- [x] 1.1 Extract `_calendar_criteria(...)` from `service.get_calendar_feed`.
  It covers scope resolution, `resolve_branch_scope` /
  `relevant_to_me_clause`, the visit timezone, UTC bounds and default
  statuses (design.md A1). The feed calls it with no behaviour change.
- [x] 1.2 `repository.py`: add `_calendar_order(event_date_expr)`, returning
  the shared `ORDER BY` (date, time NULLS LAST, name, id). Use it in
  `calendar_events` (A4).

## 2. perDayLimit

- [x] 2.1 Router: add `per_day_limit: Annotated[int | None, Query(alias="perDayLimit", ge=1, le=100)] = None`
  to `GET /invitations/calendar`, passed through the service to the
  repository.
- [x] 2.2 `calendar_events(criteria, *, limit, per_day_limit=None)`: when
  `per_day_limit` is set, use the window-function subquery that keeps
  `rn <= per_day_limit` (A2). Leave the query unchanged when it's None.

## 3. Day page endpoint

- [x] 3.1 `repository.calendar_day_page(criteria, *, offset, limit)` is the
  same column select and order, with OFFSET/LIMIT (A3).
- [x] 3.2 `service.get_calendar_day_page(...)` takes `date`, `scope`,
  `statuses`, `x_branch_id` and `page`/`page_size`, and returns the events,
  the total and the applied scope. The total comes from
  `calendar_day_totals(criteria)`.
- [x] 3.3 `router.py`: add `GET /invitations/calendar/day`, registered
  before `/{invitation_id}`:
  - `response_model=PaginatedEnvelope[CalendarEventOut]`;
  - `get_pagination`;
  - `paginated_response`;
  - an `X-Calendar-Scope` header;
  - 422 on a bad `date`.

## 4. Tests (`invitations/test_calendar.py`)

- [x] 4.1 `perDayLimit`:
  - a busy day is limited and the other days are complete;
  - totals are exact;
  - 0 and 101 get 422;
  - omitting it gives the same events as before.
- [x] 4.2 Day page:
  - page 1 with size 10 equals the feed's first 10 for the day with
    `perDayLimit=10`;
  - pages 1–N concatenated equal the full day order, with no duplicates
    or gaps (25 visits, `pageSize=10`);
  - `pagination.total` equals the feed's day total;
  - a page past the end is empty.
- [x] 4.3 Scope on the day page:
  - a host sees only their own visits (`X-Calendar-Scope: mine`);
  - `scope=branch` as a host gets 403;
  - an unauthorized `X-Branch-ID` gets 403;
  - tenant isolation is checked at the repository level.
- [x] 4.4 Ties: two visits with the same time and name always come back in
  id order across both endpoints.
- [x] 4.5 The statement count for the feed with `perDayLimit` and for the
  day page stays constant as visits grow.

## 5. Docs and checks

- [x] 5.1 `docs/features/invitations.md`: document `perDayLimit`, the day
  endpoint, the `X-Calendar-Scope` header and the paging contract.
- [x] 5.2 Run `ruff check`, `ruff format --check`, `mypy` (no new errors) and
  `pytest src/vmss_api/invitations/test_calendar.py`. Compare the affected
  suites against a stashed baseline, remembering the `InvitationFactory`
  `checkin_code` flake.

  *Result:*
  - ruff and format are clean.
  - mypy reports 8 errors, all pre-existing (`invitations/tests.py`,
    `tasks.py:538`).
  - `test_calendar.py`: 25/25.
  - invitations + dashboard + org_structure + api-docs: 128 failed, 672
    passed. That is the same failure count as the previous calendar run,
    with 8 new passing tests. The one test that differs
    (`test_export_archived_date_range_applies_to_archived_at`, export code
    this change doesn't touch) passes 3/3 in isolation, which is the known
    flake.

## Implementation notes

- **A4.** The shared ordering is `InvitationRepository._within_day_order(rows)`
  over a column-only subquery (`_calendar_rows`), rather than a
  `_calendar_order(event_date_expr)` helper. Every ordering, window and
  offset runs over the subquery's columns. That keeps `event_date`'s bound
  timezone in one place (the Postgres repeated-bind-parameter issue).
- **A3.** `X-Calendar-Scope` is also added to the CORS `expose_headers`, so
  a cross-origin portal can read it. The web itself takes the scope from
  the feed.

