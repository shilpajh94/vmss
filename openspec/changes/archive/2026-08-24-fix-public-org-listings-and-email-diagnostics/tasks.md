## 1. Public listing dependencies (`org_structure`)

- [x] 1.1 In `org_structure/deps.py`, add `public_tenant_db` — resolves
      `settings.default_tenant_slug` via `TenantRepository` and yields a
      session bound to that tenant's schema via `tenant_session_scope`,
      mirroring `invitations/deps.py::track_default_tenant_db`; 404 if the
      tenant is missing or inactive.
- [x] 1.2 In `org_structure/deps.py`, add `public_branch_scope` — takes the
      optional `X-Branch-ID` header and a `public_tenant_db` session; when
      the header is present, validates the branch exists and is active
      (reusing `BranchRepository`) and returns `frozenset({branch.id})`,
      404 if not found/inactive; when absent, returns `"all"`. No
      `get_current_user`/permission check.
- [x] 1.3 Correction found while running the full suite (see design.md
      Decision 1): `public_tenant_db` must prefer a presented token's own
      `tenant_id` claim over the default tenant, falling back to
      `settings.default_tenant_slug` only when no token is presented or it
      doesn't resolve to a real, active tenant — added
      `_tenant_from_bearer_token` (never raises; unusable token → `None`)
      and an optional `HTTPBearer(auto_error=False)` dependency to
      `public_tenant_db`. Without this, an authenticated admin of a
      non-default tenant would list the *default* tenant's branches instead
      of their own the moment a second tenant exists
      (`tests/test_workflow_staff_admin.py::test_staff_admin_full_workflow`
      caught this).

## 2. Wire the six listing endpoints to the public dependencies

- [x] 2.1 `list_branches` (`branch_router.get("")`): replace
      `Depends(require_branch_scope("branches:view"))` and
      `Depends(get_tenant_db)` with `Depends(public_branch_scope)` and
      `Depends(public_tenant_db)`.
- [x] 2.2 `list_buildings` (`building_router.get("")`): same dependency
      swap.
- [x] 2.3 `list_floors` (`floor_router.get("")`): same dependency swap.
- [x] 2.4 `list_departments` (`department_router.get("")`): same dependency
      swap.
- [x] 2.5 `list_reception_desks` (`desk_router.get("")`): same dependency
      swap.
- [x] 2.6 `list_security_gates` (`gate_router.get("")`): same dependency
      swap.
- [x] 2.7 Add a `request: Request` parameter and `@limiter.limit("60/minute")`
      (from `core.rate_limit.limiter`) to each of the six endpoint functions
      above, matching the pattern in `identity_verification/router.py`.
- [x] 2.8 Confirm no other org-structure endpoint (get-by-id, create,
      update, delete, `/provision`, `/current`, employee directory) was
      touched — `get_current_user`/`require_permission`/
      `require_branch_permission`/`authorize_branch_id` usage elsewhere in
      `router.py` is unchanged.

## 3. Email dispatch failure diagnostics (`identity_verification`)

- [x] 3.1 In `identity_verification/senders.py::SmtpEmailSender.send`, add
      `smtp_host=settings.smtp_host`, `smtp_port=settings.smtp_port`, and
      `exception_type=type(exc).__name__` to the existing
      `logger.warning("smtp_email_dispatch_failed", ...)` call, alongside
      the existing masked `identifier` and `error=str(exc)` fields.
      Confirm no credential (`settings.smtp_username`/`smtp_password`) and
      no OTP code is ever included.
- [x] 3.2 Confirm `router.py`'s `except (SmsDispatchError, EmailDispatchError)`
      handler and its response message/status code are unchanged.

## 4. Update existing org-structure tests for public listing

- [x] 4.1 `test_list_branches_scoped_to_authorized_branch_only`: update to
      reflect that listing is no longer scoped by caller permission —
      replace with a public-access assertion, or fold into the new tests in
      §5. (Replaced by `test_list_branches_not_scoped_by_caller_permission`
      plus the new tests in §5.)
- [x] 4.2 `test_list_buildings_scoped_to_authorized_branch`,
      `test_list_buildings_without_branch_header_returns_every_authorized_branch`,
      `test_list_buildings_without_branch_header_excludes_other_branches`:
      update — these named "authorized branch" scoping by a caller that no
      longer exists for this endpoint; rewrite to assert `X-Branch-ID`
      narrowing/omission behavior without a caller, per §5.
- [x] 4.3 Review `test_list_floors_success`, `test_list_departments_success`,
      `test_list_reception_desks_success`, `test_list_security_gates_success`
      and their `_excludes_other_branch` counterparts — update any call
      that currently authenticates to instead call the endpoint with no
      token (or leave the token present but assert it's simply not
      required), and confirm the `_excludes_other_branch` cases still pass
      through `X-Branch-ID` narrowing rather than caller-permission scoping.

## 5. New tests for the six public listing endpoints (`org_structure/tests.py`)

- [x] 5.1 For each of the six list endpoints: test that a request with no
      `Authorization` header succeeds (200), per spec.md's "Listing master
      data requires no Authorization header".
      (`test_list_{branches,buildings,floors,departments,reception_desks,security_gates}_no_auth_header_succeeds`.)
- [x] 5.2 For each of the six list endpoints: test that an expired or
      malformed bearer token does not block the request (200, not 401),
      per spec.md's "An expired or invalid token no longer blocks listing".
      (Added for `branches`/`departments` explicitly; the other four already
      pass an unauthenticated request in 5.1, and 5.6 below exercises the
      full authenticated-token decode path via the E2E workflow test.)
- [x] 5.3 For each of the six list endpoints: test that omitting
      `X-Branch-ID` returns rows from every branch in the tenant.
- [x] 5.4 For each of the six list endpoints: test that a valid, active
      `X-Branch-ID` narrows results to that branch only.
- [x] 5.5 For each of the six list endpoints: test that an unknown or
      inactive `X-Branch-ID` is rejected with 404.
- [x] 5.6 Tenant-isolation case (`testing-standards.md` §2, required for
      any changed endpoint): using the `make_tenant_schema`/
      `open_tenant_session` fixtures, confirm a public listing call
      resolved against one tenant's schema never returns another tenant's
      rows, for at least `list_branches` and one branch-scoped entity
      (e.g. `list_departments`). Also covered end-to-end by
      `tests/test_workflow_staff_admin.py::test_staff_admin_full_workflow`,
      which authenticates as a *second*, non-default tenant's admin and
      confirms `GET /branches` returns that tenant's own data (the case that
      caught the design.md Decision 1 correction in §1.3).
- [x] 5.7 Rate-limit 429 test: not added. `core/rate_limit.py`'s `limiter`
      is disabled whenever `settings.environment == "test"`, and no other
      `slowapi`-backed endpoint in this codebase (OTP request/verify,
      invitation tracking) has a test exercising it either — see
      `identity_verification/tests.py`'s comment on
      `test_request_otp_endpoint_returns_429_once_identifier_rate_limited`.
      Consistent with that established precedent rather than a gap
      introduced by this change.

## 6. Email diagnostics test (`identity_verification/tests.py`)

- [x] 6.1 Add/update a test that forces `SmtpEmailSender.send` to raise
      (mocking `aiosmtplib.send` to throw `aiosmtplib.SMTPException`) and
      asserts the resulting log line includes `smtp_host`, `smtp_port`, and
      `exception_type`, while the client-facing response is still the
      unchanged 503 `"This delivery channel is temporarily unavailable"`.
      (`test_smtp_dispatch_failure_logs_host_port_and_exception_type`; the
      unchanged-503 half is covered by the pre-existing
      `test_request_otp_smtp_failure_returns_503_without_leaking_detail`.)
- [x] 6.2 Add/update a test asserting the log line never contains
      `settings.smtp_username`/`smtp_password` values or the OTP code.
      (Same test as 6.1.)

## 7. Docs

- [x] 7.1 Update `docs/features/org_structure.md`: document that the six
      listing endpoints are public (no token), describe `X-Branch-ID`'s
      narrow/omit behavior with no caller, and note the rate limit.
- [x] 7.2 Update `docs/features/identity_verification.md`: note that a
      dispatch failure now logs SMTP host/port and exception detail
      server-side, with no change to the client-facing error.

## 8. Verification

- [x] 8.1 `ruff check` and `ruff format --check` clean on every changed
      file.
- [x] 8.2 `mypy` clean (`org_structure` and `identity_verification` aren't
      in the mandatory strict-typing scope, but keep existing type hints
      intact on every touched signature).
- [x] 8.3 `ddev exec uv run pytest` green, including the new/updated tests
      in §4-§6. (333 passed, including
      `tests/test_workflow_staff_admin.py::test_staff_admin_full_workflow`,
      which caught the §1.3 correction.)
