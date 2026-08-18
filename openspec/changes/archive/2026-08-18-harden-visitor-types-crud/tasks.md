## 1. Re-Audit API-05 and API-06 (no code change)

- [x] 1.1 Confirmed full CRUD exists for `VisitorCategory` and
      `ApprovalWorkflowRule` (`visitors/router.py`/`service.py`/
      `repository.py`), tenant-wide (not branch-scoped) by design — 21
      passing tests covering happy path, permission-denial, and
      tenant-schema isolation.
- [x] 1.2 Confirmed the configurable form schema (`FormFieldDefinition`) is
      validated at the API boundary (snake_case name pattern, unique names
      within one category, max lengths) before ever reaching the JSONB
      column — `security-architecture.md` §4.
- [x] 1.3 Reproduced, in a rolled-back transaction against the real
      `vmss_test` database, that a soft-deleted `VisitorCategory`'s `code`
      still collides at the DB level on the next insert with the same code,
      even though the app-level `get_by_code` check reports it as free —
      the identical defect class fixed in `archive/2026-08-18-harden-org-structure-crud`.
      Confirmed the same pattern applies to `VisitorCategory.name` and
      `ApprovalWorkflowRule(visitor_category_id, step_order)`.
- [x] 1.4 Confirmed a `select`-type `FormFieldDefinition` can be saved with
      no/empty `options`, which no downstream form renderer could use.
- [x] 1.5 Confirmed API-06's rule-*evaluation* engine remains an explicit,
      already-documented non-goal (the not-yet-built `approvals` feature) —
      not a hidden gap in this change's scope.

## 2. Migration: Partial Unique Indexes (design.md Decision 1)

- [x] 2.1 Added `alembic_tenant/versions/2b57bd4b7d9d_visitor_types_partial_unique_indexes.py`
      (revises `880cf061a484`) that drops the existing unconditional unique
      constraints/index on `visitor_categories.name`, `visitor_categories.code`,
      and `approval_workflow_rules(visitor_category_id, step_order)`, and
      creates unique indexes scoped to `deleted_at IS NULL` in their place.
      Verified `alembic -c alembic_tenant.ini heads` resolves cleanly to
      this revision.
- [x] 2.2 `downgrade()` reverses both steps per table.

## 3. Model Changes (mirror the migration)

- [x] 3.1 `visitors/models.py`: replaced `VisitorCategory.name`/`.code`'s
      column-level `unique=True` with partial unique `Index`es in
      `__table_args__` (shared `_NOT_DELETED` module constant).
- [x] 3.2 Replaced `ApprovalWorkflowRule`'s
      `UniqueConstraint("visitor_category_id", "step_order")` with the
      equivalent partial `Index`.

## 4. Service-Layer Race Guard (design.md Decision 2)

- [x] 4.1 Added a `_commit_or_conflict` helper to `visitors/service.py`
      (mirroring `org_structure/service.py`'s) and wired it into
      `create_visitor_category`/`update_visitor_category`,
      `create_approval_workflow_rule`/`update_approval_workflow_rule`'s
      `commit()` calls. Both `delete_*` functions correctly left unwrapped
      (soft-delete, no insert).

## 5. Form Schema Validation (design.md Decision 3)

- [x] 5.1 `visitors/schemas.py`: added a `model_validator` to
      `FormFieldDefinition` rejecting `field_type == select` with `options`
      `None` or empty.

## 6. Tests

- [x] 6.1 Added `test_create_visitor_category_after_soft_delete_reuses_code`
      and `test_create_visitor_category_after_soft_delete_reuses_name`.
- [x] 6.2 Added `test_create_approval_workflow_rule_after_soft_delete_reuses_step`.
- [x] 6.3 Added `test_create_visitor_category_select_field_without_options_rejected`.

## 7. Final Verification

- [x] 7.1 `ddev exec uv run ruff check` and `ddev exec uv run ruff format --check`
      clean on `src/vmss_api/visitors/`.
- [x] 7.2 `ddev exec uv run mypy src/vmss_api/visitors` — clean (7 source
      files).
- [x] 7.3 `ddev exec uv run pytest src/vmss_api/visitors/tests.py` — 25
      passed (21 existing + 4 new). Required dropping the persistent
      `tenant_acme_test` test schema first, same as
      `harden-org-structure-crud` — `Base.metadata.create_all()` doesn't
      retrofit indexes onto an already-existing table.
- [x] 7.4 Full `ddev exec uv run pytest` — 171 passed (167 + 4 new), zero
      regressions.
- [x] 7.5 Updated `docs/features/visitors.md`: noted the partial unique
      indexes under both `VisitorCategory` and `ApprovalWorkflowRule`, and
      the `select`-field options requirement.
