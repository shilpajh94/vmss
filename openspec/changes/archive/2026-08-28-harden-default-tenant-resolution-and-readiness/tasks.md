## 1. Shared Default-Tenant Resolver

- [x] 1.1 In `core/tenancy.py`, add `DefaultTenantUnresolved` (an exception
      carrying `reason: Literal["not_found", "inactive"]`) and
      `resolve_default_tenant(db: AsyncSession) -> Tenant`, looking up
      `settings.default_tenant_slug` via `TenantRepository.get_by_slug` and
      raising `DefaultTenantUnresolved` with the correct `reason` on a
      missing or inactive row.
- [x] 1.2 Add a unit-style test in `auth/tests.py` (or a new
      `core/tests.py` if one doesn't exist) covering
      `resolve_default_tenant`'s three outcomes: resolves, not-found,
      inactive.

## 2. Wire `registrations` to the Shared Resolver

- [x] 2.1 In `registrations/deps.py::_resolve_default_device_context`,
      replace the inline `TenantRepository(db).get_by_slug(...)` +
      not-found/inactive checks with a call to
      `core.tenancy.resolve_default_tenant`, catching
      `DefaultTenantUnresolved` and calling
      `_reject_unconfigured_default("registration_default_tenant_unconfigured",
      reason=exc.reason, tenant_slug=settings.default_tenant_slug)` exactly
      as today. The default-branch lookup below it is unchanged.
- [x] 2.2 Re-run `registrations/tests.py` and `visit_info/tests.py`
      unchanged; confirm identical 401 status, message, and log event for
      every existing default-tenant/branch scenario.

## 3. Fix `identity_verification`'s Default-Tenant Logging

- [x] 3.1 In `identity_verification/deps.py::default_tenant_id`, replace
      the inline lookup with `core.tenancy.resolve_default_tenant`,
      catching `DefaultTenantUnresolved` and logging
      `identity_verification_default_tenant_unconfigured` at `ERROR` with
      `reason=exc.reason` before raising the existing 404
      `"Tenant not found or inactive"`.
- [x] 3.2 Add a test to `identity_verification/tests.py` asserting the
      `ERROR` log is emitted (with the correct `reason`) when the default
      tenant is unresolvable, and that the client-facing 404
      status/message is unchanged from today.

## 4. Fix `invitations`' Tracking-Lookup Default-Tenant Logging

- [x] 4.1 In `invitations/deps.py::track_default_tenant_db`, replace the
      inline lookup with `core.tenancy.resolve_default_tenant`, catching
      `DefaultTenantUnresolved` and logging
      `invitations_track_default_tenant_unconfigured` at `ERROR` with
      `reason=exc.reason` before raising the existing 404
      `"Tenant not found or inactive"`.
- [x] 4.2 Add a test to `invitations/tests.py` asserting the `ERROR` log is
      emitted (with the correct `reason`) when the default tenant is
      unresolvable for `GET /invitations/track`, and that the client-facing
      404 status/message is unchanged from today.

## 5. Readiness Check for Default Tenant/Branch

- [x] 5.1 In `main.py::health_ready`, after the existing DB/Redis checks,
      call `core.tenancy.resolve_default_tenant`; on
      `DefaultTenantUnresolved`, return a 503 `error_response` whose
      message distinguishes "default tenant not configured" (with the
      not-found/inactive reason) from the DB/Redis-unreachable case.
- [x] 5.2 If the default tenant resolves, open `tenant_session_scope` on
      it and call `BranchRepository(tenant_db).get_by_code(settings.
      registration_default_branch_code)`; if the result is `None` or
      inactive, return 503 distinguishing "default branch not configured".
- [x] 5.3 Add tests exercising all of: fully healthy, DB unreachable, Redis
      unreachable, default tenant unresolved, default branch unresolved -
      each asserting the distinct message/response and correct 200-vs-503
      status.

## 6. Documentation

- [x] 6.1 Add a "Provisioning the default tenant/branch" checklist entry to
      `docs/features/configuration.md` covering `TENANT_DEFAULT_SLUG` and
      `REGISTRATION_DEFAULT_BRANCH_CODE`, pointing at
      `scripts/seed_dev_data.py` for local dev and stating the readiness
      check now surfaces a mismatch before it reaches a real caller.
- [x] 6.2 Update `docs/features/identity_verification.md`'s "Tenant
      resolution" section and `docs/features/invitations.md`'s tracking
      section to describe the new `ERROR`-level logging.

## 7. Verification

- [x] 7.1 Run `ddev exec uv run pytest` for the full suite; confirm 100%
      green including every new/adjusted test from Sections 1-5.
- [x] 7.2 Run `ddev exec uv run ruff check` and
      `ddev exec uv run ruff format --check` on the full tree.
- [x] 7.3 Run `ddev exec uv run mypy` on `core/` (strict scope per
      `project-rules.md`) and any other touched module.
- [x] 7.4 Confirm no existing test's assertions changed meaning - only new
      logging/readiness behavior was added; every currently-passing
      request's client-facing response is identical to before this change.
