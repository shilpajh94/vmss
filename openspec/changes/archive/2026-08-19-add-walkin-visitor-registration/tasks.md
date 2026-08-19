## 1. `invitations` model/service changes (Decision 1)

- [x] 1.1 Add `RegistrationSource` enum (`staff_pre_registration`,
      `visitor_walk_in`) to `invitations/models.py` (or a shared location if
      `registrations` also needs it), and a `source` column on `Invitation`,
      `NOT NULL DEFAULT 'staff_pre_registration'`.
- [x] 1.2 Relax `Invitation.created_by_user_id` to nullable.
- [x] 1.3 Author the `alembic_tenant/` migration for both column changes;
      confirm it applies cleanly against an existing tenant schema with
      existing `invitations` rows (default backfills `source`, nullable
      change needs no backfill).
- [x] 1.4 Add a `source` parameter to `invitations.service.create_invitation`
      (default `staff_pre_registration`), threading it onto the created row;
      confirm the existing `POST /invitations` call site's behavior is
      unchanged (it passes no explicit `source`, i.e. relies on the default).
- [x] 1.5 Update `InvitationOut`/`InvitationTrackingOut` (or a shared
      tracking schema) to expose `source` and confirm no test asserts the
      old field set exactly (would need updating instead of just extending).

## 2. Device credential (Decision 3)

- [x] 2.1 Create `registrations/models.py::RegistrationDeviceKey`
      (`GlobalBase`): `id`, `tenant_id`, `branch_id`, `key_hash` (Argon2),
      `label`, `is_active`, `TimestampMixin`.
- [x] 2.2 Create `registrations/repository.py::RegistrationDeviceKeyRepository`
      (plain class over a `get_db`-sourced session, not
      `TenantScopedRepository` — this is a global-schema table).
- [x] 2.3 Author the `alembic/` (global-schema) migration creating
      `registration_device_keys`.
- [x] 2.4 Create `registrations/deps.py::get_registration_device` — reads
      `X-Device-Key` header, hashes and looks up an active key, resolves the
      `Tenant` (via existing `tenant/repository.py`) and `Branch` (tenant-bound
      session via `get_tenant_db`-equivalent), raises 401 on missing/invalid/
      inactive key. Binds `tenant_id`/`branch_id` into `structlog` contextvars
      (`logging-observability.md` §1-2).
- [x] 2.5 Add a `scripts/provision_registration_device.py` (or extend
      `scripts/provision_tenant.py`) to issue a device key for a branch —
      prints the raw key once, stores only the hash. This is the minimum
      needed to test the endpoint; a management UI/endpoint is out of scope.

## 3. `registrations` feature — walk-in endpoint

- [x] 3.1 Scaffold `src/vmss_api/registrations/` (`__init__.py`, `router.py`,
      `service.py`, `schemas.py`, `deps.py`, `models.py`, `repository.py`,
      `tests.py`) per `project-rules.md`'s New Features process.
- [x] 3.2 `registrations/schemas.py`: re-export/import `InvitationCreate` and
      its nested shapes from `invitations.schemas` rather than redefining
      them (spec.md "Walk-in registration accepts the same visit-record
      contract as staff pre-registration").
- [x] 3.3 `registrations/service.py::create_walk_in_registration`: thin
      wrapper calling `invitations.service.create_invitation(..., source=
      RegistrationSource.visitor_walk_in, created_by_user_id=None)`.
- [x] 3.4 `registrations/router.py`: `POST /registrations/walk-in`, multipart
      body matching `POST /invitations`'s shape (JSON `payload` Form field +
      ID-proof file parts), depends on `get_registration_device` (not
      `get_current_user`/`require_branch_permission`), rate-limited
      (`core/rate_limit.py`'s `limiter`, same posture as
      `GET /invitations/track`), supports `Idempotency-Key` (reuse the same
      Redis cache-key pattern `invitations/router.py` uses, keyed by
      resolved tenant, not a bearer-token user).
- [x] 3.5 Queue the `invitation_created`-equivalent audit log
      (`auth/audit.py::record_audit_log`) as a `BackgroundTasks` task with
      `actor_user_id=None`.
- [x] 3.6 Register the router in `api.py`
      (`api_router.include_router(registrations.router.router)`) and add its
      tag + description to `main.py`'s `_TAGS_METADATA`
      (`api-documentation.md` §2).
- [x] 3.7 Set `response_model=Envelope[...]` on the new route
      (`api-documentation.md` §1) and confirm the payload Form field's
      `description` renders both individual/group examples the same way
      `invitations/router.py`'s `_PAYLOAD_DESCRIPTION` does.

## 4. `core/storage.py` — S3 backend (Decision 4, API-14)

- [x] 4.1 Add `storage_backend: Literal["local", "s3"]` and
      `storage_s3_bucket` / `storage_s3_region` / `storage_s3_endpoint_url`
      settings to `core/config.py`; update `.env.example`.
- [x] 4.2 Add the S3-compatible client dependency via `uv add` (async
      client, e.g. `aioboto3`), `uv add --dev` any test-only S3 mocking
      dependency needed.
- [x] 4.3 Implement the `s3` branch of `save`/`url_for` in `core/storage.py`
      behind the existing two-function signature — same
      `vmss:{tenant_id}:{category}:{uuid}{ext}` key convention, `url_for`
      returns a pre-signed, time-boxed URL for `s3`.
- [x] 4.4 Confirm `validate_upload`'s content/size checks run identically
      regardless of backend (they already run before `save` is called at
      each call site — verify no call site changed that ordering).
- [x] 4.5 Handle backend-unreachable/misconfigured failure explicitly (spec.md
      "Backend unreachable or misconfigured") — surface as a clear error,
      not a silently-lost upload.

## 5. Tests (`testing-standards.md`)

- [x] 5.1 `registrations/tests.py`: happy path for individual and group
      walk-in registration (matching `Requirements/register-type-*.txt`
      fixtures), via factories per `testing-standards.md` §1.
- [x] 5.2 Device-auth-denied case (equivalent of the mandated
      permission-denied case, since this endpoint has no RBAC permission to
      test): missing key, invalid key, inactive key → 401, no row created.
- [x] 5.3 Tenant-isolation case: a device key provisioned for tenant A's
      branch cannot create or read anything in tenant B's schema, using the
      `make_tenant_schema`/`open_tenant_session` fixtures per
      `testing-standards.md` §2.
- [x] 5.4 Rate-limit test: requests beyond the configured limit get 429.
- [x] 5.5 Idempotency test: retried request with the same `Idempotency-Key`
      returns the cached response, does not create a second row.
- [x] 5.6 Regression test that `POST /invitations` (staff pre-registration)
      is fully unchanged: default `source`, existing auth, existing response
      shape.
- [x] 5.7 `core/storage.py` tests for the `s3` backend (save/retrieve
      round-trip, oversized/invalid-content rejection, unreachable-backend
      failure) — a fake client, not moto: moto's in-process response
      stubbing is incompatible with aiobotocore's async body handling
      (`TypeError: object bytes can't be used in 'await' expression`), a
      documented moto/aiobotocore gap, not a bug in this codebase.
- [x] 5.8 Extend/confirm `tests/test_api_documentation.py`'s router-discovery
      test picks up the new `registrations` router automatically.

## 6. Docs

- [x] 6.1 Add `docs/features/registrations.md` (endpoints, device-key
      provisioning/rotation, config knobs, what's explicitly deferred: OTP,
      approval-workflow evaluation, check-in).
- [x] 6.2 Update `docs/features/invitations.md`: remove walk-in from "Not yet
      built" (now covered by `registrations`), update "File uploads" to
      describe the real S3 backend instead of "swapping... is a new
      implementation" as a future item.
