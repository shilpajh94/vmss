## 1. Re-Audit API-03 and API-04 (no code change)

- [x] 1.1 Confirmed full CRUD exists and is branch-scoped correctly for
      Company, Branch, Building, Floor, Department, ReceptionDesk,
      SecurityGate (`org_structure/router.py`/`service.py`/`repository.py`)
      — 70 passing tests covering happy path, permission-denial,
      tenant-schema isolation, and cross-branch 404s per entity.
- [x] 1.2 Confirmed employee directory sync (`auth/service.py::sync_employee_directory`,
      `POST /auth/employees/sync`) batch-reconciles correctly: N+1-safe
      (`query-performance.md` §2/§3), validates every `department_id`
      up front, deactivates (not deletes) departed employees — 6 passing
      tests.
- [x] 1.3 Reproduced, in a rolled-back transaction against the real
      `vmss_test` database, that a soft-deleted `Branch`'s `code` still
      collides at the DB level on the next insert with the same code, even
      though the app-level `get_by_code` check reports it as free — see
      proposal.md's verification note. Confirmed via migration/`\d` output
      that the same unconditional-unique-constraint pattern applies to all
      seven entities (design.md's table).
- [x] 1.4 Confirmed `CompanyCreate`/`CompanyUpdate.email` is plain `str`
      while every other email field in the codebase (`auth`, `platform`,
      `invitations`) is `EmailStr`.

## 2. Migration: Partial Unique Indexes (design.md Decision 1)

- [x] 2.1 Added `alembic_tenant/versions/880cf061a484_org_structure_partial_unique_indexes.py`
      (revises head `a1c9d4f7e2b0`): for each of `branches.code`,
      `companies.registration_number`, `buildings(branch_id, code)`,
      `floors(building_id, floor_number)`, `departments(floor_id, code)`,
      `reception_desks(floor_id, code)`, `security_gates(branch_id, code)`,
      drops the existing unconditional unique constraint/index and creates
      a unique index scoped to `deleted_at IS NULL` in its place. Verified
      `alembic -c alembic_tenant.ini heads` resolves cleanly to this
      revision.
- [x] 2.2 `downgrade()` reverses both steps per table, restoring the
      original unconditional constraint/index under its original name.

## 3. Model Changes (mirror the migration)

- [x] 3.1 `org_structure/models.py`: replaced the plain
      `UniqueConstraint(...)` in `__table_args__` for `Building`, `Floor`,
      `Department`, `ReceptionDesk`, `SecurityGate` with
      `Index(..., unique=True, postgresql_where=_NOT_DELETED)` (a shared
      `_NOT_DELETED = text("deleted_at IS NULL")` module constant).
- [x] 3.2 `Branch.code`: removed `unique=True`/`index=True` from the column
      definition; added the equivalent partial `Index` to `__table_args__`.
- [x] 3.3 `Company.registration_number`: removed `unique=True` from the
      column definition; added the equivalent partial `Index` to
      `__table_args__`.

## 4. Service-Layer Race Guard (design.md Decision 2)

- [x] 4.1 Added `_commit_or_conflict(tenant_db, conflict_detail)` helper and
      wired it into `create_company`/`update_company`, `create_branch`,
      `provision_branch`, `create_building`/`update_building`,
      `create_floor`/`update_floor`, `create_department`/`update_department`,
      `create_reception_desk`/`update_reception_desk`,
      `create_security_gate`/`update_security_gate` — 14 call sites total
      (the plan's 13 plus `provision_branch`'s bulk-insert commit, added for
      consistency with design.md Decision 2's "every affected create/update
      path"). `update_branch`/every `delete_*` correctly left unwrapped —
      neither touches a uniquely-constrained column or inserts a row.

## 5. Company Email Validation (design.md Decision 3)

- [x] 5.1 `org_structure/schemas.py`: changed `CompanyCreate.email` and
      `CompanyUpdate.email` from `str | None` to `EmailStr | None`.

## 6. Tests

- [x] 6.1 Added `test_create_branch_after_soft_delete_reuses_code` — delete a
      branch, then create a new one with the same `code`; assert 201.
- [x] 6.2 Added `test_create_company_after_soft_delete_reuses_registration_number`
      (same pattern, `registration_number`).
- [x] 6.3 Added `test_create_building_after_soft_delete_reuses_code`,
      `test_create_floor_after_soft_delete_reuses_number`,
      `test_create_department_after_soft_delete_reuses_code`,
      `test_create_reception_desk_after_soft_delete_reuses_code`,
      `test_create_security_gate_after_soft_delete_reuses_code`.
- [x] 6.4 Added `test_create_company_invalid_email_rejected` — malformed
      email in `CompanyCreate`; assert 422.

## 7. Final Verification

- [x] 7.1 `ddev exec uv run ruff check` and `ddev exec uv run ruff format --check`
      clean on `src/vmss_api/org_structure/`.
- [x] 7.2 `ddev exec uv run mypy src/vmss_api/org_structure` — clean (8
      source files).
- [x] 7.3 `ddev exec uv run pytest src/vmss_api/org_structure/tests.py` —
      78 passed (70 existing + 8 new). Required dropping the persistent
      `tenant_acme_test` test schema first — `Base.metadata.create_all()`
      never alters an existing table's indexes, so the pre-existing schema
      still had the old unconditional indexes until recreated fresh from
      the updated models.
- [x] 7.4 Full `ddev exec uv run pytest` — 167 passed (159 + 8 new), zero
      regressions.
- [x] 7.5 Updated `docs/features/org_structure.md` with a new "Soft-deleted
      rows free their code/number for reuse" section.
