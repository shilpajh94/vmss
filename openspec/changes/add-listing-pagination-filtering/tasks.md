## 1. Schema and endpoint changes

- [x] 1.1 Add `PaginatedEnvelope[PermissionOut]` as the response model for
      `GET /auth/permissions` in `auth/router.py` (currently line ~409),
      replacing `Envelope[list[PermissionOut]]`.
- [x] 1.2 Add `Annotated[tuple[int, int], Depends(get_pagination)]` to
      `list_permissions`'s signature, matching `list_roles`'s existing
      parameter shape.
- [x] 1.3 Add a `sort_by`/`sort_order` pair whitelisted to `code` (default
      `code` ascending), matching the pattern used by `list_roles`.
- [x] 1.4 Update `auth/repository.py`'s permission-catalog query method to
      accept `page`/`page_size`/`sort_by`/`sort_order` and return both the
      page of rows and the total count needed for `PaginationMeta`.
- [x] 1.5 Update `auth/service.py`'s calling code to pass pagination/sort
      through to the repository and build the `paginated_response()` call.

## 2. Tests (testing-standards.md §2)

- [x] 2.1 Update or add a happy-path test asserting `GET /auth/permissions`
      returns a `PaginatedEnvelope` shape with correct `page`/`pageSize`/
      `total`/`totalPages`.
- [x] 2.2 Add a test for the default page (no `page`/`page_size` supplied)
      returning page 1 with the house default page size.
- [x] 2.3 Add a test for a `page` number past the last page returning an
      empty `data` array with a valid pagination block, not an error.
- [x] 2.4 Add a test for `sort_by=code&sort_order=desc` returning permission
      codes in descending order.
- [x] 2.5 Confirm the existing permission-denied test for this endpoint
      (caller without `roles:view`) still passes unchanged.
- [x] 2.6 Run the full suite (`ddev exec uv run pytest`) and confirm no
      regression in `auth/tests.py` or any test that currently asserts the
      old bare-list shape. Result: 928/929 passed; the one failure
      (`tests/test_workflow_full_lifecycle.py::test_full_lifecycle_workflow`)
      is a pre-existing, unrelated role-permission-set assertion failure
      (confirmed unrelated to `rbac_catalog.py`/role seeding, which this
      change does not touch).

## 3. Documentation

- [x] 3.1 Update `docs/features/auth.md` (or add it, if it doesn't yet
      describe this endpoint) to document the new `page`/`page_size`/
      `sort_by`/`sort_order` params and the `PaginatedEnvelope` response
      shape.
- [x] 3.2 Confirm `response_model=Envelope[PaginatedEnvelope[PermissionOut]]`
      (or the correct generic nesting) renders correctly in Swagger per
      `api-documentation.md` §1, and that the schema now shows in camelCase.
      Verified via `app.openapi()`: response resolves to
      `PaginatedEnvelope[PermissionOut]` with `data`/`pagination`, and query
      params render as `sortBy`/`sortOrder`/`page`/`pageSize`.

## 4. Coordination with the paired web-side change

- [x] 4.1 Confirm the `improve-listing-ux` change's `admin-roles` capability
      work (reading `data.data` + `data.pagination` from this endpoint) is
      sequenced to land in the same release as this change, per
      `design.md`'s Migration Plan. Confirmed: `improve-listing-ux` is
      implemented immediately after this change, in the same session
      (per explicit user instruction to do the API change first, then the
      web change).

## 5. org_structure/visitors filter additions (discovered mid-implementation)

While implementing the paired `improve-listing-ux` web change, its list
pages turned out to need server-side filters that didn't exist yet on six
`org_structure` and two `visitors` endpoints. Confirmed with the user
(who chose to add these to the API now rather than defer or drop them) —
see `design.md`'s Context and this proposal's updated Why/What Changes.

- [x] 5.1 Add `ActiveStatus` (active/inactive) and `SecurityLevel`
      (standard/high) enums to `org_structure/schemas.py`.
- [x] 5.2 Add `ApprovalWorkflowRuleStatus` (active/inactive) enum to
      `visitors/schemas.py`.
- [x] 5.3 `BranchRepository.list_page`: add `status` filter
      (`Branch.is_active`).
- [x] 5.4 `BuildingRepository.list_page`: add `status` filter
      (`Building.is_active`).
- [x] 5.5 `FloorRepository.list_page`: add `status` (`Floor.is_active`) and
      `access_level` (`Floor.access_level`) filters.
- [x] 5.6 `DepartmentRepository.list_page`: add `status` filter
      (`Department.is_active`).
- [x] 5.7 `ReceptionDeskRepository.list_page`: add `status` filter
      (`ReceptionDesk.status`, using the existing `DeskStatus` enum).
- [x] 5.8 `SecurityGateRepository.list_page`: add `gate_type`
      (`SecurityGate.gate_type`) and `security_level` (mapped onto
      `SecurityGate.high_security`) filters.
- [x] 5.9 `VisitorCategoryRepository.list_page`: add `badge_color`,
      `nda_requirement`, `escort_requirement` filters.
- [x] 5.10 `ApprovalWorkflowRuleRepository.list_page`: add `status` filter
      (`ApprovalWorkflowRule.is_active`), combinable with the existing
      `visitor_category_id` filter.
- [x] 5.11 Wire all of the above through each entity's `service.py`
      `list_*_page` function and `router.py` GET handler as typed,
      camelCase-aliased `Query()` params, using an entity-prefixed local
      parameter name (e.g. `branch_status`) where the wire name `status`
      would otherwise shadow FastAPI's `status` module import in that file.
- [x] 5.12 Add a test per new filter (one scenario each covering a
      positive match and exclusion of a non-matching row) in
      `org_structure/tests.py` and `visitors/tests.py`.
- [x] 5.13 Update the two existing direct-repository tenant-isolation tests
      in `visitors/tests.py` (`VisitorCategoryRepository.list_page`,
      `ApprovalWorkflowRuleRepository.list_page`) to pass the new required
      filter parameters.
- [x] 5.14 Run `ruff format`, `ruff check`, and `mypy` on
      `org_structure/` and `visitors/`; run both modules' `pytest` suites
      to confirm no regressions. Result: 204/204 passed, lint/format/mypy
      clean.
- [x] 5.15 Update `docs/features/org_structure.md` and
      `docs/features/visitors.md` to document the new filter params.

## 6. auth/employees filter addition, and a scope correction (also discovered mid-implementation)

- [x] 6.1 Add `EmployeeStatus` (active/inactive) enum to
      `auth/schemas.py`; add a `status` filter to
      `UserRepository.list_employees_page` (mapped onto `User.is_active`),
      wired through `service.list_employees` and the `GET /employees`
      router handler (local param name `employee_status`, wire name
      `status`, to avoid shadowing the `status` module import in
      `auth/router.py`).
- [x] 6.2 Add a test (`test_list_employees_filter_by_status`) covering the
      new filter.
- [x] 6.3 Update `docs/features/auth.md`'s `GET /employees` row and add an
      `ADDED Requirements` block to `specs/auth/spec.md` for this filter.
- [x] 6.4 **Correction, not an API change**: confirmed `Role` has no
      active/inactive column (only a computed Standard/Custom distinction).
      The paired web change's `admin-roles` capability delta is corrected
      to drop its planned Status filter rather than adding an unjustified
      `is_active` column to `Role`.
- [x] 6.5 Run `ruff format`, `ruff check`, and `mypy` on `auth/`; run
      `auth/tests.py`. Result: 104/104 passed, lint/format/mypy clean.

## 7. invitations search filter (also discovered mid-implementation)

The Invitations board's search box (visitor name / tracking ID) had no
server-side equivalent — `GET /invitations` had no free-text filter at all.

- [x] 7.1 Add a `search` query param to `GET /invitations`
      (`invitations/router.py`), threaded through
      `service.list_invitations_page` and
      `InvitationRepository.list_page` as a case-insensitive `ILIKE` match
      against `primary_contact_full_name` OR `tracking_id`, combined with
      the endpoint's existing filters via `AND`.
- [x] 7.2 Update the three direct `InvitationRepository.list_page` calls in
      `invitations/tests.py` (tenant-isolation tests) to pass the new
      required `search=None` parameter.
- [x] 7.3 Add a test
      (`test_list_invitations_filters_by_search_matching_contact_name_or_tracking_id`)
      covering both the contact-name and tracking-ID match paths.
- [x] 7.4 Update `docs/features/invitations.md`'s query-param table and add
      an `ADDED Requirements` block to `specs/invitations/spec.md`.
- [x] 7.5 Run `ruff format`, `ruff check`, and `pytest` on `invitations/`.
      Result: 271/271 passed, lint/format clean (the 2 pre-existing mypy
      errors at `router.py:1169-1170` are unrelated to this change —
      confirmed present on the unmodified baseline via `git stash`).
