## Context

See proposal.md for the problems. The relevant state of the code:

- **Dashboard queries.** `dashboard/repository.py` builds every figure with
  its own `COUNT(*) FILTER (...)` expressions. `invitations/repository.py`'s
  `_list_filters` builds the board's list. The only thing they share today
  is `relevant_to_me_clause` (and `_upcoming_filters`, which is private to
  the dashboard).
- **Timezones.** `dashboard/service.py::_resolve_tenant_timezone` reads
  `Tenant.timezone` only. `invitations/service.py::_visit_timezone`
  resolves company default → tenant → UTC, and that zone sets every
  invitation's `expires_at` (end of the visit day).
- **Expired requests.** The visit-lifecycle sweep archives
  approved-but-never-admitted invitations after expiry. It never touches
  `submitted` ones, and expired requests can still be approved.
- **Board scope.** The web board calls `GET /invitations` once per status
  column, with `relevantToMe=true` on the staff board. Each column shows
  the API's `total`.

## Goals / Non-Goals

**Goals:**
- Every count a dashboard shows and links from equals the `total` of the
  list it opens, for every role and branch selection.
- Figures on one page agree with each other: "checked in so far" ≤
  "expected today", and today's trend point matches the KPIs.
- One timezone, one visit-day rule, one filter per figure, each shared by
  the count and the list.

**Non-Goals:**
- Closing or archiving expired `submitted` requests. They stay on the
  board's full Requested list; the user chose to exclude them from the
  count only.
- Check-in history. With repeated check-ins, `checked_in_at` holds only
  the latest one, so the hourly chart counts a visit once, at its latest
  arrival. A per-entry history table would be needed to change that.
- Counting people instead of invitations. A group invitation counts once,
  on the dashboard and on the board alike.
- Linking the trend chart or the top-labels chart to the board.

## Decisions

### D1. One visit timezone, resolved by one function
Make the invitations resolver public as
`invitations/service.py::resolve_visit_timezone(tenant_db, tenant)` and
delete `dashboard/service.py::_resolve_tenant_timezone`. The dashboard,
the list's visit-date filter and the expiry calculation then share one
resolution.
- *Alternative:* copy the company→tenant fallback into the dashboard.
  Rejected, because that duplication is how the two zones drifted apart in
  the first place.
- `resolve_visit_timezone` needs `tenant_db` (for the company row). Every
  dashboard service function already has it.

### D2. The visit day is one SQL expression
`invitations/repository.py::visit_day(tz_name)` returns
`coalesce(preferred_visit_date, cast(timezone(tz_name, created_at) as date))`.
These all use it:
- the overview's scheduled-today counts;
- the personal overview's `visitsToday`;
- `daily_trend`, `status_breakdown` and `_label_counts`;
- the list's `visitDateFrom`/`visitDateTo`.

- *Alternative:* keep `preferred_visit_date` alone and drop the fallback
  from the status breakdown. Rejected: it changes an existing chart's
  meaning, and the fallback is the rule the spec already states.
- *Implementation note:* there are two forms of the same rule. Filtering
  (counts and the list) uses the calendar's two-arm pattern: the visit
  date in range, OR no visit date and `created_at` inside the range's UTC
  bounds. That keeps the visit-date arm on
  `ix_invitations_branch_visit_date`. Grouping (the trend, status and
  label charts) uses the `coalesce` expression over a subquery, because
  Postgres won't match a SELECT-list timezone parameter to a GROUP BY one
  (see `calendar_day_totals`). The calendar's own fallback uses the
  check-in date, not the creation date. It is out of scope here and only
  differs for undated rows.
- *Cost:* `coalesce(...)` can't use a plain index on
  `preferred_visit_date`. The dashboard queries are already per-scope
  aggregates over the same rows, so this is no worse than today. If it
  shows up in `EXPLAIN` at volume, add an expression index in a tenant
  migration. Not needed now.

### D3. Each figure's filter is a public function, used by both sides
Move `_upcoming_filters` out of the dashboard into
`invitations/repository.py`, next to two new helpers, all public:
- `upcoming_filters(now)`;
- `not_expired_filter(now)`, which is `expires_at > now`;
- `visit_day_filter(range)` with `VISIT_DAY_STATUSES`
  (`approved`/`checked_in`/`checked_out`) for "scheduled today".

The dashboard's `COUNT(*) FILTER (...)` and `_list_filters` both call these
helpers. A parity test (tasks §5) asserts that every count equals its list
total over one mixed fixture. If a future edit changes one side only, that
test fails.

### D4. New fields, not new meanings (api-conventions.md §2)
Changing what `pendingApprovalCount` or `awaitingApproval` count would be
a breaking change for any client on `v1`. So the new definitions go into
new fields:
- `openPendingApprovalCount` and `oldestOpenPendingSubmittedAt`;
- `scheduledTodayCheckedInCount`;
- `openAwaitingApproval`.

The old fields stay, marked `deprecated` in the schema, with a removal
date in `docs/features/dashboard.md`. This follows the `visitsTodayCount`
precedent. `checkedInTodayCount` keeps its meaning, which is still correct
(it equals the sum of the hourly chart). Only the web label that paired
it with "Expected today" was wrong.

### D5. `branchId` as a list query param, narrowing only
`GET /invitations` already reads `X-Branch-ID`, but only in branch mode,
and ignores it under `relevantToMe`. Making the header narrow
`relevantToMe` lists would change behaviour for current callers that send
it. A new `branchId` query param matches what the dashboard already uses,
and the board can copy it straight from the dashboard link:
- **Branch mode:** resolve the scope as today, then narrow it to
  `{branchId}` via `org_structure.deps.authorize_branch_id` (404 for an
  unknown branch, 403 outside the scope), the same check as
  `resolve_dashboard_branch_scope`.
- **`relevantToMe` mode:** add `Invitation.branch_id == branchId` to the
  filters. No authorization is needed, because it can only shrink a set
  the caller may already see.
- **Export:** the same narrowing, inside the `invitations:export` scope.

### D6. `now` is taken per request
`upcoming=true` and `excludeExpired=true` compare against the request
time. A dashboard poll and a board load a few seconds apart can differ by
an invitation that expires in between. That is accepted. The next poll
agrees again, and freezing a shared "as of" time across requests is not
worth the complexity.

### D7. Web drill-down links mirror the API params (VMMS_WEB change)
A dashboard link carries the API's own parameters in the board URL:
- `status` (repeatable);
- `visitDateFrom` and `visitDateTo`;
- `upcoming`;
- `excludeExpired`;
- `branchId`.

The board passes them to every column query, and to export, unchanged.

| Dashboard element | Board URL query |
|---|---|
| Expected / Visits today | `status=approved&status=checked_in&status=checked_out&visitDateFrom=<today>&visitDateTo=<today>` |
| On-site / Inside now | `status=checked_in` |
| Pending / Awaiting approval | `status=submitted&excludeExpired=true` |
| Upcoming tile and Upcoming card "View all" | `upcoming=true` |
| Recent check-ins "View all" | `status=checked_in&status=checked_out` |
| Status bar `<s>` | `status=<s>&visitDateFrom=<range start>&visitDateTo=<today>` |

Every branch-dashboard link adds `branchId` when a branch is selected.
`<today>` and the range start come from the API's `today` and
`dailyTrend`, never the browser clock.
- On the board, the non-status params show as one removable "From
  dashboard" chip row, for example "Visit date: 26 Oct · Branch: HQ ·
  Not expired". Without it, a board showing fewer cards than usual looks
  like another bug. "Clear filters" removes the chips too.
- *Alternative:* a dedicated drill-down list page per tile. Rejected,
  because the board is where staff act on these invitations.

### D8. Reception keeps its "relevant to me" board
The reception dashboard counts the branch scope, and its board is
`relevantToMe`. Reception holds the tenant's default host role, and
relevant-to-me clause (e) gives that role every invitation at its
branches. So the two sets match wherever reception holds both the role and
`invitations:view-all`. With `branchId` carried through (D5), a selected
branch matches as well. If an installation grants view-all without the
default host role, the totals would differ. That configuration is outside
this change and is noted in `docs/features/dashboard.md`.

## Risks / Trade-offs

- [Deprecated fields linger and get used by mistake] → They are marked
  `deprecated` in the OpenAPI schema, and the web change stops reading
  them. The removal date goes in `docs/features/dashboard.md`.
- [Count and list taken seconds apart differ at an expiry boundary] →
  Accepted (D6). The next poll self-corrects.
- [`coalesce` visit day slows large scopes] → Check with `EXPLAIN` on the
  local QA data during implementation, and add an expression index only if
  needed (D2).
- [The web ships before the API] → The new query params would be ignored
  and the new fields would be missing. The web change is gated to ship
  after this one, and its schemas would fail loudly on missing fields
  instead of showing wrong numbers.

## Migration Plan

1. Ship the API change. It is purely additive: no migration, no data
   change.
2. Ship the VMMS_WEB `fix-dashboard-count-accuracy` change.
3. Rollback: revert the web change first. The API additions are inert
   without it.
