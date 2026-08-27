## 1. Diagnostics in `registrations/deps.py`

- [x] 1.1 Add a `reason: Literal["not_found", "inactive"]` parameter to
      `_reject_unconfigured_default`, included as a structured field on the
      `ERROR` log call.
- [x] 1.2 In `_resolve_default_device_context`, split the default-tenant
      check (`tenant is None or not tenant.is_active`) into two branches so
      each calls `_reject_unconfigured_default` with the correct `reason`.
- [x] 1.3 Do the same split for the default-branch check
      (`branch is None or not branch.is_active`).
- [x] 1.4 Confirm the 401 response body/detail text is unchanged for both
      cases (diagnostics are log-only, per design.md).

## 2. Tests

- [x] 2.1 Extend
      `test_walk_in_registration_missing_device_key_no_default_tenant_rejected`
      (or add a sibling case) to assert `reason="not_found"` on the
      `registration_default_tenant_unconfigured` log entry.
- [x] 2.2 Add a case for an existing-but-inactive default tenant asserting
      `reason="inactive"` on the same event.
- [x] 2.3 Extend
      `test_walk_in_registration_missing_device_key_no_default_branch_rejected`
      to assert `reason="not_found"` on the
      `registration_default_branch_unconfigured` log entry.
- [x] 2.4 Add a case for an existing-but-inactive default branch asserting
      `reason="inactive"` on the same event.
- [x] 2.5 Assert the 401 response body is byte-for-byte unchanged across all
      four cases (regression guard for design.md's "no client-facing change").

## 3. Validation

- [x] 3.1 `ruff check` / `ruff format --check` on `registrations/deps.py`
      and `registrations/tests.py`.
- [x] 3.2 `ddev exec uv run pytest src/vmss_api/registrations/tests.py`.
- [x] 3.3 `openspec validate clarify-walkin-registration-config-errors --strict`.
