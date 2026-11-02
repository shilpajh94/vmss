## 1. Shared definitions (design D1–D3)

- [x] 1.1 Rename `invitations/service.py::_resolve_visit_timezone` to public `resolve_visit_timezone` and update its callers
- [x] 1.2 In `invitations/repository.py`, add public `VisitDayRange`, `visit_day(tz_name)` (for grouping), `visit_day_filter(range)` (two-arm filter), `not_expired_filter(now)` and `upcoming_filters(now)`; move the dashboard's `_upcoming_filters` there and its status tuple as `VISIT_DAY_STATUSES`
- [x] 1.3 In `dashboard/service.py`, replace `_resolve_tenant_timezone`/`_today_bounds_utc`/`_local_today` with versions built on `resolve_visit_timezone`, so every endpoint (overview, my-overview, analytics, my-analytics) uses the visit timezone and reports it as `timezone`

## 2. Dashboard figures

- [x] 2.1 `overview_counts`: compute `scheduledTodayCount` with `visit_day_filter` + `VISIT_DAY_STATUSES`; add `scheduledTodayCheckedInCount` (the same filter plus `checked_in_at IS NOT NULL`), `openPendingApprovalCount` and `oldestOpenPendingSubmittedAt` (`submitted` plus `not_expired_filter`); keep the deprecated `pendingApprovalCount`/`oldestPendingSubmittedAt`/`visitsTodayCount` unchanged
- [x] 2.2 `personal_overview_counts`: compute `visitsToday` the same way; add `openAwaitingApproval`; keep the deprecated `awaitingApproval`
- [x] 2.3 `daily_trend`, `status_breakdown`, `_label_counts`: date rows by `visit_day(tz)` (pass the timezone through from the service)
- [x] 2.4 `dashboard/schemas.py`: add the new fields; mark `pendingApprovalCount`, `oldestPendingSubmittedAt` and `awaitingApproval` with `Field(deprecated=...)`, as `visitsTodayCount` is

## 3. Invitation list drill-down filters

- [x] 3.1 `_list_filters`: accept `visit_days` (a `VisitDayRange`), `upcoming`, `exclude_expired`, `now`, `branch_id`, and apply them through the D2/D3 helpers
- [x] 3.2 `GET /invitations`: add the `visitDateFrom`, `visitDateTo`, `upcoming`, `excludeExpired` and `branchId` query params; reject a reversed date range with 422; resolve the visit timezone (the tenant is loaded from the token's `tenant_id` only when a visit-date filter is used, so the route doesn't add `get_tenant`); narrow branch mode via `authorize_branch_id` (404/403), and in `relevantToMe` mode only add the branch filter (D5)
- [x] 3.3 `GET /invitations/export`: add the same params, with `branchId` narrowing inside the `invitations:export` scope
- [x] 3.4 Thread the new arguments through `list_invitations_page`, `export_invitations` and `InvitationRepository.list_page`/export query

## 4. Docs

- [x] 4.1 `docs/features/dashboard.md`: the new fields, the deprecations with a removal date, the visit timezone and visit-day rules, the count-to-list mapping table, and the D8 reception note
- [x] 4.2 `docs/features/invitations.md`: the drill-down list/export params

## 5. Tests (targeted modules only: `dashboard/tests.py`, the invitations list/export tests)

- [x] 5.1 Parity test: one mixed fixture (all statuses, expired and live, today/past/future, two branches); assert each overview and my-overview count equals the matching `GET /invitations` total, and each `statusBreakdown` row equals its date-ranged list total
- [x] 5.2 Scenarios from the dashboard delta: checked-in-so-far ≤ expected, expired pending excluded (old fields unchanged), today's trend point agrees with the overview, undated visit dated by creation day
- [x] 5.3 Timezone: tenant `UTC` + company `Asia/Kolkata` at 02:00 IST → `today`, `timezone` and the hourly bucket are in IST
- [x] 5.4 List filters: each scenario in the invitations delta, including the reversed range (422), `branchId` outside scope (403, the permission-denied case), `branchId` under `relevantToMe` not widening, and export parity
- [x] 5.5 Tenant isolation: the drill-down filters on a second tenant's schema return none of the first tenant's rows
- [x] 5.6 Run `ruff check`, `ruff format --check`, and `mypy` on the touched modules; run only the dashboard and invitations test modules, not the full suite
- [x] 5.7 `EXPLAIN` the overview and list queries on local QA data; note in the PR whether the visit-day expression index is needed (D2)
