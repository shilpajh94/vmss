## 1. Feature Scaffolding

- [x] 1.1 Create `src/vmss_api/dashboard/` with `__init__.py`, `router.py`,
      `service.py`, `repository.py`, `schemas.py`, `deps.py`, `tests.py`
      (no `models.py` — this feature owns no table, per design.md Decision 1).

## 2. Schemas

- [x] 2.1 In `dashboard/schemas.py`, add `CamelModel`-based response schemas:
      `DashboardOverviewOut` (counts + `upcomingVisitors`),
      `UpcomingVisitorOut` (id, trackingId, primaryContactFullName, hostId,
      purposeOfVisit, expiresAt), `DashboardCheckInRequest` (`invitationId:
      UUID`), `DashboardCheckInListItemOut` (id, trackingId,
      primaryContactFullName, hostId, branchId, status, checkedInAt,
      checkedOutAt), `DashboardSearchResultOut` (id, trackingId,
      primaryContactFullName, status, branchId).
- [x] 2.2 Add a `query` request-query validator for search requiring a
      minimum length of 2 characters (spec.md "Query below the minimum
      length is rejected"). (Implemented as `Query(min_length=2)` directly
      on the router's `query` param in `dashboard/router.py::search` — a
      single scalar query param doesn't need its own request schema class.)

## 3. Branch Scope Dependency

- [x] 3.1 In `dashboard/deps.py`, add `resolve_dashboard_branch_scope(permission_code)`
      mirroring `org_structure.deps.require_branch_scope`'s logic but
      reading `branch_id` from an optional `branchId` query parameter
      instead of the `X-Branch-ID` header (design.md Decision 2): narrow to
      one branch via `authorize_branch_id` when supplied, otherwise fall
      back to `user.authorized_branch_ids(permission_code)`, returning 403
      if that resolves to an empty set.

## 4. Repository (read queries over `invitations.models.Invitation`)

- [x] 4.1 In `dashboard/repository.py`, add `DashboardRepository` (no owned
      model — reads `invitations.models.Invitation` directly, same posture
      as `reports/repository.py::BranchRollupRepository`).
- [x] 4.2 `overview_counts(branch_scope, day_start_utc, day_end_utc) ->` counts
      for visits-created-today, checked-in, pending-approval, and
      upcoming-visitor counts — one grouped/filtered query per count, scoped
      by `branch_scope` (a single branch id or "all authorized").
- [x] 4.3 `upcoming_visitors_preview(branch_scope, limit=10)` — `approved`,
      non-expired invitations ordered by `expires_at` ascending, capped at
      `limit`.
- [x] 4.4 `paginated_checkins(branch_scope, page, page_size, sort_by, sort_order)`
      — invitations with status `checked_in` or `checked_out`, one page +
      total count query (`query-performance.md` §2 — no per-row loop).
- [x] 4.5 `search_by_contact_name(branch_scope, query, limit)` — case-insensitive
      `ILIKE` partial match on `primary_contact_full_name`, capped at
      `limit`.

## 5. Service

- [x] 5.1 In `dashboard/service.py`, add `get_overview(tenant, branch_scope)`:
      resolve the tenant's local "today" boundary from `Tenant.timezone`
      (stdlib `zoneinfo`, design.md Decision 5), call the repository's
      count + preview methods, assemble `DashboardOverviewOut`. (Also falls
      back to UTC with a `WARNING` log if `Tenant.timezone` doesn't resolve
      via `zoneinfo` — that column has no DB-level validation today and
      this is its first real consumer; see `_resolve_tenant_timezone`.)
- [x] 5.2 Add `check_in_upcoming_visitor(tenant_db, invitation_id, user, tenant)`:
      fetch the invitation, `authorize_branch_id_tolerant(..., "invitations:checkin", ...)`,
      then call `invitations.service.check_in_invitation` directly (design.md
      Decision 4 — no reimplementation of the check-in rule).
- [x] 5.3 Add `list_checkins_page(branch_scope, page, page_size, sort_by, sort_order)`
      and `search_visitors(branch_scope, query, limit)` thin wrappers over the
      repository methods.

## 6. Router

- [x] 6.1 `GET /admin/dashboard/overview` — `require_permission`-equivalent via
      `resolve_dashboard_branch_scope("invitations:view")`, calls
      `service.get_overview`, returns `success_response` with
      `response_model=Envelope[DashboardOverviewOut]`.
- [x] 6.2 `PATCH /admin/dashboard/upcoming-visitors` — accepts
      `DashboardCheckInRequest` body and optional `Idempotency-Key` header
      (same Redis cache convention as `invitations/router.py`'s check-in
      endpoint — design.md Decision 4), calls
      `service.check_in_upcoming_visitor`, records the same
      `invitation_checked_in` audit action via `background_tasks`, returns
      `Envelope[InvitationOut]` (reusing `invitations.schemas.InvitationOut`
      and its `to_invitation_out` mapper).
- [x] 6.3 `GET /admin/dashboard/checkins` — `resolve_dashboard_branch_scope("invitations:view")`
      + `get_pagination` + `sortBy`/`sortOrder` query params, calls
      `service.list_checkins_page`, returns `paginated_response` with
      `response_model=PaginatedEnvelope[DashboardCheckInListItemOut]`.
- [x] 6.4 `GET /admin/dashboard/search` — `resolve_dashboard_branch_scope("invitations:view")`
      + validated `query` param, calls `service.search_visitors`, returns
      `success_response` with `response_model=Envelope[list[DashboardSearchResultOut]]`.

## 7. Registration

- [x] 7.1 Add `api_router.include_router(dashboard.router.router)` in
      `src/vmss_api/api.py` (`fastapi-architecture.md` §7).
- [x] 7.2 Add a `"dashboard"` entry (with a non-empty description) to
      `main.py`'s `_TAGS_METADATA` (`api-documentation.md` §2).

## 8. Tests (`dashboard/tests.py`)

- [x] 8.1 Happy-path test per endpoint (overview counts + preview, check-in
      action, paginated checkins list, search) via `httpx.AsyncClient`,
      using factory-built `Invitation` rows (`testing-standards.md` §1), not
      hand-built dicts. (Also fixed two pre-existing test-fixture gaps this
      feature was the first to expose: `TenantFactory`/`InvitationFactory`
      don't honor `Tenant.timezone`'s/`Invitation.created_at`'s real
      defaults, since polyfactory generates a value for every column
      regardless of a Python- or server-side default — see the `tenant`
      fixture in `conftest.py` and `dashboard/tests.py::_build_invitation`.)
- [x] 8.2 Permission-denied case: a caller lacking `invitations:view` gets 403
      from overview/checkins/search; a caller lacking `invitations:checkin`
      gets 403 from the check-in action (`testing-standards.md` §2).
- [x] 8.3 Tenant-isolation case: an invitation in another tenant's schema
      never appears in overview counts, the checkins list, or search results
      for the caller's own tenant (`testing-standards.md` §2, using
      `make_tenant_schema`/`open_tenant_session`).
- [x] 8.4 `branchId` scoping tests: narrowed-to-one-branch vs.
      aggregated-across-authorized-branches vs. 403 for an unauthorized
      `branchId` (spec.md scenarios).
- [x] 8.5 Check-in business-rule tests: non-`approved` invitation rejected
      with 409, watchlist-flagged invitation rejected with 409, retried
      request with the same `Idempotency-Key` does not double-check-in.
- [x] 8.6 "Today" boundary test: a tenant configured with a non-UTC timezone
      at a moment where UTC and local date disagree — verify the
      visits-created-today count uses the tenant's local date. (Implemented
      as a pure-function test of `dashboard/service.py::_today_bounds_utc`
      per testing-standards.md §3, rather than monkeypatching real time
      through the HTTP endpoint.)
- [x] 8.7 Search tests: partial case-insensitive match, below-minimum-length
      query rejected, no-match returns empty list with 200.

## 9. Documentation

- [x] 9.1 Add `docs/features/dashboard.md` describing the four endpoints,
      the `branchId` query-param convention (and why it differs from
      `X-Branch-ID` elsewhere — design.md Decision 2), and the reused
      permission codes.
