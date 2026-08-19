## 1. RBAC Catalog

- [x] 1.1 Add `roles:manage` and `roles:view` to `PERMISSION_CODES` in `auth/rbac_catalog.py`, and grant both to the `admin` role's default permission set
- [x] 1.2 Confirm `seed_default_roles`'s idempotent check-before-insert still passes against an already-provisioned tenant schema (adds the two new permission rows only)

## 2. Role CRUD (auth)

- [x] 2.1 Extend `RoleRepository` (`auth/repository.py`) with `create`, `list_page`, `update`, and use the existing `TenantScopedRepository.get`/`soft_delete` for get/delete; add a `get_by_name` case-insensitive variant if the current one isn't already
- [x] 2.2 Add `RoleCreateRequest`, `RoleUpdateRequest`, `RoleOut`, `RoleVerifyResponse` schemas (`CamelModel` subclasses) to `auth/schemas.py`
- [x] 2.3 Add service functions in `auth/service.py`: `create_role` (validates permission codes exist in catalog, checks name uniqueness), `update_role` (rejects rename/permission-set-untouched-name-check for standard roles per Decision 1, full-replace of `role_permissions` per Decision 2), `delete_role` (rejects standard roles, rejects roles with active `UserBranchRole` grants with 409), `verify_role_name` (case-insensitive availability check)
- [x] 2.4 Add router endpoints to `auth/router.py`: `POST /auth/roles`, `GET /auth/roles` (paginated), `GET /auth/roles/{id}`, `PUT /auth/roles/{id}`, `DELETE /auth/roles/{id}`, `GET /auth/roles/verify` — all gated by `roles:manage`/`roles:view` as appropriate, all using `success_response`/`paginated_response` and `response_model=Envelope[...]`/`PaginatedEnvelope[...]` per `api-documentation.md` §1
- [x] 2.5 Add `DELETE /auth/users/{user_id}/branch-roles/{assignment_id}` to revoke a branch-role grant, gated by `users:manage`
- [x] 2.6 Wire audit logging (`record_audit_log` via `BackgroundTasks`) for role create/update/delete and branch-role revocation, per `security-architecture.md` §5 and `logging-observability.md`

## 3. Employee Directory Read Enhancements (auth)

- [x] 3.1 Add `avatar_url` column to `User` model (nullable string) with a tenant migration
- [x] 3.2 Add `avatar_url` and `branch_roles: list[BranchRoleOut]` to `EmployeeOut` schema; update `_to_employee_out` in `auth/router.py` to populate both (branch_roles already loaded via `User.branch_roles` relationship)

## 4. Department Branch Scoping (org_structure)

- [x] 4.1 Add `branch_id: Mapped[uuid.UUID]` to `Department` model, make `floor_id: Mapped[uuid.UUID | None]`; replace the `(floor_id, code)` unique index with `(branch_id, code)` scoped to non-deleted rows
- [x] 4.2 Write the tenant migration: add nullable `branch_id`, pre-check query for `(branch_id, code)` collisions across existing rows and abort with a report if any exist, backfill `branch_id` from `floor → building → branch`, add the new partial unique index, make `branch_id` non-nullable, make `floor_id` nullable, drop the old index
- [x] 4.3 Update `DepartmentCreate`/`DepartmentOut`/`DepartmentUpdate` schemas: `branch_id` required, `floor_id` optional; add `head_of_department_user_id` (optional UUID) and `description` (optional string)
- [x] 4.4 Update `org_structure/service.py`/`router.py`/`repository.py` department create/list/update paths to authorize and filter by `branch_id` directly instead of only via floor join; keep floor-scoped lookups working where `floor_id` is set
- [x] 4.5 Update bulk-provisioning (branch tree creation) to populate `Department.branch_id` directly, still accepting nested floor placement as optional

## 5. Branch, Building, Floor Field Additions (org_structure)

- [x] 5.1 Add `city`, `country`, `contact_person_user_id`, `contact_email`, `contact_phone`, `operating_hours_from`, `operating_hours_to`, `notes` columns to `Branch`; add corresponding fields to `BranchCreate`/`BranchOut`/`BranchUpdate`, with `is_active` now settable on `BranchCreate`
- [x] 5.2 Make `is_active` settable on `BuildingCreate` (model already has the column)
- [x] 5.3 Add `capacity` (int, nullable), `capacity_type` (enum: `guests`/`staff`, nullable), `access_level` (enum: `public`/`restricted`/`secure`, nullable) columns to `Floor`; add corresponding schema fields
- [x] 5.4 Write the tenant migration(s) for Branch/Building/Floor new columns (additive only, no backfill needed)

## 6. Reception Desk and Security Gate Status (org_structure)

- [x] 6.1 Add `status` column (`active`/`maintenance`/`inactive`) to `ReceptionDesk`; add `assigned_receptionist_user_id`, `operating_hours_from`, `operating_hours_to` columns
- [x] 6.2 Add `connectivity_status` column (`online`/`maintenance`/`offline`), `high_security` (bool, default false), `auth_method` (nullable string) to `SecurityGate`
- [x] 6.3 Write the tenant migration for both: add new columns nullable, backfill `status`/`connectivity_status` from existing `is_active` (`true`→`active`/`online`, `false`→`inactive`/`offline`) via a single `UPDATE`, make the new status column non-nullable with its default, drop `is_active` from both tables
- [x] 6.4 Update `ReceptionDeskCreate`/`Out`/`Update` and `SecurityGateCreate`/`Out`/`Update` schemas to use the new enum-typed status fields in place of `is_active`; update any service/router code and tests referencing `is_active` on these two models
- [x] 6.5 Update bulk-provisioning payload schemas/service code for ReceptionDesk/SecurityGate to accept the new status fields instead of `is_active` (no change needed: bulk-provisioning never exposed `is_active`; new status columns default sensibly at the model level)

## 7. Company Profile Policy Fields (org_structure)

- [x] 7.1 Add `default_timezone` (nullable string), `auto_approve_pre_registered_visitors` (bool, default false), `badge_expiry_duration_minutes` (nullable int) columns to `Company`; write the additive tenant migration
- [x] 7.2 Add corresponding fields to `CompanyCreate`/`CompanyOut`/`CompanyUpdate` schemas

## 8. Visitor Category Field Additions (visitors)

- [x] 8.1 Add `badge_color` (nullable string), `nda_requirement` (enum: `digital`/`signed_pdf`/`optional`/`none`, nullable), `escort_requirement` (enum: `self_escort`/`access_logs_only`/`always_required`/`gate_check_in_only`, nullable), `max_duration_minutes` (nullable int) columns to `VisitorCategory`
- [x] 8.2 Write the additive tenant migration for the new `VisitorCategory` columns
- [x] 8.3 Add corresponding fields and enums to `VisitorCategoryCreate`/`Out`/`Update` schemas in `visitors/schemas.py`, with 422 validation on the two enum fields

## 9. Tests

- [x] 9.1 Role CRUD: happy path for create/list/get/update/delete/verify; permission-denied case (caller without `roles:manage`); tenant-isolation case (role created in tenant A's schema not visible from tenant B's session)
- [x] 9.2 Standard-role protection: renaming or deleting Admin/Reception/Security/Host/Visitor is rejected (new tests); a freshly provisioned tenant still has exactly the five seeded roles with their default permissions (already covered by `platform/tests.py`, unaffected by this change)
- [x] 9.3 Role deletion with active grants: deleting a custom role that has a `UserBranchRole` grant is rejected with 409; deleting one with no grants succeeds
- [x] 9.4 Branch-role revocation: happy path, and a revoked grant's permission checks subsequently fail
- [x] 9.5 Department branch scoping: create with `branch_id` and no `floor_id` succeeds and lists correctly (pytest); migration backfill verified manually via `ddev` against a real scratch schema — confirmed both the collision-abort path (two same-branch departments sharing a code) and correct `branch_id` backfill from `floor -> building -> branch` (pytest doesn't exercise Alembic at all in this project — `conftest.py` builds the test schema via `Base.metadata.create_all`, not migrations)
- [x] 9.6 ReceptionDesk/SecurityGate tri-state status: create/update through each of the three states (pytest); migration backfill verified manually via `ddev` for the same reason as 9.5
- [x] 9.7 VisitorCategory new fields: happy path create/update with each enum value; 422 on an invalid `ndaRequirement` value
- [x] 9.8 Update `factories.py` for every changed model (`Role`, `Department`, `ReceptionDesk`, `SecurityGate`, `Branch`, `Building`, `Floor`, `Company`, `VisitorCategory`, `User`) so factory-built rows include the new required/typical fields — including pinning the three new nullable FKs into `users` (`Branch.contact_person_user_id`, `Department.head_of_department_user_id`, `ReceptionDesk.assigned_receptionist_user_id`) to `None`, matching the existing `UserFactory.department_id = None` precedent, so polyfactory doesn't generate a random UUID that violates the FK

## 10. Documentation

- [x] 10.1 Add or update `docs/features/auth.md` describing the Role management endpoints, the standard-vs-custom role distinction, and the verify-name check
- [x] 10.2 Update `docs/features/org_structure.md` (or equivalent) with the new Branch/Building/Floor/Department/ReceptionDesk/SecurityGate/Company fields and the Department branch-scoping change
- [x] 10.3 Update `docs/features/visitors.md` (or equivalent) with the new VisitorCategory fields and enums
- [x] 10.4 Update `.env.example` if any new setting is introduced — confirmed none needed (no `core/config.py` changes in this change)

## 11. Verification

- [x] 11.1 `ruff check` and `ruff format --check` clean
- [x] 11.2 `mypy` clean on `auth/` and any other touched module under strict-typing scope (ran across all of `src/vmss_api`, clean)
- [x] 11.3 Full `pytest` suite green, including all new tests from Section 9 (229 passed)
- [x] 11.4 Confirm every new/changed router is still discovered by `tests/test_api_documentation.py::test_every_feature_router_is_registered_in_api_router` and that new response schemas render camelCase per `api-documentation.md` §5
