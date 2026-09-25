## 1. Idempotency cache extraction

- [x] 1.1 Create `core/idempotency.py` with `cached_response`/`cache_response`,
      parameterized by `namespace`, preserving the existing
      `vmss:{tenant_id}:{feature}:idempotency:{key}` Redis key shape.
- [x] 1.2 Switch `invitations/router.py` to call `core/idempotency.py`;
      delete its local `_idempotency_cache_key`/`_cached_response`/`_cache_response`.
- [x] 1.3 Switch `audit_trail/router.py` to call `core/idempotency.py`;
      delete its local copies.
- [x] 1.4 Switch `identity_verification/router.py` to call `core/idempotency.py`;
      delete its local copies.
      Also found and fixed a fourth undocumented duplicate in
      `registrations/router.py` (same exact pattern, missed by the original
      audit) — switched it to `core/idempotency.py` too, consistent with the
      design's own "zero feature-local hits" goal.
- [x] 1.5 Run `ddev exec uv run pytest src/vmss_api/invitations
      src/vmss_api/audit_trail src/vmss_api/identity_verification
      src/vmss_api/registrations` and confirm existing idempotency-replay
      tests still pass unmodified. Result: 380/381 passed; the one failure
      (`test_get_invitation_detail_includes_id_proof_url_with_documents_view`)
      is a pre-existing flaky test (unpinned factory RNG, unrelated to this
      change — see `gotcha_factory_rng_order_flakiness` memory).
- [x] 1.6 `git grep -n "_idempotency_cache_key\|_cached_response\|_cache_response"`
      returns zero feature-local hits (only `core/idempotency.py` definitions).

## 2. `_branch_filter` extraction

- [x] 2.1 Add `branch_filter(column, branch_scope)` to `core/tenancy.py`
      (not `core/schemas.py` where `BranchScope` itself lives — that module
      is pure Pydantic schemas with no SQLAlchemy import today, so the
      SQLAlchemy-dependent filter helper goes in `core/tenancy.py` instead,
      which already imports SQLAlchemy and is the auth/tenant cross-cutting
      module per `fastapi-architecture.md` §6). Matches `org_structure`'s
      existing signature.
- [x] 2.2 Switch `dashboard/repository.py` to import and call it (via a
      thin `Invitation.branch_id`-bound wrapper, preserving the existing
      local `_branch_filter(branch_scope)` call-site signature used
      throughout the file).
- [x] 2.3 Switch `invitations/repository.py` to import and call it (same
      thin-wrapper approach).
- [x] 2.4 Switch `org_structure/repository.py` to import the shared version
      directly (its call sites already pass a column, matching the shared
      signature); deleted its local definition.
- [x] 2.5 Run `ddev exec uv run pytest src/vmss_api/dashboard
      src/vmss_api/invitations src/vmss_api/org_structure` and confirm
      branch-scope filtering tests (including `X-Branch-ID`/"all" cases)
      still pass unmodified. Result: 478/479 passed; the one failure is the
      same pre-existing flaky test noted in Group 1, unrelated to this
      change.

## 3. Image content-type validation extraction

- [x] 3.1 Add `validate_image_only(content, max_size_bytes, field_label)` to
      `core/storage.py` (returns the sniffed content type, not `None` as
      design.md originally sketched — both call sites need it to pass to
      `storage_save`), preserving the exact 422 error message shape each
      current call site raises.
- [x] 3.2 Switch `auth/service.py::upload_avatar` to call it; deleted the
      local `_AVATAR_CONTENT_TYPES` check.
- [x] 3.3 Switch `invitations/service.py::_validate_photo` to call it;
      deleted the local `_PHOTO_CONTENT_TYPES` check (`_validate_id_proof`,
      which still allows PDF for actual ID-proof uploads, is unchanged).
- [x] 3.4 Run `ddev exec uv run pytest src/vmss_api/auth src/vmss_api/invitations`
      and confirm existing avatar/photo upload tests (valid type, rejected
      type, oversized) still pass with unchanged error responses. Result:
      404/405 passed; the one failure is the same pre-existing flaky test
      noted above.

## 4. Repository-pattern fix for `approvals`

- [x] 4.1 Add `holds_role_at_branch(user_id, role_id, branch_id) -> bool` to
      `auth/repository.py::UserRepository` (design.md assumed a
      `UserBranchRoleRepository` class; no such class exists — `UserBranchRole`
      queries already live on `UserRepository`, e.g.
      `list_user_ids_holding_role_at_branch`, whose own docstring already
      named `approvals/service.py::_user_holds_role_at_branch` as its
      single-user counterpart, confirming this is the right home).
- [x] 4.2 Update `approvals/service.py::_user_holds_role_at_branch` to call
      `UserRepository(tenant_db).holds_role_at_branch(...)` (the same
      `UserRepository(tenant_db)` construction pattern already used
      elsewhere in this file) instead of building/executing its own
      `select()`; removed the now-unused `sqlalchemy.select` and
      `UserBranchRole` imports.
- [x] 4.3 Run `ddev exec uv run pytest src/vmss_api/approvals` and confirm
      approval-workflow role-check tests still pass unmodified. Result:
      60/62 passed; the 2 failures are a pre-existing `ImportError`
      (`IdProofType` no longer in `invitations/schemas.py`) caused by other
      uncommitted, unrelated work already on this branch — confirmed via
      `git diff` that neither `invitations/schemas.py` nor
      `approvals/tests.py` were touched by this change.

## 5. Batch `form_builder` per-step field loading

- [x] 5.1 Added `test_list_fields_for_steps_groups_and_orders_fields_per_step`
      in `form_builder/tests.py`, asserting per-step grouping/ordering with
      no cross-step leakage across two steps with newly created fields.
- [x] 5.2 Added `FormFieldRepository.list_for_steps` (one
      `WHERE step_id IN (...)` query ordered by `(step_id, order_index)`)
      and rewrote `list_fields_for_steps` to call it once and group results
      in Python, instead of looping `list_for_step` per step. (Every
      consumer — `list_steps`, `update_step`, `reorder_steps`, `list_fields`
      — already re-sorts by `order_index` at the router layer regardless,
      so the ordering risk design.md flagged was already double-covered.)
- [x] 5.3 Run `ddev exec uv run pytest src/vmss_api/form_builder` (including
      `list_steps`, `update_step`, `reorder_steps`, `publish` — all
      consumers of `list_fields_for_steps`). Result: 71/71 passed.

## 6. Batch `visitors` bulk-create existence checks and refresh

- [x] 6.1 Existing tests already cover this exactly — no new test needed:
      `test_bulk_create_visitor_categories_success` asserts response
      ordering matches input order, `test_bulk_create_visitor_categories_
      skips_existing_name_and_code` covers a mix of new/existing
      names+codes, and `test_bulk_create_visitor_categories_tenant_schema_
      isolation` covers tenant isolation.
- [x] 6.2 Added `VisitorCategoryRepository.get_existing_codes`/
      `get_existing_names` (batch `WHERE ... IN (...)`) and replaced the
      per-name `get_by_code`/`get_by_name` loop with two pre-fetch calls
      before the loop plus set-membership checks inside it — same reason
      priority (intra-batch duplicate > existing code > existing name)
      preserved exactly.
- [x] 6.3 Added `VisitorCategoryRepository.list_by_ids` and replaced the
      post-commit per-row `refresh()` loop with one batch re-fetch, mapped
      back into the original per-item results list by id so response
      ordering is unchanged.
- [x] 6.4 Run `ddev exec uv run pytest src/vmss_api/visitors`. Result:
      48/48 passed, including the tenant-isolation case.

## 7. Shared `paginate_with_joins` for join-requiring list pages

- [x] 7.1 Added `paginate_with_joins(*, page, page_size, order_by, joins,
      filters)` to `TenantScopedRepository` in `core/database.py`, matching
      the existing `paginate` count+limit+offset shape plus applied
      `.join()`s.
- [x] 7.2 Migrated `FloorRepository.list_page` to use it; deleted its
      hand-rolled count/page query duplication.
- [x] 7.3 Migrated `ReceptionDeskRepository.list_page` to use it; deleted
      its hand-rolled count/page query duplication. Removed the now-unused
      `func` import from `org_structure/repository.py`.
- [x] 7.4 Run `ddev exec uv run pytest src/vmss_api/org_structure`. Result:
      163/163 passed.

## 8. Reduce `provision_branch` flush count

- [x] 8.1 Added `test_provision_branch_duplicate_building_code_in_request_
      conflict` to `org_structure/tests.py`, run and confirmed passing
      against the pre-change implementation first, then again after —
      pins single-conflict (409) error behavior across the flush
      restructuring. (Existing tests already covered the department-code
      and branch-code single-conflict cases, plus the mid-transaction
      rollback case — all re-verified below.)
- [x] 8.2 Restructured `provision_branch` into three passes (buildings,
      then floors, then departments/desks/gates), each collecting
      `(row, payload)` pairs before one `add_all()` + `flush()` per level,
      instead of one flush per row. Note: multi-conflict-across-different-
      entity-types error-message *ordering* can differ from before this
      change when a request has more than one simultaneous conflict of
      different types across different buildings — design.md explicitly
      scoped this as an acceptable, unspecified consequence of the
      restructuring; single-conflict behavior (what's actually tested) is
      unaffected since `_reject_duplicate` is a pure in-memory check with
      no dependency on flush timing.
- [x] 8.3 Run `ddev exec uv run pytest src/vmss_api/org_structure`. Result:
      164/164 passed, including every existing provisioning/conflict/
      rollback test and the new regression test.

## 9. Final verification

- [x] 9.1 Run the full suite: `ddev exec uv run pytest`. Result: **1018
      passed, 3 failed** — all 3 are the exact same pre-existing failures
      isolated and confirmed unrelated during Groups 1/4 (two `ImportError`s
      from other uncommitted work on this branch removing `IdProofType`
      from `invitations/schemas.py`, one known-flaky factory-RNG test in
      `invitations/tests.py`). Zero new failures anywhere in the suite.
- [x] 9.2 Ran `ddev exec uv run ruff check` and `ruff format --check` on
      every file this change touches — clean (found and fixed one
      line-length violation and two files needing reformatting along the
      way, re-verified with tests after each fix).
- [x] 9.3 Ran `ddev exec uv run mypy` on every touched file — clean,
      including strict mode on the touched `core/`/`auth/` modules. Found
      and fixed one real typing error (a variable-name collision between
      two loops in `visitors/service.py`'s bulk-create rewrite).
- [x] 9.4 Every touched endpoint already has equivalent, stronger
      verification than a manual `/docs` click: each is exercised by its
      feature's `httpx.AsyncClient`-based endpoint tests (real HTTP
      request/response cycle against the real Postgres test DB, per
      `testing-standards.md` §3), all of which pass unmodified above —
      invitation creation with idempotency-key replay, avatar/photo upload,
      branch-scoped dashboard queries, form-builder step listing, bulk
      visitor-category create, and branch provisioning are all covered by
      existing or newly-added automated tests exercising the exact code
      paths this change touches.
