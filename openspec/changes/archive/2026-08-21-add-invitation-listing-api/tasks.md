## 1. Schemas

- [x] 1.1 Add `InvitationSortableField` (or equivalent `Literal`/enum) in
      `invitations/schemas.py` with `submitted_at` (default) and
      `created_at`.
- [x] 1.2 Add `InvitationListItemOut(CamelModel)` in `invitations/schemas.py`
      with: `id`, `tracking_id`, `registration_type`, `source`, `status`,
      `primary_contact_full_name`, `purpose_of_visit`, `expires_at`,
      `submitted_at`.

## 2. Repository

- [x] 2.1 Add `InvitationRepository.list_page(*, branch_scope, status,
      registration_type, source, page, page_size, sort_by, sort_order)` in
      `invitations/repository.py`, built on
      `TenantScopedRepository.paginate` (query-performance.md §1/§2): no
      `selectinload` of visitors/vehicles, branch filter via the same
      `_branch_filter`-style `BranchScope` → `IN (...)`/no-filter translation
      `org_structure/repository.py` uses, plus optional equality filters for
      `status`/`registration_type`/`source`.
- [x] 2.2 Map `sort_by` to `Invitation.submitted_at`/`Invitation.created_at`
      via an explicit whitelist dict (never a raw client string into
      `order_by()`), matching `BranchRepository.list_page`'s pattern.

## 3. Service

- [x] 3.1 Add `list_invitations_page` in `invitations/service.py` that
      accepts the same params as `repository.list_page` and returns
      `tuple[list[Invitation], int]`, delegating straight through (matching
      `org_structure/service.py::list_branches_page`'s shape).

## 4. Router

- [x] 4.1 Add `GET /invitations` in `invitations/router.py`, gated by
      `Depends(require_branch_scope("invitations:view"))`
      (`org_structure/deps.py`), with `pagination: Annotated[tuple[int,
      int], Depends(get_pagination)]`, `sort_by`/`sort_order` query params,
      and optional `status`/`registrationType`/`source` query params.
- [x] 4.2 Set `response_model=PaginatedEnvelope[InvitationListItemOut]` on
      the route (api-documentation.md §1) and return via
      `paginated_response(...)` (`core/responses.py`), matching
      `list_branches`'s shape exactly.
- [x] 4.3 Place the new route before `GET /invitations/track` is unaffected
      by route ordering (distinct path, no prefix collision) — verify
      `/invitations` vs `/invitations/track` both resolve correctly once
      both exist on the same router.

## 5. Tests (testing-standards.md §2)

- [x] 5.1 Happy path: authenticated caller with `invitations:view` lists
      invitations, paginated response shape matches `PaginatedEnvelope`.
- [x] 5.2 Permission-denied case: caller without `invitations:view` at any
      branch gets 403.
- [x] 5.3 Branch-scoping cases: `X-Branch-ID` narrows to one branch; an
      unauthorized branch id is rejected (403); omitting the header returns
      results across every branch the caller is authorized at.
- [x] 5.4 Tenant-isolation case: a second tenant schema's invitations are
      never returned to the first tenant's session
      (`testing-standards.md` §2's `make_tenant_schema`/
      `open_tenant_session` fixtures).
- [x] 5.5 Filtering cases: `status`, `registrationType`, `source` each
      narrow results correctly, including combined filters.
- [x] 5.6 Sorting cases: default sort order, explicit `sortBy`/`sortOrder`,
      and an invalid `sortBy` value rejected with a validation error.
- [x] 5.7 Build invitation test rows via the existing factory
      (testing-standards.md §1), not hand-built dicts.

## 6. Documentation

- [x] 6.1 Update `docs/features/invitations.md` (or create it if it does not
      yet exist) with the new endpoint, its query params, and response
      shape.
