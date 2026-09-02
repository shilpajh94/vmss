## Context

See proposal.md for motivation. Relevant existing pieces this design builds
on, all in `src/vmss_api/invitations/`:
- `models.py::Invitation` — single table carrying the whole visit lifecycle
  (`status` in `submitted`/`approved`/`denied`/`checked_in`/`checked_out`),
  `branch_id`, `checked_in_at`/`checked_out_at`, `expires_at`,
  `watchlist_flagged`, `primary_contact_full_name`.
- `service.py::check_in_invitation` — the existing check-in business rule
  (status transition, watchlist gate), already used by both
  `PATCH /invitations/{id}/check-in` (deprecated, still functional) and the
  public `PATCH /api/v2/invitations/{trackingId}/check-in`.
- `org_structure/deps.py` — `authorize_branch_id` (branch + permission check
  from a known id), `require_branch_scope` (header-based, "narrow to one
  branch or fall back to every authorized branch" pattern used by
  `GET /invitations`), and `User.authorized_branch_ids`.
- `tenant/models.py::Tenant.timezone` — already exists, unused for any
  day-boundary logic yet.

## Goals / Non-Goals

**Goals:**
- Ship exactly the four routes the frontend asked for, matching their
  method/path/action names.
- Reuse existing business logic (check-in rule, permission codes, branch
  authorization) rather than duplicating it under `dashboard/`.

**Non-Goals:**
- A `GET` endpoint to list/paginate upcoming visitors beyond the overview's
  bounded preview — not requested; if the frontend needs a "view all
  upcoming" page later, that's a follow-up change.
- Any new permission code, table, or migration.
- Full-text/fuzzy search — `ILIKE` partial match on one field is sufficient
  for what was asked.

## Decisions

### Decision 1: New `dashboard` feature package, no owned table
`src/vmss_api/dashboard/{router,service,repository,schemas,deps}.py` +
`tests.py`. `repository.py` queries `invitations.models.Invitation` directly
(imported cross-feature) — the same posture as `reports/repository.py`'s
`BranchRollupRepository`, which already reads `org_structure`/`auth` models
without owning a table. Router calls service, service calls repository +
(for the check-in action) `invitations.service.check_in_invitation` directly
— no new copy of the check-in rule.

**Alternative considered**: put these routes in `invitations/router.py`
under an `/admin/dashboard` sub-path. Rejected — `invitations` already
carries the full pre-registration/approval/check-in/badge lifecycle
(`router.py` is 1000+ lines); a dashboard-shaped read/aggregate surface is a
distinct concern (`fastapi-architecture.md` §1's one-subpackage-per-feature
intent), and keeping it separate means the two can evolve (e.g. a future
per-widget endpoint) without growing an already-large file.

### Decision 2: `branchId` query param, not `X-Branch-ID` header — dashboard endpoints only
All four endpoints accept an optional `branchId: uuid.UUID` query parameter.
`dashboard/deps.py` adds one dependency,
`resolve_dashboard_branch_scope(permission_code)`, mirroring
`org_structure.deps.require_branch_scope`'s logic (narrow to one branch via
`authorize_branch_id` when supplied, else fall back to
`user.authorized_branch_ids(permission_code)`, 403 if that's empty) but
reading the id from `Query(alias="branchId")` instead of a header. This
duplicates a small amount of branch-scope-resolution logic rather than
parameterizing `require_branch_scope` itself, to avoid changing the header
convention every other list endpoint (`GET /invitations`) already relies on.

**Why the frontend gets a param here specifically**: the dashboard page has
its own branch-selector control in the UI, distinct from any global
per-request branch header the rest of the portal might use — this was the
frontend's explicit ask ("needs branchId param added") on the overview
endpoint, and it's applied consistently to all four dashboard endpoints
rather than only the one it was mentioned on, so the same page's branch
selector works uniformly across its widgets.

**Alternative considered**: reuse `require_branch_scope` as-is (header-only)
and have the frontend send `X-Branch-ID`. Rejected per the explicit
`branchId` param ask.

### Decision 3: Reuse `invitations:view` / `invitations:checkin`, no new permission codes
The three read endpoints (overview, checkins, search) require
`invitations:view`; the check-in action requires `invitations:checkin` —
both already exist in `auth/rbac_catalog.py` and are already granted to the
same roles that can see/act on invitations elsewhere. Real RBAC from day one
(`security-architecture.md` §1) doesn't mean a new code per new route; it
means every route goes through `require_permission`/branch-scope, which
these do.

### Decision 4: Check-in action delegates to `invitations.service.check_in_invitation`
`PATCH /admin/dashboard/upcoming-visitors` resolves the invitation by the
`invitationId` in its body, authorizes via `authorize_branch_id_tolerant`
(tolerant because the invitation's branch could theoretically have been
soft-deleted after creation — same reasoning `invitations/router.py` already
applies), then calls the existing `service.check_in_invitation`. It
implements its own small `Idempotency-Key` cache/response pair (same Redis
key convention, `vmss:{tenant_id}:idempotency:{key}` —
`database-architecture.md` §6) rather than extracting
`invitations/router.py`'s private `_cached_response`/`_cache_response`
helpers into a shared module — that extraction isn't required by this
change and isn't done speculatively (`project-rules.md`: no premature
abstraction).

### Decision 5: "Today" uses `Tenant.timezone`, computed in the service layer
The overview's "visits created today" count converts `Invitation.created_at`
(UTC in the DB) into the resolved tenant's `timezone` to determine the day
boundary, using the existing `Tenant.timezone` column (already populated,
previously unused for this purpose). Computed with Python's `zoneinfo`
(stdlib, no new dependency) in `dashboard/service.py`, not pushed into SQL —
keeps the boundary logic testable and readable; the query itself still
takes plain UTC `created_at >= day_start_utc AND < day_end_utc` bounds
computed from that conversion, so it's still one indexed range query, not a
per-row Python filter (`query-performance.md`).

### Decision 6: Upcoming-visitors preview is bounded, not paginated
The overview's `upcomingVisitors` list is capped at a fixed size (10),
ordered by `expires_at` ascending. Only `GET /admin/dashboard/checkins` was
explicitly asked for as paginated ("View All"); the preview is a dashboard
widget, not a page of its own, and doesn't take `page`/`pageSize` params.

## Risks / Trade-offs

- **[Risk]** A `branchId`-as-query-param convention that's inconsistent with
  the rest of the API (`X-Branch-ID` header) could confuse future feature
  work if copied outside `dashboard/`. → **Mitigation**: Decision 2's
  rationale is written down here and in the spec; scope the deviation
  explicitly to `dashboard/` in code review, don't generalize it without a
  new design decision.
- **[Risk]** Search by name only (per the confirmed answer) may prove too
  narrow once the frontend actually wires up the topbar (a visitor typing a
  tracking ID or badge number would get no results). → **Mitigation**: the
  spec's requirement is scoped to name-only for this change; extending match
  fields later is additive (no breaking change) and doesn't require revising
  this design.
- **[Trade-off]** Duplicating idempotency-cache glue instead of extracting a
  shared helper (Decision 4) means two near-identical private functions exist
  across `invitations/router.py` and `dashboard/router.py`. Accepted for now
  per the no-premature-abstraction rule; worth revisiting if a third
  idempotent-PATCH endpoint shows up.
