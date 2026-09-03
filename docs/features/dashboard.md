# Dashboard

Backs the admin portal's dashboard page: overview summary counts and an
upcoming-visitors preview, the check-in action triggered from that preview, a
paginated check-ins log, and topbar visitor search. Owns no table — it reads
(and, for the check-in action, writes) `invitations`' `Invitation` rows the
same way `reports/repository.py::BranchRollupRepository` reads across
`org_structure`/`auth` without owning a table
(`fastapi-architecture.md`'s layering still applies:
`router.py` → `service.py` → `repository.py`, only `repository.py` touches
`AsyncSession`).

## Endpoints

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/v1/admin/dashboard/overview` | `invitations:view` | Visits-today/checked-in/pending-approval/upcoming-visitor counts plus a bounded (10) upcoming-visitors preview. |
| PATCH | `/api/v1/admin/dashboard/upcoming-visitors` | `invitations:checkin` | Checks in one invitation (`invitationId` in the body) — the dashboard's row-level counterpart to `PATCH /invitations/{id}/check-in`. |
| GET | `/api/v1/admin/dashboard/checkins` | `invitations:view` | Paginated "View All" list of every invitation that has been checked in at least once (`checked_in` or `checked_out`). |
| GET | `/api/v1/admin/dashboard/search` | `invitations:view` | Topbar search — case-insensitive partial match on the primary contact's full name, capped at 10 results. |

## `branchId` query param, not `X-Branch-ID` header

Every endpoint above accepts an optional `branchId` query parameter instead of
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

No new permission codes exist for this feature. `invitations:view` covers the
three read endpoints; `invitations:checkin` covers the check-in action — both
already exist in `auth/rbac_catalog.py` and are already granted to whichever
roles can see/act on invitations elsewhere.

## Check-in action delegates to `invitations`

`PATCH /admin/dashboard/upcoming-visitors` doesn't reimplement the check-in
business rule: it resolves the invitation, authorizes via
`authorize_branch_id_tolerant`, then calls
`invitations.service.check_in_invitation` directly — the same 404/409s (not
approved, watchlist-flagged) and audit trail entry (`invitation_checked_in`)
as `PATCH /invitations/{id}/check-in`. It has its own small
`Idempotency-Key` cache/response pair (same Redis convention,
`vmss:{tenant_id}:dashboard:idempotency:{key}` — `database-architecture.md`
§6), rather than sharing `invitations/router.py`'s private helpers.

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
