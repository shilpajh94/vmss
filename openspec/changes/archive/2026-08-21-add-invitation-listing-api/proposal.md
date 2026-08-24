## Why

Staff can create an invitation (`POST /invitations`) and the public can look
up one invitation at a time by tracking ID or email (`GET /invitations/track`),
but no endpoint lets an authenticated employee browse the invitations at
their branch — e.g. to see today's expected visitors or find one without
already knowing its tracking ID. `invitations:view` already exists as a
permission (granted to Admin/Employee/Security roles in the RBAC catalog)
and is currently unused, which is a strong signal a list endpoint was always
the intended follow-up.

## What Changes

- Add `GET /invitations` — an authenticated, paginated listing of
  invitations, gated by the existing `invitations:view` permission.
- Branch scoping follows the same pattern as `GET /branches`'s siblings
  (`org_structure`'s `list_buildings`/`list_floors`): an optional
  `X-Branch-ID` header narrows to one branch (still checked against the
  caller's access to it); omitting it lists across every branch the caller
  holds `invitations:view` at.
- Filtering: `status`, `registrationType`, and `source` as explicit typed
  query params (api-conventions.md §1) — no generic `?filter=` string.
- Sorting: `sortBy` (`submittedAt` default, or `createdAt`) + `sortOrder`
  (`asc`/`desc`), validated against a whitelist, matching `SortableField`'s
  role in `org_structure`.
- Pagination: shared `page`/`pageSize` params via `get_pagination`, same
  `PaginatedEnvelope` response shape every other list endpoint uses.
- Response rows use a new summary schema (id, trackingId, registrationType,
  source, status, primaryContact name, purpose of visit, expiry/submission
  timestamps) — not the existing `InvitationTrackingOut`, which is sized for
  a single full-detail lookup and always includes visitors/vehicles; a list
  response returning that per row would N+1 fan out unnecessarily for a
  view that only needs to show a table of rows.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `invitations`: adds a new requirement — an authenticated, branch-scoped,
  paginated listing endpoint for invitations, with filtering and sorting.

## Impact

- `src/vmss_api/invitations/router.py` — new `GET /invitations` route.
- `src/vmss_api/invitations/service.py` — new `list_invitations_page`.
- `src/vmss_api/invitations/repository.py` — new `list_page` method
  (query-performance.md §1/§2: single paginated query, no N+1).
- `src/vmss_api/invitations/schemas.py` — new `InvitationListItemOut`
  (and a `SortableField`-style enum for `sortBy`).
- No new tables/migrations — reads existing `invitations` columns only.
- No breaking changes; purely additive.
