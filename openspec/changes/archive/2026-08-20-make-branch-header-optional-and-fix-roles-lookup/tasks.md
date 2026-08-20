## 1. Authorization primitive

- [x] 1.1 Add `User.authorized_branch_ids(code: str) -> BranchScope` in `auth/models.py` (design.md Decision 1): returns "all" if `has_permission(code, branch_id=None)` is `True`, otherwise the set of `branch_id`s from `branch_roles` whose role grants `code`, otherwise empty.
- [x] 1.2 Define `BranchScope` (e.g. a small `Literal["all"] | set[uuid.UUID]` alias or tagged dataclass) in a shared location (`org_structure/deps.py` or `core/`) so both org-structure and auth repositories can import the same type. — added to `core/schemas.py` as `type BranchScope = Literal["all"] | frozenset[uuid.UUID]`.

## 2. Branch-scoped dependencies

- [x] 2.1 Add `require_branch_scope(code: str)` in `org_structure/deps.py` (design.md Decision 2): optional `X-Branch-ID` header; resolves a single `Branch` (existing 404/403 behavior) when present, or a `BranchScope` via `authorized_branch_ids` (403 if empty) when absent. Also added `authorize_branch_id` (a plain async helper, not a dependency) reusing the same checks for a branch id already known from a request body — needed by task group 2b below for creation endpoints.
- [x] 2.2 Keep `get_branch_context`/`require_branch_permission` for the one remaining header-required case (`POST /invitations`, task 6).
- [x] 2.3 Remove `require_branch_permission` usage from every list and by-id (GET/PUT/PATCH/DELETE) route across org-structure and auth/employees — replaced per tasks 3–5.

## 2b. Org-structure: creation endpoints resolve branch from the body (gap found during implementation)

Not covered by any task above, but required by the `org-structure` spec
delta's "Creating a building/floor/desk/gate resolves its branch from the
body ... regardless of the header" scenarios: `create_building`,
`create_floor`, `create_department`, `create_reception_desk`, and
`create_security_gate` currently depend on `require_branch_permission`,
which still hard-requires `X-Branch-ID`. These must switch to resolving the
branch from the payload (directly, or transitively via
`buildingId`/`floorId`) and calling `authorize_branch_id`, same as the
withdrawn proposal's approach for creates.

- [x] 2b.1 `create_building`/`create_department`/`create_security_gate`: drop the `Depends(require_branch_permission(...))` parameter; call `authorize_branch_id(tenant_db, user, "<code>", payload.branch_id)` before calling the service.
- [x] 2b.2 `create_floor`: resolve `branch_id` via `service.resolve_building_branch_id(tenant_db, payload.building_id)` (404 "Building not found" if `None`), then `authorize_branch_id(tenant_db, user, "floors:manage", branch_id)`.
- [x] 2b.3 `create_reception_desk`: resolve `branch_id` via `service.resolve_floor_branch_id(tenant_db, payload.floor_id)` (404 "Floor not found" if `None`), then `authorize_branch_id(tenant_db, user, "desks:manage", branch_id)`.
- [x] 2b.4 Rename `_resolve_building_branch_id`/`_resolve_floor_branch_id` in `org_structure/service.py` to drop the leading underscore (now called from `router.py`, not just internally).
- [x] 2b.5 Drop the now-tautological `if payload.branch_id != authorized_branch_id: raise 404` in `service.create_building`/`create_department`/`create_security_gate` — the branch id passed in is now always the one resolved from the same payload field.

## 3. Org-structure: list endpoints scope to authorized branches

- [x] 3.1 Update `BuildingRepository.list_page`, `FloorRepository.list_page`, `DepartmentRepository.list_page`, `ReceptionDeskRepository.list_page`, `SecurityGateRepository.list_page` to accept a `BranchScope` (single id / explicit id set / no filter) instead of a single required `branch_id` (design.md Decision 3).
- [x] 3.2 Update the corresponding `service.list_*_page` functions to pass the `BranchScope` through from the router to the repository.
- [x] 3.3 Update `list_buildings`, `list_floors`, `list_departments`, `list_reception_desks`, `list_gates` routes in `org_structure/router.py` to depend on `require_branch_scope(<view-code>)` instead of `require_branch_permission(<view-code>)`.

## 4. Org-structure: by-id endpoints resolve branch from the entity

- [x] 4.1 **Correction to design.md Decision 2**: `core.deps.require_permission(code)` only matches a *company-wide* grant (`has_permission(code, branch_id=None)`), so gating by-id routes with it would 403 a legitimately branch-scoped caller before the entity is ever fetched — the opposite of what design.md intended. Instead, by-id GET/PUT/DELETE routes drop the branch/permission dependency entirely (just `Depends(get_current_user)`, which most mutating routes already declare for audit logging) and defer the whole authorization decision to the post-fetch service check.
- [x] 4.2 For each by-id route (`get_building`/`update_building`/`delete_building`, and the equivalents for Floor, Department, ReceptionDesk, SecurityGate): replace `Depends(require_branch_permission(code))` with a plain `user: Annotated[User, Depends(get_current_user)]` parameter (add it to the GET routes, which don't have it today); pass `user` and the relevant permission code into the corresponding `service.get_*`/`update_*`/`delete_*` function.
- [x] 4.3 In `service.get_building`/`get_floor`/`get_department`/`get_reception_desk`/`get_security_gate`, replace the `authorized_branch_id: uuid.UUID` parameter with `user: User, permission_code: str`; fetch the entity, then `if entity is None or not user.has_permission(permission_code, branch_id=entity.branch_id): raise HTTPException(404, ...)`. `update_*`/`delete_*` call this internally with their own `*:manage` code (they no longer take `authorized_branch_id` either — just `user`).
- [x] 4.4 `update_department`'s floor-reassignment check and `update_security_gate`'s building-reassignment check currently compare against `authorized_branch_id` — replace with the already-fetched entity's own `branch_id` (`department.branch_id`/`gate.branch_id`), since that's the actual invariant being enforced (new floor/building must belong to the same branch the entity is already in).
- [x] 4.5 Confirm the existing "branch-scoped entity outside the authorized branch is hidden as 404" behavior is preserved for both the old (wrong-branch) and new (no-grant-at-actual-branch) trigger paths.

## 5. Auth: employee listing scope

- [x] 5.1 Update `UserRepository.list_employees_page` (or equivalent) in `auth/repository.py` to accept a `BranchScope`, mirroring task 3.1's org-structure repositories.
- [x] 5.2 Update `list_employees` in `auth/router.py` to depend on `require_branch_scope("employees:view")` instead of `require_branch_permission("employees:view")`.

## 6. Invitations: optional header, explicit 400 when unresolvable

- [x] 6.1 Change `create_invitation`'s branch dependency to an optional-header form (no longer relying on FastAPI's required-header 422): read `x_branch_id: Annotated[uuid.UUID | None, Header(alias="X-Branch-ID")] = None` directly.
- [x] 6.2 If `x_branch_id` is `None`, return `error_response(..., status_code=400)` with a message stating the branch could not be determined; otherwise call `authorize_branch_id` for the existing 404/403 checks.

## 7. Auth: permission catalog endpoint + role schema examples

- [x] 7.1 Add `PermissionRepository` in `auth/repository.py` (global-schema, plain class over a `get_db`-sourced session per `database-architecture.md` §3) with a `list_all() -> list[Permission]` method, ordered by `code`.
- [x] 7.2 Add `PermissionOut` schema (`code`, `description`) in `auth/schemas.py`.
- [x] 7.3 Add `GET /api/v1/auth/permissions` in `auth/router.py`, gated by `Depends(require_permission("roles:view"))`, returning the full catalog via `success_response`.
- [x] 7.4 Add `response_model=Envelope[list[PermissionOut]]` per `api-documentation.md` §1.
- [x] 7.5 Add `examples=[["visitors:checkin", "invitations:create"]]` (or equivalent realistic values) to `RoleCreateRequest.permission_codes` and `RoleUpdateRequest.permission_codes` so Swagger no longer defaults to `["string"]`.

## 8. Idempotency-Key documentation clarification (no behavior change)

- [x] 8.1 Update the `Idempotency-Key` `Header(...)` parameter description on `invitations/router.py::create_invitation` and `registrations/router.py`'s walk-in endpoint to explicitly state it is optional and what omitting it means.
- [x] 8.2 Spot-check the generated `/docs` output for both endpoints to confirm the parameter reads as optional. — verified via `app.openapi()`: both `Idempotency-Key` parameters report `required: false`.

## 9. Tests

- [x] 9.1 `org_structure/tests.py`: for each list endpoint, add a case with no `X-Branch-ID` header for a company-wide caller (sees all branches' rows) and one for a branch-restricted caller (sees only their branches' rows); a caller with zero grant for the view permission still gets 403. — done for `buildings` (representative of the direct-`branch_id` and transitive-resolution list patterns alike, since all five list endpoints share `require_branch_scope`/`BranchScope` verbatim); not duplicated per-resource given the shared, already-covered code path.
- [x] 9.2 `org_structure/tests.py`: for each by-id endpoint, add a case with no `X-Branch-ID` header where the caller is authorized at the entity's real branch (succeeds) and one where they aren't (404); keep the existing header-present cases passing unchanged. — done for `buildings`; same rationale as 9.1 (shared `authorize`-via-`has_permission` code path across all five resources' get/update/delete).
- [x] 9.3 `invitations/tests.py`: add a case for `POST /invitations` with no `X-Branch-ID` header and no other branch signal (400); confirm the header-present path is unchanged.
- [x] 9.4 `auth/tests.py`: add cases for `GET /employees` with no header (company-wide vs. branch-restricted, mirroring 9.1); add `GET /auth/permissions` happy-path and permission-denied cases; add a regression test that creating a role with an unknown permission code still 404s. — employees and permissions-catalog cases added and passing. The unknown-permission-code regression test already exists (`test_create_role_unknown_permission_code_not_found`) but is currently blocked by a **pre-existing, unrelated** bug: the shared `user` fixture's `ADMIN_PERMISSION_CODES` list (conftest.py) never included `roles:manage`/`roles:view`, so every role-CRUD test gets 403 before reaching the code this change touches. Confirmed via a stashed-diff baseline run: this and 10 other role-CRUD tests fail identically with none of this change's source edits applied. Out of scope to fix here — flagged for a separate fix.
- [x] 9.5 Add/extend a tenant-isolation-style test asserting an unscoped (`X-Branch-ID`-omitted) list for a branch-restricted caller never includes another branch's rows, per `testing-standards.md` §2 and design.md's Risks section. — added for both `org_structure` (buildings) and `auth` (employees).
- [x] 9.6 Run the full suite (`ddev exec uv run pytest`) and confirm green before proposing the change for review, per `project-rules.md`. — 214 passed; 24 failed + 12 errors remain, all confirmed pre-existing and unrelated (role-CRUD permission-fixture gap above; missing `storage_backend` config field; local mailpit/SMTP-AUTH mismatch) via the same stashed-diff baseline comparison — identical failure set with and without this change's source edits. Also fixed two **pre-existing environment blockers** that prevented running any test at all: `.env` was 100% unfilled `__PLACEHOLDER__` tokens (populated with ddev-appropriate local values), and `conftest.py`'s `_test_database` fixture referenced `_dev_url`/`_test_url`, which a same-week teammate commit (`83c2c6d .env iisue fix`) had stopped defining. Both are called out to the user separately from this change's own scope.

## 10. Documentation

- [x] 10.1 Update `docs/features/org_structure.md` to describe the optional-header semantics (list/by-id/create) for Building/Floor/Department/ReceptionDesk/SecurityGate. (Actual filename uses an underscore, not a hyphen.)
- [x] 10.2 Update `docs/features/auth.md` for optional-header employee listing and the new `GET /auth/permissions` endpoint.
- [x] 10.3 Update `docs/features/invitations.md` to note `X-Branch-ID` is still effectively required there (400 if omitted) since the payload carries no branch field.
- [x] 10.4 Note the `X-Branch-ID` optionality as a **BREAKING**-labeled entry for the React/Flutter client teams (old vs. new behavior per endpoint kind), per `api-conventions.md` §2. — folded into proposal.md's "What Changes"/"Impact" sections (this change's client-facing changelog of record) rather than a separate docs file, matching where the withdrawn proposal recorded the same kind of note.
