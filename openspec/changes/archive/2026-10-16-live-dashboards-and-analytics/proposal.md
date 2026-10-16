## Why

The admin, reception and staff dashboards are the first screen every user
sees, but today they are four count tiles and two short lists. There are no
charts, one button does nothing, and some figures are misleading:

- "Today's Visitors" counts invitations **created** today, not visits
  **scheduled** for today.
- The upcoming list shows the invitation's expiry instead of the visit date.
- Host names are resolved on the client from the first 100 employees only.

The dashboards need live, accurate figures and a small set of charts that
answer the questions reception and admins actually ask: how busy is today,
when do visitors arrive, what is stuck waiting, and what is the trend.

This change has a companion change of the same name in VMMS_WEB. That
change holds the web specs and tasks. This one holds the API contract and
the shared design.

## Gap Analysis

| Today | This change |
|---|---|
| `visitsTodayCount` = invitations whose `created_at` falls today. The staff `my-overview` already uses the scheduled visit date, so the two dashboards disagree. | Add `scheduledTodayCount` (scheduled visit date is today, status `approved`/`checked_in`/`checked_out`) and `checkedInTodayCount`. `visitsTodayCount` stays unchanged and is marked deprecated. |
| `upcomingVisitorCount` counts every non-expired `approved` invitation. The preview list additionally excludes visitors who were already admitted, so the count and the list disagree. | The count uses the same filter as the preview. This is a bug fix to match the existing spec text ("not yet checked in"). |
| Upcoming and check-in rows carry `hostId` only. The web resolves names from `GET /auth/employees?pageSize=100`, so the 101st host shows "Unassigned". | Rows also carry `hostFullName`. Upcoming rows also carry the scheduled visit date and time. |
| No time-series or breakdown data exists anywhere in the API. | A new `GET /admin/dashboard/analytics` (branch-wide) and `GET /admin/dashboard/my-analytics` (personal). |
| No "as of" date. The web prints the browser's date, which can disagree with the tenant's timezone. | Overview responses carry `today` (in the tenant's timezone) and `generatedAt`. |

## What Changes

- **Branch-wide analytics endpoint.** `GET /api/v1/admin/dashboard/analytics?branchId=&range=7d|30d`
  is gated on `invitations:view-all`, with the same branch-scope resolution
  as `overview`. It returns:
  - `dailyTrend`: one row per local day in the range, with scheduled,
    checked-in and no-show counts. Days with no visits are returned as zeros.
  - `hourlyCheckInsToday`: 24 hourly buckets in the tenant's timezone.
  - `statusBreakdown`: counts by status for visits scheduled in the range.
  - `topPurposes` and `topDepartments`: the top 5 of each, plus an "Other"
    remainder.
  - `range`, `timezone`, `today` and `generatedAt`.
- **Personal analytics endpoint.** `GET /api/v1/admin/dashboard/my-analytics?range=7d|30d`
  is available to any authenticated user. It returns `dailyTrend` and
  `statusBreakdown` over the caller's `relevantToMe` set, the same predicate
  `my-overview` uses.
- **Additive overview fields.**
  - `overview` gains `scheduledTodayCount`, `checkedInTodayCount`,
    `oldestPendingSubmittedAt`, `today` and `generatedAt`.
  - Its upcoming rows gain `hostFullName`, `preferredVisitDate` and
    `preferredVisitTime`.
  - `my-overview` gains `today` and `generatedAt`.
  - `checkins` rows gain `hostFullName`.
- **Overview bug fix.** `upcomingVisitorCount` now applies the same
  "never admitted" filter as the preview list.
- **Deprecation.** `visitsTodayCount` keeps its current meaning and is
  documented as deprecated in favour of `scheduledTodayCount`. Its removal
  date is recorded in `docs/features/dashboard.md`. It is not removed in
  this change.
- **Indexes.** A tenant migration adds
  `(branch_id, preferred_visit_date)` and `(branch_id, checked_in_at)`
  indexes on `invitations`, so range aggregation stays an index scan as data
  grows.

None of this is **BREAKING**. Every response change adds fields. The
`upcomingVisitorCount` fix brings the count in line with what the spec
already promised.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `dashboard`:
  - The overview gains scheduled-today, checked-in-today and as-of fields,
    and its upcoming rows gain host names and schedules.
  - The upcoming count is aligned with the preview list.
  - Two analytics endpoints are added: branch-wide and personal.

## Impact

- **API code**: `dashboard/{router,service,repository,schemas,tests}.py`.
  The personal analytics query reuses
  `invitations/repository.py::relevant_to_me_clause`.
- **DB**: one `alembic_tenant` migration that adds two composite indexes.
  It must be applied to every tenant, and `alembic -c alembic_tenant.ini heads`
  must show one head.
- **RBAC**: none new. `analytics` uses `invitations:view-all`, like
  `overview`. `my-analytics` uses the authenticated-user gate, like
  `my-overview`.
- **Docs**: `docs/features/dashboard.md` (new endpoints, new fields,
  deprecation note).
- **Web (VMMS_WEB)**: see the companion change. It covers the charts, live
  refresh, working buttons, the reception dashboard and responsive layout.
- **Dependencies**: none on the API side. The web side adds `recharts`.
