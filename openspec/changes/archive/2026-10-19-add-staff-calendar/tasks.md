Web-side tasks live in VMMS_WEB `openspec/changes/add-staff-calendar/tasks.md`.
Finish and deploy this API change first; the web change depends on it.

## 1. Shared helpers (pure extraction, no behaviour change)

- [x] 1.1 Extract the body of `org_structure/deps.py::require_branch_scope`
  into an `async def resolve_branch_scope(tenant_db, user, permission_code,
  x_branch_id) -> BranchScope` helper. Make the dependency call it. Run the
  existing invitation-list branch-scope tests unchanged (design.md D2).
- [x] 1.2 ~~Move `_resolve_tenant_timezone` to `core/timezone.py`~~.
  *Deviation:* the calendar reuses `invitations/service.py::_resolve_visit_timezone`
  (company timezone → tenant → UTC) instead, the zone expiry and the
  check-in gate already use. Nothing is moved and the dashboard is
  unchanged (design.md D3).

## 2. Schemas

- [x] 2.1 Add the following to `invitations/schemas.py` (all `CamelModel`):
  - `CalendarScope` (`auto`/`mine`/`branch`);
  - `CalendarQuery` (`from_`/`to` dates with alias `from`, `scope`, and
    `status: list[InvitationStatus] | None`). Add a validator that rejects
    `to < from` and spans over 42 days with 422;
  - `CalendarDayOut`;
  - `CalendarEventOut`, with exactly the spec's display fields and no
    phone, email, ID or photo fields;
  - `CalendarFeedOut`.
- [x] 2.2 Extend `tests/test_api_documentation.py::test_response_schemas_render_camel_case`
  (or a feature test) to cover `CalendarFeedOut` and `CalendarEventOut`.

## 3. Repository

- [x] 3.1 `InvitationRepository.calendar_filters(scope_clause, from_, to,
  from_start_utc, to_end_utc, statuses)` builds the list of filters:
  - the soft-delete filter;
  - the scope clause;
  - the status set (default: every status except `denied`);
  - the two-arm event-date OR (design.md D3).
- [x] 3.2 `calendar_day_totals(filters, tz)` is one `GROUP BY` statement on
  the event date. The fallback arm's date is computed in SQL with
  `timezone(:tz, checked_in_at)::date`.
- [x] 3.3 `calendar_events(filters, limit=1001)` is one column-select
  statement:
  - outer joins host `User`, `Branch`, `Building` and `VisitorCategory`;
  - a correlated `invitation_visitors` count;
  - ordered by event date, `preferred_visit_time NULLS LAST`, then primary
    contact name.

  No ORM relationship access (design.md D4).

## 4. Service and router

- [x] 4.1 `service.get_calendar_feed(tenant_db, tenant, user, query,
  x_branch_id)`:
  - resolve the scope (`auto` → `branch` if `authorized_branch_ids`
    non-empty, else `mine`). `branch` uses `resolve_branch_scope`; `mine`
    uses `relevant_to_me_clause` + `get_default_host_role`;
  - compute the UTC bounds from the visit timezone (`_resolve_visit_timezone`);
  - zero-fill `days`, trim to 1,000 and set `truncated`;
  - set `generatedAt`;
  - log `calendar_feed_truncated` at INFO with `tenant_id`, range and
    count when truncated.
- [x] 4.2 `router.py`: add `GET /invitations/calendar` **above**
  `GET /invitations/{invitation_id}`, with
  `response_model=Envelope[CalendarFeedOut]`, `-> JSONResponse` and
  `success_response`. Read `X-Branch-ID` as an optional header. No
  `require_permission` dependency (`mine` is open to any authenticated
  user; `branch` is checked in the service).

## 5. Tests (`invitations/test_calendar.py` — factories, real Postgres; a separate module because `tests.py` is ~15k lines)

- [x] 5.1 Range: inclusive bounds, 43-day 422, reversed 422, missing
  params 422, soft-deleted excluded.
- [x] 5.2 Event date:
  - a late check-in stays on the scheduled date;
  - a rescheduled invitation appears once, on its new date;
  - a legacy null-date row falls back to its visit-timezone check-in date
    (Asia/Kolkata boundary case);
  - a walk-in appears.
- [x] 5.3 Scope:
  - a host sees only their own (`scope=mine`);
  - a host with `scope=branch` gets 403 (permission-denied case);
  - reception at branch A doesn't see branch B;
  - security sees non-involved branch-A invitations;
  - an admin's `X-Branch-ID` narrows the result;
  - an unauthorized `X-Branch-ID` gets 403;
  - reception with `scope=mine` gets the personal set.
- [x] 5.4 Parity: for a host, the calendar's ids equal
  `GET /invitations?relevantToMe=true` ids filtered to the range.
- [x] 5.5 Tenant isolation: a second tenant schema with a same-date
  invitation is never returned (`make_tenant_schema`/`open_tenant_session`).
- [x] 5.6 Status:
  - `denied` is hidden by default;
  - an explicit multi-status filter works;
  - `archived` is shown by default;
  - an unknown status gets 422.
- [x] 5.7 Totals and cap:
  - empty days are zero-filled;
  - with the cap lowered via monkeypatch, `truncated` is true and the
    `days` sum is exact.
- [x] 5.8 Shape:
  - no phone, email, ID or photo keys in an event;
  - `hostFullName` is resolved, or null when unassigned;
  - `visitorCount` includes co-visitors;
  - a query-count assertion shows the number of statements stays constant
    as events grow;
  - no token gets 401.

## 6. Docs and checks

- [x] 6.1 Add a "Calendar" section to `docs/features/invitations.md` with
  the endpoint, params, scope rules, event-date rule, the 42-day and
  1,000-event caps, and the pagination deviation (design.md D1).
- [x] 6.2 Run `ddev exec uv run ruff check`, `ruff format --check`, `mypy`
  (core touched) and `pytest invitations dashboard org_structure`. If the
  full suite fails, compare it against a baseline per the known
  pre-existing failures.

  *Result:*
  - `ruff check` and `ruff format --check` are clean.
  - `mypy` reports no new errors. 8 errors remain in `invitations/tests.py`
    and `tasks.py:538`, the same as with this change stashed.
  - `test_calendar.py`: 17/17 pass.
  - invitations + dashboard + org_structure + api-docs: 128 failed with this
    change vs 131 on a stashed baseline.
    - The 2 failing only with the change pass when rerun in isolation.
    - The churn is `InvitationFactory` leaving the new `checkin_code` column
      unpinned (random `""` collides on its unique index), which is
      independent of this change.
    - The rest are the known create-payload 422s.

