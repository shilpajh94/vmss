## 1. Employee List — Filters

- [x] 1.1 Add `email: EmailStr | None` and `role: str | None` optional query
      params to `GET /auth/employees` in `auth/router.py`.
- [x] 1.2 Thread `email`/`role` through `auth/service.py::list_employees`
      into `UserRepository.list_employees_page`.
- [x] 1.3 In `auth/repository.py::list_employees_page`, add an exact-match
      condition on `User.email` when `email` is supplied.
- [x] 1.4 In the same method, add a join through `UserBranchRole`/`Role` and
      an existence-based (not row-multiplying) condition on `Role.name` when
      `role` is supplied, so a user with multiple branch-role assignments is
      not duplicated in the page or double-counted in `total`.

## 2. Employee List — Remove Bearer Token Requirement

- [x] 2.1 Replace `require_branch_scope("employees:view")` on
      `GET /auth/employees` with `org_structure/deps.py`'s
      `public_tenant_db` / `public_branch_scope` dependencies (same pattern
      already used by `GET /security-gates` et al.).
- [x] 2.2 Update `list_employees_page`'s branch-scope handling to accept the
      `BranchScope` shape produced by `public_branch_scope` ("all" or a
      frozenset of one branch id) instead of the caller's
      `authorized_branch_ids`.
- [x] 2.3 Remove the now-unused authorization/permission wiring specific to
      this route in `router.py`/`org_structure/deps.py::require_branch_scope`
      call site (leave `require_branch_scope` itself untouched — other
      endpoints still use it).
- [x] 2.4 Confirm no other endpoint or internal caller relies on
      `GET /auth/employees` being permission-gated (grep for
      `employees:view` usage before removing the check).

## 3. Employee List — Tests

- [x] 3.1 Add a test: `GET /auth/employees` with no `Authorization` header
      returns 200 and lists the default tenant's employees.
- [x] 3.2 Add a test: `GET /auth/employees` with a valid token for a
      non-default tenant lists that tenant's employees, not the default
      tenant's. (Already covered at the integration level by
      `tests/test_workflow_staff_admin.py::test_staff_admin_full_workflow`,
      which asserts a freshly-provisioned tenant's own token lists that
      tenant's employees — mirrors how `org_structure/tests.py`'s public
      listing tests rely on the same workflow test rather than duplicating
      it per-feature.)
- [x] 3.3 Add a test: `email` filter returns only the exact-match employee.
- [x] 3.4 Add a test: `role` filter returns every employee holding that role
      at any branch in scope, with no duplicates.
- [x] 3.5 Remove or rewrite any existing test asserting `GET /auth/employees`
      rejects an unauthenticated/unpermissioned caller (per
      `testing-standards.md`, keep at least one permission-denied test
      elsewhere in `auth/tests.py` for an endpoint that still requires
      permission, e.g. the single-employee-create endpoint).
- [x] 3.6 Add/keep a tenant-isolation test confirming the public listing
      still only returns the resolved tenant's own employees, never another
      tenant's, per `testing-standards.md` §2.
- [x] 3.7 **Discovered during implementation, not in the original plan**:
      add `@limiter.limit("60/minute")` to `GET /auth/employees`, matching
      the six public org-structure listing endpoints — missed in the
      original proposal/design (`security-architecture.md` §2 requires rate
      limiting on every unauthenticated endpoint). Folded into the spec
      delta and a new test.

## 4. Gate CRUD — Remove Fields

- [x] 4.1 Remove `connectivity_status` and `auth_method` columns from
      `SecurityGate` in `org_structure/models.py`.
- [x] 4.2 Remove `GateConnectivityStatus` enum and the `connectivity_status`/
      `auth_method` fields from `SecurityGateCreate`, `SecurityGateUpdate`,
      and `SecurityGateOut` in `org_structure/schemas.py`.
- [x] 4.3 Remove the enum-to-`.value` conversion for `connectivity_status` in
      `org_structure/service.py::create_security_gate` and
      `update_security_gate`.
- [x] 4.4 Remove `connectivity_status`/`high_security` field-setting
      leftovers tied specifically to the removed fields in
      `org_structure/factories.py::SecurityGateFactory` (keep
      `high_security` itself — out of scope).

## 5. Gate CRUD — Migration

- [x] 5.1 Generate a new `alembic_tenant` migration chained after head
      `a05c36d976c4`, dropping `security_gates.auth_method` and
      `security_gates.connectivity_status`, with `schema=` passed explicitly
      to both `op.drop_column` calls (per the existing
      `524da546af26_desk_gate_tri_state_status.py` migration's documented
      `schema_translate_map` landmine). Written as
      `alembic_tenant/versions/d6cca1692557_remove_gate_auth_method_and_.py`;
      `alembic ... history` confirms it chains cleanly after `a05c36d976c4`.
- [x] 5.2 Write a `downgrade()` that re-adds both columns (nullable, no
      backfill) so the migration is reversible for rollback.
- [x] 5.3 Deliberately **not** applied to the dev DB's `tenant_default`
      schema — no write access to that shared/dev environment is in scope
      for this change (user directive: local codebase only, no direct
      changes to the development server). Correctness verified without
      touching it instead:
      `alembic -c alembic_tenant.ini -x tenant_schema=tenant_default history`
      shows the new revision chaining cleanly after head `a05c36d976c4`
      (a read-only command — no DB write); the full `pytest` suite (357
      tests) exercises the equivalent column drop against the disposable,
      locally-recreated `vmss_test` database via `Base.metadata.create_all`,
      not the dev DB. Applying this migration to `tenant_default` (and
      resolving that schema's unrelated stamp mismatch at `6f2a8c1d9e4b`,
      from a different branch's SSO migration) is left to whoever owns that
      environment.

## 6. Gate CRUD — Tests

- [x] 6.1 Remove `test_create_security_gate_with_offline_connectivity` and
      `test_update_security_gate_connectivity_status` from
      `org_structure/tests.py` (they assert on fields that no longer exist).
- [x] 6.2 Confirm remaining gate CRUD tests
      (`test_create_security_gate_success`,
      `test_create_security_gate_with_building`,
      `test_create_security_gate_requires_permission`, list/get/update/
      delete tests) still pass without referencing `authMethod`/
      `connectivityStatus`.
- [x] 6.3 Add a test confirming a create/update request that still sends
      `connectivityStatus`/`authMethod` in the body succeeds and the field is
      simply absent from the response (extra-field tolerance, not a 422).

## 7. Documentation

- [x] 7.1 Update `docs/features/` entries covering the employee directory
      endpoint (auth/org-structure feature doc) and the gate CRUD endpoint to
      reflect: no-token-required listing + new filters, and the removed gate
      fields.
- [x] 7.2 Confirm `tests/test_api_documentation.py`'s response-schema/camel
      case checks still pass for the updated `EmployeeOut`/`SecurityGateOut`
      schemas. (Neither schema is parametrized in
      `test_response_schemas_render_camel_case`, and
      `test_protected_routes_declare_bearer_security` doesn't reference
      `/auth/employees` — no update needed.)

## 8. Full Verification

- [x] 8.1 `ruff check` and `ruff format --check` clean.
- [x] 8.2 `mypy` clean on `auth/` and `org_structure/` (touched, and
      `org_structure` handles PII-adjacent employee data).
- [x] 8.3 Full `pytest` suite green, including the new/updated tests above.
      (357 passed; confirmed stable across a rerun against the persistent
      `vmss_test` DB — the first run of `test_list_employees_tenant_isolation`
      used a fixed `employee_code` and collided with itself on the second
      run, fixed by randomizing it like the existing
      `test_list_branches_tenant_isolation` pattern.)
