## 1. Shared Admin-role check

- [x] 1.1 Add `has_admin_role(user: User) -> bool` to `auth/service.py`,
      checking `user.branch_roles` for any non-revoked assignment whose
      `role.name` matches `"admin"` (case-insensitive, consistent with
      `STANDARD_ROLE_NAMES` comparisons elsewhere in this module).

## 2. Password login gate (`auth`)

- [x] 2.1 In `auth/service.py::authenticate_user`, after the existing
      password check succeeds, call `has_admin_role`; if `False`, raise a
      distinct 403 exception (not the existing `invalid_credentials` 401)
      with a message directing the caller to SSO login.
- [x] 2.2 `auth/tests.py`: add a happy-path test that an Admin account still
      logs in via `POST /auth/login` (should already pass — confirms no
      regression), and a new test that a Reception/Security/Host account
      with correct credentials is rejected with 403 from the same
      endpoint.

## 3. SSO role-mapping guard (`sso`)

- [x] 3.1 In `sso/service.py::create_role_mapping`, extend the existing
      `role.name == "visitor"` guard to also reject `role.name == "admin"`
      with the same 409 response.
- [x] 3.2 `sso/tests.py`: add `test_create_role_mapping_targeting_admin_role_conflict`,
      mirroring the existing visitor-role-mapping-rejected test.

## 4. SSO callback Admin-account gate (`sso`)

- [x] 4.1 In `sso/service.py::_provision_or_resolve_user` (or immediately
      after it returns, inside `handle_callback`, whichever keeps the
      email-resolution and role-check logic together most simply), when
      the resolved user is an **existing** account (`created is False`)
      and `has_admin_role(user)` is `True`, raise `InvalidSsoCallbackError()`
      — same generic shape as every other callback rejection.
- [x] 4.2 Before raising, write a synchronous (not `background_tasks.add_task`)
      audit log entry with action `sso_login_rejected_admin_account`,
      matching how the existing `sso_login_failed`/missing-email rejections
      in `handle_callback` are already written synchronously and why (see
      the existing comment on `BackgroundTasks` not attaching to error
      responses).
- [x] 4.3 `sso/tests.py`: add a test that an existing Admin-role account
      completing an otherwise-valid SSO callback is rejected with the
      generic callback error, and that the audit log records
      `sso_login_rejected_admin_account` rather than `sso_login`.

## 5. Documentation

- [x] 5.1 Update `docs/features/auth.md`: state that `POST /auth/login`
      is Admin-only, replacing any "any role" framing.
- [x] 5.2 Update `docs/features/sso_authentication.md`: state that SSO
      login never succeeds for an Admin account (existing or newly
      resolved), and that role mappings can't target Admin — replacing the
      current "Fallback (password) login... unaffected by SSO in every
      way" framing, which is no longer true for non-Admin accounts.

## 6. Verification

- [x] 6.1 `ddev exec uv run pytest` — full suite green, including the new
      tests from tasks 2.2, 3.2, 4.3.
- [x] 6.2 `ruff check .` and `ruff format --check .` clean.
- [x] 6.3 `mypy` clean on `core/`, `auth/`, `sso/` (project-rules.md's
      strict-typing scope — this change touches `auth/service.py` and
      `sso/service.py`, both in scope).
