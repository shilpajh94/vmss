Web-side tasks live in VMMS_WEB `openspec/changes/live-dashboards-and-analytics/tasks.md`.
Finish and deploy this API change first; the web change depends on it.

## 1. Indexes

- [x] 1.1 Add an `alembic_tenant` migration (generated revision id) creating
  partial indexes `ix_invitations_branch_visit_date (branch_id,
  preferred_visit_date)` and `ix_invitations_branch_checked_in_at (branch_id,
  checked_in_at)`. Both are `WHERE deleted_at IS NULL`. Pass `schema=`
  explicitly to the index ops. The downgrade drops both. Mirror them in
  `invitations/models.py` `__table_args__` (design.md D4).
- [x] 1.2 Run `ddev exec uv run alembic -c alembic_tenant.ini heads` and
  confirm there is one head. Upgrade every local tenant
  (`tenant_default`). Drop `vmss_test` if the test schema is stale.

## 2. Overview and check-ins fields

- [x] 2.1 `dashboard/schemas.py`:
  - `DashboardOverviewOut` gains `scheduled_today_count`,
    `checked_in_today_count`, `oldest_pending_submitted_at`, `today` and
    `generated_at`;
  - `UpcomingVisitorOut` gains `host_full_name`, `preferred_visit_date` and
    `preferred_visit_time`;
  - `DashboardCheckInListItemOut` gains `host_full_name`;
  - `MyDashboardOverviewOut` gains `today` and `generated_at`.
- [x] 2.2 `repository.overview_counts`: add the scheduled-today,
  checked-in-today and oldest-pending figures. Make
  `upcoming_visitor_count` use `_upcoming_filters` (the spec scenario
  "Upcoming count agrees with the preview filter"). Collapse the counts into
  one `COUNT(*) FILTER (...)` statement, the same as
  `personal_overview_counts`.
- [x] 2.3 Resolve `host_full_name` in `upcoming_visitors_preview` and
  `paginated_checkins` with a single join (no per-row query,
  query-performance.md §2) (design.md D5).
- [x] 2.4 `service.get_overview` and `get_my_overview`: populate `today`
  (tenant-local) and `generated_at`. In `router.get_overview`, add a
  `Deprecation` response header for `visitsTodayCount` (design.md D2).
  *Deviation:* no `Deprecation` header. `core.responses.mark_deprecated`
  marks a whole route deprecated (RFC 8594), which would wrongly tell
  clients `/overview` itself is going away. Instead, the field carries
  `Field(deprecated=...)`, which renders as `deprecated: true` in OpenAPI,
  and the docs note covers the removal date.

## 3. Analytics endpoints

- [x] 3.1 Schemas:
  - `DashboardRange = Literal["7d", "30d"]`;
  - row models `DailyTrendPointOut`, `HourlyCheckInsOut`,
    `StatusCountOut` and `LabelCountOut`;
  - `DashboardAnalyticsOut` and `MyDashboardAnalyticsOut`.
- [x] 3.2 Repository: add the grouped queries from design.md D3. These are
  daily trend, hourly check-ins today, status breakdown, top purposes (with
  a `LEFT JOIN visit_purposes`) and top departments (with a
  `LEFT JOIN departments`). Each takes a scope filter that is either the
  branch filter or `relevant_to_me_clause`.
- [x] 3.3 Service: compute the range bounds in the tenant timezone. Zero-fill
  the days, the 24 hours and the six statuses. Compute the top 5 plus
  "Other" (ties alphabetical) and fill `range`, `timezone`, `today` and
  `generated_at`.
- [x] 3.4 Router: add `GET /admin/dashboard/analytics`, which uses
  `resolve_dashboard_branch_scope("invitations:view-all")`, and
  `GET /admin/dashboard/my-analytics`, which uses `get_current_user` only.
  Both take `range` with alias `range` and default `7d`. Both declare
  `response_model=Envelope[...]` and return `success_response`.

## 4. Tests (`dashboard/tests.py`, factories, real Postgres)

- [x] 4.1 Overview:
  - scheduled-today vs. deprecated created-today;
  - checked-in-today;
  - oldest pending;
  - upcoming count equals the preview after a check-in/check-out cycle;
  - the timezone boundary for `today`;
  - `hostFullName` and the schedule on the preview rows;
  - `hostFullName` on check-ins rows;
  - the `Deprecation` header is present.
- [x] 4.2 Analytics happy paths:
  - the 7d and 30d lengths are zero-filled and ordered;
  - the trend reports `checkedIn` and `noShow`;
  - the hourly buckets use the tenant timezone (Asia/Kolkata);
  - the status breakdown has all six rows;
  - the creation-date fallback is used when there is no visit date;
  - the top 5 plus "Other", label fallback, case-insensitive grouping;
  - `range=90d` returns 422.
- [x] 4.3 Permission-denied: a host gets 403 on `analytics`, and an
  unauthenticated request gets 401 on `my-analytics`. Branch scope: an
  out-of-scope `branchId` gets 403, and a no-`branchId` aggregate excludes
  unauthorized branches.
- [x] 4.4 Personal analytics: totals match the caller's `relevantToMe` set
  only, and `X-Branch-ID` does not widen it.
- [x] 4.5 Tenant isolation: analytics run on a second tenant schema
  (`make_tenant_schema`/`open_tenant_session`) see none of the first
  tenant's rows.
- [x] 4.6 Extend `tests/test_api_documentation.py::test_response_schemas_render_camel_case`
  (or the feature's tests) so it covers the new analytics schemas.

## 5. Docs and gate

- [x] 5.1 `docs/features/dashboard.md`: the new endpoints, the field
  definitions (scheduled, checked-in, no-show, labels), the
  `visitsTodayCount` deprecation with its removal date, and the
  "one arrival per invitation" limitation (design.md Risks).
- [x] 5.2 Run `ruff check`, `ruff format --check`, `mypy` on the touched
  modules and the dashboard tests, then the full `ddev exec uv run pytest`.
  Run pytest serially, never concurrently. Diff any unrelated failures
  against a baseline before calling them regressions.
  *Result (2026-10-16):* `ruff check`, `ruff format --check` and `mypy` are
  clean, and the dashboard and docs tests pass (76/76). The full suite has
  237 failures, none in dashboard code. Running those 237 tests on a clean
  `HEAD` (3c6e47f) worktree: 236 also fail there, and the last one
  (`test_lookup_by_email_id_proof_url_null_without_documents_view`) is
  flaky in both trees. So none are regressions from this change.
