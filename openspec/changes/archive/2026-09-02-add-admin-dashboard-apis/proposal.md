## Why

The React admin portal's dashboard page is currently unbacked — its overview
cards, "upcoming visitors" check-in action, paginated check-ins log, and
topbar search have no server endpoints to call. The frontend has shared the
exact four routes/action-names it needs wired up next.

## What Changes

- Add `GET /admin/dashboard/overview` — branch-scoped (or, when no branch is
  selected, aggregated across every branch the caller is authorized for)
  summary counts (visits today, currently checked-in, pending approvals,
  upcoming-visitor count) plus a short preview list of upcoming (approved,
  not yet checked-in) visitors. Accepts an optional `branchId` query
  parameter, per the frontend's explicit ask — a deliberate, dashboard-only
  deviation from the existing `X-Branch-ID`-header convention used by list
  endpoints elsewhere (`invitations` `GET /invitations`), since this surface
  has its own branch-selector UI rather than a global per-request header.
- Add `PATCH /admin/dashboard/upcoming-visitors` — checks in one invitation
  named by `invitationId` in the request body. Same business rule, permission
  (`invitations:checkin`), audit action, and `Idempotency-Key` behavior as the
  existing `PATCH /invitations/{id}/check-in`; this route only exists because
  the dashboard's "upcoming visitors" widget triggers the action by row, not
  by navigating to a per-invitation path — it calls the same service function,
  not a re-implementation.
- Add `GET /admin/dashboard/checkins` — paginated "View All" list of every
  invitation that has been checked in (status `checked_in` or `checked_out`),
  reusing the existing `page`/`pageSize`/`sortBy`/`sortOrder` list-endpoint
  convention, filterable by the same optional `branchId` query parameter as
  the overview endpoint.
- Add `GET /admin/dashboard/search` — topbar search over visitor/contact name
  (`primaryContactFullName`), same optional `branchId` scoping, capped result
  count (mirrors the not-yet-built `GET /hosts/search`'s
  "don't search below 2 characters" / capped-limit shape already agreed for
  this kind of lookup in `visit-info-lookup-api-spec.md`).
- All four endpoints are read/act on the existing `Invitation` lifecycle
  (`invitations` capability) — no new table, no new permission codes.
  `invitations:view` covers the three read endpoints; `invitations:checkin`
  covers the check-in action, consistent with
  `security-architecture.md` §1's "no scattered role checks, only
  `require_permission`/branch-scope dependencies."

## Capabilities

### New Capabilities
- `dashboard`: admin-portal dashboard read endpoints (overview summary +
  upcoming-visitors preview, paginated check-ins log, topbar search) and the
  upcoming-visitors check-in action, all composed read-only (plus one
  action) over the existing `invitations` capability's data.

### Modified Capabilities
(none — no existing capability's requirements change; `dashboard` only reads
`Invitation` rows and calls the existing check-in business rule, it doesn't
alter what `invitations` itself guarantees)

## Impact

- **New code**: `src/vmss_api/dashboard/` (`router.py`, `service.py`,
  `schemas.py`, `repository.py`, `deps.py`, `tests.py`) — no `models.py`,
  since it owns no table.
- **Registration**: `dashboard.router.router` added to `api.py`;
  `"dashboard"` tag + description added to `main.py`'s `_TAGS_METADATA`
  (`api-documentation.md` §2).
- **Reused, unchanged**: `invitations.models.Invitation`,
  `invitations.service.check_in_invitation`, `org_structure.deps` branch
  authorization helpers (`authorize_branch_id`,
  `user.authorized_branch_ids`), `tenant.models.Tenant.timezone` (for
  "today" day-boundary calculation), existing `invitations:view` /
  `invitations:checkin` permission codes.
- **No breaking change** to any existing endpoint or contract.
