# Dashboard

Backs the admin portal's dashboard page: overview summary counts and an
upcoming-visitors preview, a paginated check-ins log, and topbar visitor
search. Owns no table — it reads `invitations`' `Invitation` rows the
same way `reports/repository.py::BranchRollupRepository` reads across
`org_structure`/`auth` without owning a table
(`fastapi-architecture.md`'s layering still applies:
`router.py` → `service.py` → `repository.py`, only `repository.py` touches
`AsyncSession`).

## Endpoints

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/v1/admin/dashboard/overview` | `invitations:view-all` | Visits-today/checked-in/pending-approval/upcoming-visitor counts plus a bounded (10) upcoming-visitors preview. Each preview row includes `trackingId`, so the "check in" action calls `PATCH /api/v2/invitations/{trackingId}/check-in` directly — see "Check-in is done through the canonical invitation endpoint" below. |
| GET | `/api/v1/admin/dashboard/checkins` | `invitations:view-all` | Paginated "View All" list of every invitation that has been checked in at least once (`checked_in` or `checked_out`). |
| GET | `/api/v1/admin/dashboard/search` | `invitations:view-all` | Topbar search — case-insensitive partial match on the primary contact's full name, capped at 10 results. |
| GET | `/api/v1/admin/dashboard/my-overview` | Any authenticated user | The staff landing page. Returns `visitsToday`, `insideNow`, `awaitingApproval` and `upcoming`, plus a 5-row `upcomingPreview`, all counted over the caller's own `relevantToMe` invitations. See "Personal overview" below. |

**Removed** (`checkin-approval-workflow-improvements`): `PATCH
/api/v1/admin/dashboard/upcoming-visitors` — this duplicated
`PATCH /invitations/{id}/check-in`'s business rule through a second,
body-keyed contract. The dashboard's "check in" action now calls the
canonical `PATCH /api/v2/invitations/{trackingId}/check-in` endpoint
directly, using the `trackingId` already present on each upcoming-visitors
preview row.

## Personal overview (`my-overview`)

`staff-lifecycle-emails-and-dashboard-landing`. Hosts can't read the
branch-wide endpoints, so the staff portal's landing page uses this
instead.

- **Scope**: exactly the set `GET /invitations?relevantToMe=true` returns
  for the same caller. The repository applies the same predicate
  (`invitations.repository.relevant_to_me_clause`), so the dashboard and
  the board can't disagree. A holder of the tenant's default host role
  therefore sees branch-wide numbers here, just as on their board.
- **No branch gate**: like the `relevantToMe` list, the predicate is the
  whole authorization. There is no `branchId` param, and `X-Branch-ID` is
  ignored.
- **Figures**:
  - `visitsToday` counts invitations scheduled today (tenant timezone) in
    `approved`, `checked_in` or `checked_out`.
  - `insideNow` counts `checked_in` invitations.
  - `awaitingApproval` counts `submitted` invitations.
  - `upcoming` counts invitations that are `approved`, never checked in,
    and not yet expired.
  - The preview lists upcoming invitations by scheduled date and time.

  `archived` and `denied` invitations count toward nothing.
- **Prefix**: the route lives under `/admin/dashboard` for historical
  reasons only. That router already serves reception and security, and
  one feature exposes one `router`.

## `branchId` query param, not `X-Branch-ID` header

Every branch-wide endpoint above accepts an optional `branchId` query parameter instead of
the `X-Branch-ID` header `GET /invitations` and other list endpoints use.
This is a deliberate, dashboard-only deviation: the dashboard page has its own
branch-selector control, not a global per-request header, and the frontend
asked for a param specifically. `dashboard/deps.py::resolve_dashboard_branch_scope`
mirrors `org_structure.deps.require_branch_scope`'s narrow-to-one-branch-or-
fall-back-to-every-authorized-branch semantics, reading from `Query()` instead
of `Header()`. Don't copy this pattern to a non-dashboard endpoint without a
new design decision — see `openspec/changes/add-admin-dashboard-apis/design.md`
Decision 2.

## Reused permission codes

No new permission codes exist for this feature. `invitations:view-all` covers
the three read endpoints (restrict-delegated-invitation-visibility — was
`invitations:view`): they aggregate or search every invitation at a branch,
which only a branch-wide viewer (Admin, Reception, Security) may see. A
`host`, holding only `invitations:view`, gets 403. See
`docs/features/invitations.md`'s "Who can see an invitation".

## Check-in is done through the canonical invitation endpoint

The dashboard no longer exposes its own check-in mutation. The admin portal's
"check in" action on an upcoming-visitors preview row calls
`PATCH /api/v2/invitations/{trackingId}/check-in` directly, using that row's
`trackingId` (see `docs/features/invitations.md`) — the same endpoint every
other staff/desk check-in flow uses. `Idempotency-Key` and the resulting
audit-trail entry behave exactly as they do for that endpoint.

## "Today" follows the tenant's configured timezone

The overview's "visits created today" count converts `Invitation.created_at`
(stored UTC) into the resolved tenant's `Tenant.timezone` to determine the day
boundary (`dashboard/service.py::_today_bounds_utc`, stdlib `zoneinfo`), then
queries with a plain UTC range — one indexed `created_at` range scan, not a
per-row Python filter. `Tenant.timezone` has no DB-level validation, so an
unresolvable value falls back to UTC with a `WARNING` log rather than a 500.

## Non-goals

- No `GET` endpoint to list/paginate upcoming visitors beyond the overview's
  bounded (10) preview — only `GET /admin/dashboard/checkins` was asked for
  as paginated ("View All").
- Search matches the primary contact's full name only — no tracking ID,
  badge number, host, or email matching yet.
