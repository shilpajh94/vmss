Phases follow design D1. Each numbered section is one commit or PR group.

- **No behaviour change** applies to every section except §3 and §4: the
  same routes, request/response shapes and status codes.
- **Verify after each section:** `ddev exec uv run ruff check`, then
  `ruff format --check`, then the full `pytest` suite. Run one pytest
  process only (gotcha: concurrent runs share the test DB). Never run
  pytest alongside the QA harness.

## 0. Baseline

- [x] 0.1 Record the baseline:
  - **Recorded 2026-10-20:** 240 failed / 1457 passed (15 min). 122 are `MissingGreenlet` (T1)
    and 98 are "visitDetails.branchId is required" (T2); the remaining ~20 are T3 plus flakes.
    Ruff is clean. mypy has 13 errors: 2 in production code (fixed by 1.2/1.3) and 11 in tests.
  - the current `pytest -q` pass/fail counts and the list of failing test
    ids, saved to the scratchpad;
  - `ruff`, and `mypy src/vmss_api` (13 errors expected).
- [x] 0.2 Add a "Superseded by `audit-and-harden-api-and-web`" note to the top
  of `VMMS_WEB/openspec/changes/optimize-web-code-reuse-and-performance/proposal.md`
  (design D15).

## 1. P0 — Correctness bugs

- [x] 1.1 Add `SmsTemplate.approval_reverted`, plus its DLT and WhatsApp
  template-id settings in `core/config.py` and `.env.example` (blank by
  default) (D2).
- [x] 1.2 Fix `invitations/tasks.py:538`. Pass `sms_template`/`sms_variables`;
  when the template id is blank, send by email if an address exists, else
  skip with a WARNING. Add a test that runs the task body and asserts
  exactly one email.
- [x] 1.3 Fix `form_builder/router.py:65`. Build the `VisibilityCondition` with
  `model_validate` instead of passing a dict.
- [x] 1.4 Add `core/notifications_dedupe.py` with sent markers: `SET NX` after
  a successful send, 7-day TTL (D3).
- [x] 1.5 Apply the sent markers to every invitation notification task in
  `invitations/tasks.py` (:315 and its siblings). Add a redelivery test per
  task family.
- [x] 1.6 *(Done differently; see design D3.)* Split the multi-recipient emails into one subtask per recipient:
  `invitations/tasks.py:738-757` and `reports/tasks.py:132-139`.
- [x] 1.7 Fix `reports/tasks.py:84-140`. Set the rollup "sent" marker only
  after a successful send. Add a test: a failing first send, then a retry,
  delivers.
- [x] 1.8 Add `core/timezones.resolve_timezone` (D6). Replace
  `dashboard/service.py:39` and `invitations/service.py:136` with it. Add
  tests for IANA, `GMT+05:30`, `UTC-04:00` and garbage (WARNING logged).
- [x] 1.9 Change `invitations/service.py` `create_invitation`: resolve the
  branch, building and department before the first `storage_save`. Add a
  test: a bad branch gives 422 and no stored objects.

## 2. P4 — Make the suite green (safety net for §5–§6)

- [x] 2.1 Apply `isolate-test-storage-and-cache` (0/7) first, or confirm it is
  done. Tests must not share the dev Redis or storage.
- [x] 2.2 T1: give the `conftest.py:383` `get_tenant_db` override its own
  session per request, so `get_tenant`'s rollback stops expiring the
  objects the `client` fixture holds (about 120 `MissingGreenlet` failures).
- [x] 2.3 T2: add `visitDetails.branchId`/`buildingId` to the test payload
  builders (about 85 failures since `8ec5b06`).
- [x] 2.4 T3: fix the stale tests. Remove the `IdProofType` import and the
  dict-shaped `consents` (`approvals/tests.py:2704, 2731, 2774, 2816`); fix
  the 7 fake-object arg-type errors in `invitations/tests.py`.
- [x] 2.5 Pin the known-flaky factory fields (`checkin_code`,
  `id_proof_storage_key`, vehicle ordering) in the builders.
- [x] 2.6 *(2026-10-22: 1724 passed, 1 xfailed (G38, deliberate), 1 failed. The failure is an
  intermittent 401 in `form_builder::test_excluded_system_field_type_cannot_be_changed[...time-text]`
  that passes in isolation; it is the known full-suite teardown-race flake. Down from 240 failed.
  T1 was fixed by giving the test client's `get_db` its own session. T2 was fixed by
  `factories.with_default_location`. Several stale tests had been masked and are now updated.)* Full run is green. Record the new baseline counts; this is the gate
  for §5 and §6.

## 3. P1 — Security hardening

- [x] 3.1 Add `@limiter.limit` to `form_builder/router.py:363`,
  `core/storage_router.py:25` and `core/email_assets_router.py:26`.
- [x] 3.2 Add a route-inventory test. It walks the app routes, finds every
  route without an auth dependency, and asserts each one has a limit.
- [x] 3.3 *(Implemented as app-level `ProxyHeadersMiddleware(trusted_hosts=FORWARDED_ALLOW_IPS)`, outermost, so it works under any server. The Dockerfile CMD is unchanged, since uvicorn honours the same env var.)* Rate-limit key behind a proxy:
  - add a `FORWARDED_ALLOW_IPS` setting;
  - run uvicorn with `--proxy-headers --forwarded-allow-ips` in the
    `Dockerfile`;
  - keep `get_remote_address` (it now reads the trusted client);
  - test that two forwarded clients get separate buckets.
- [x] 3.4 *(Implemented as a `Depends(idempotency)` guard whose cleanup releases the lock even on error. The caller is the user id, the device id, `device-branch:<id>` for walk-ins, or the normalised identifier for OTP.)* Idempotency (D5). Add `core/idempotency.py`:
  - the scoped key (method, route template, caller);
  - a body hash, with a 422 when a key is reused with a different body;
  - a `SET NX` in-flight lock, with a 409 for a concurrent duplicate.
  
  Update every caller, including the shared `"invitations"` and
  `"identity-verification"` namespaces.
- [x] 3.5 Idempotency tests:
  - one key across check-in and check-out;
  - OTP verify for identifier A, then B with the same key;
  - concurrent duplicates;
  - a genuine replay.
- [x] 3.6 Multipart caps:
  - an ASGI middleware enforcing `MAX_REQUEST_BODY_BYTES` (streamed, 413
    before buffering);
  - a `MAX_UPLOAD_FILES` check in the invitation, walk-in and registration
    multipart parsers;
  - tests for an oversize body, too many parts, and a normal body.
- [x] 3.7 *(Revised before commit: enforcement is opt-in (`ENFORCE_SECRET_CHECK`, default off, which only warns), and the Dockerfile does not set `APP_ENV`. The DEV/STAGE pipelines inject `APP_ENV` through `.env`, and an image-level `ENV` would override it and switch those servers to production.)* Startup guard. Outside `local`/`testing`, refuse to start when
  `jwt_secret_key` is empty, the placeholder, or shorter than 32 characters.
  Set `ENV APP_ENV=production` in the `Dockerfile`; DDEV keeps `local`.
  Add tests.
- [x] 3.8 Add the `PUBLIC_ENDPOINT_HARDENING` setting and the
  `public_access_mode` dependency (`Deprecation` and `Link` headers in
  legacy mode) (D4).
- [x] 3.9 *(The anonymous strict-mode employee list reuses the existing `EmployeeDirectoryOut` instead of a new `PublicEmployeeOut`. Host search nulls `email`.)* Employee list and host search:
  - add the `PublicEmployeeOut` and `PublicHostSearchResultOut` schemas;
  - wire them into `auth/router.py:321` and `visit_info/router.py:39` for
    strict mode;
  - test anonymous vs permitted callers in both modes.
- [x] 3.10 Strict-mode credential checks:
  - `PATCH /api/v2/invitations/{trackingId}/check-in`
    (`invitations/router.py:1647`): an approved device key or
    `invitations:checkin` at the branch;
  - `GET /invitations/track?email=`: an OTP proof token for the same email;
  - tests in both modes.
- [x] 3.11 Kiosks (`kiosks/router.py:78,110`):
  - ignore `includeHidden` for anonymous callers in both modes;
  - require `kiosks:view` in strict mode;
  - tests.
- [x] 3.12 Log `mask_identifier(email)` in `auth/service.py:68-86` and
  `platform/service.py:242-245`.
- [x] 3.13 Replace `error_response(message=str(exc))` for pydantic
  `ValidationError` with a fixed, field-level message, at
  `invitations/router.py:1298, 2262, 2292, 2351` and
  `registrations/router.py:147`. Keep the status codes and envelope.
- [x] 3.14 Document the deprecations in `docs/features/auth.md`,
  `visit_info.md`, `invitations.md` and `kiosks.md`: what strict mode
  requires, and a target date to enable it.

## 4. P1 — Additive contract fields for the web

- [x] 4.1 *(As a separate `MeOut`/`MyBranchRoleOut`, so the shared `BranchRoleOut` used by employee responses is unchanged.)* Add `permission_codes: list[str]` to `BranchRoleOut`
  (`auth/schemas.py:40`) for `/auth/me`. Load it through the explicit
  loader from 5.3, or `selectinload` until 5.3 lands. Add tests for a
  standard role and a tenant-defined role.
- [x] 4.2 *(Steps are batch-loaded by `service.current_approval_steps` with one query per page. The constant-query-count test compares a page of 1 with a page of 4.)* Add `preferred_visit_date`, `preferred_visit_time` and
  `current_approval_step` to `InvitationListItemOut` (`invitations/schemas.py:501`).
  Load the steps with one `selectinload` per page. Add a test that the
  query count stays constant for pages of 1 and 20 items.
- [x] 4.3 Add `check_in_device`/`check_out_device` to `InvitationDetailOut`
  and call `_attach_devices` in `GET /invitations/{id}`. Add a test.
- [x] 4.4 Extend `tests/test_api_documentation.py::test_response_schemas_render_camel_case`
  to cover the new fields.

## 5. P2 — Performance (requires §2.6 green)

- [x] 5.1 *(Narrowed: only presigning moved to one cached sync botocore client (`_s3_presigner`), which was the per-row hot path. Save and load keep the per-call async client, which avoids event-loop-lifetime risk.)* Add a long-lived, per-event-loop S3 client to `core/storage.py`
  (D8), closed on app shutdown and at the end of each Celery task.
  Optionally `asyncio.gather` the per-row URL resolution in the list
  presenters.
- [x] 5.2 *(Done: 8 `.branch_roles` and 19 `.role`/`.permissions` accesses outside tests, in `auth/` (models, service, router, rbac_catalog) and `core/database.py`, and `has_permission` sits on every request path. Outcome: D7 revised.)* Grep every access to `.branch_roles`, `.role` and `.permissions`
  on `User`, `UserBranchRole` and `Role`. Record the list in the PR.
- [x] 5.3 *(Revised; see design D7. The lazy strategies stay. `core/tenancy.py::get_current_user` now uses `UserRepository.get_with_permissions`, with an explicit `selectinload` chain.)* ~~Set `lazy="raise"` on `auth/models.py:66, 95, 153`. Add the
  `UserRepository.get_with_permissions` and `list_with_branch_roles`
  loaders. Make `core/tenancy.py:160` use the repository (D7). The full
  suite and the QA API runner must both be green.~~
- [x] 5.4 Add a tenant migration for the `audit_logs` indexes
  `(entity_type, entity_id, created_at DESC)` and `(actor_user_id)`. Use a
  generated revision id and check that `alembic heads` returns one head.
- [x] 5.5 Add a tenant migration for the `pg_trgm` GIN indexes on
  `invitations.primary_contact_full_name` and `tracking_id`, with the
  skip-and-notice fallback if the extension is unavailable. The
  provisioning service creates the extension.
- [x] 5.6 *(Done 2026-10-22: `tenant_default` is at `14319832f01f` and `pg_trgm` is installed. `vmss_test` was dropped and rebuilt.)* Upgrade every tenant locally (only `tenant_default`). Drop
  `vmss_test` so the test DB picks up the indexes (gotcha: stale test-DB
  schema).
- [x] 5.7 Form-builder seeding (`form_builder/service.py:75, 93, 156, 181`):
  flush once per table tier instead of once per row.
- [x] 5.8 *(The single 409 for any duplicate is unchanged; there was never per-row attribution.)* Employee sync (`auth/service.py:438-460`): build all users and
  index rows, then flush once, with an IntegrityError fallback that keeps
  the per-row error messages. Role resync (`:381`): use a single
  `get_by_names`.
- [x] 5.9 *(Reviewed, deferred to G39. The invitation export already counts first and rejects over `INVITATION_EXPORT_MAX_ROWS` with 422, so memory is bounded. The audit report runs in Celery, off the request path. Streaming both means reworking the CSV/PDF renderers, for no current pain.)* Stream `list_for_export` (`invitations/repository.py:1213`) and
  the audit-report `list_all` (`audit_trail/repository.py:69`) with
  `yield_per`.
- [x] 5.10 Make `list_by_primary_contact_email` (`invitations/repository.py:942`)
  select only the tracking id and status.
- [x] 5.11 *(Reviewed, deferred to G40. `create_invitation` has no partial-failure cleanup today, and validation is interleaved with the saves. Concurrent uploads would leave more orphans when one save fails, and a typical request uploads only 2–3 files. 1.9 already stopped the commonest orphan case, a bad location.)* Upload the validated files concurrently in `create_invitation`
  with `anyio.create_task_group()`, keeping the existing cleanup on partial
  failure.
- [x] 5.12 *(Folded into 6.14: the 21 `asyncio.run` + `engine.dispose` copies are rewritten when the tasks go table-driven. A NullPool engine would open the same number of connections, so there is no performance gain to take separately.)* Add `core/celery_app.run_tenant_task(tenant_id, coro_fn)`: a
  NullPool worker engine plus the context bind and dispose. Use it in
  every task, replacing the 20 `asyncio.run` + `engine.dispose()` copies.
- [x] 5.13 *(Reviewed, no change: 7 constant GROUP BY queries regardless of branch count, no N+1, admin-only. The audit itself rated it low impact.)* Rebuild `reports/service.py:9-15` as a single query with per-branch
  scalar subqueries.
- [x] 5.14 *(Recorded in `docs/qa/2026-10-full-stack-qa.md` under "L1 re-run". A same-machine A/B against HEAD shows no regression. The absolute numbers are inflated by workstation load, so they aren't comparable to L1.)* Re-run the locust baseline (`scripts/qa`) and record p50 and p95
  against the QA report's L1 numbers.

## 6. P3 — Refactor and rule compliance (requires §2.6 green)

Each item is one commit; tests are unchanged unless noted.

- [x] 6.1 *(The org lookups are now `BranchRepository.is_active`, `BuildingRepository.is_active_in_branch` and `DepartmentRepository.active_ids_named`. Tasks use `_load_invitation`, which deliberately keeps `session.get`: it includes soft-deleted rows, as before. `TenantRepository.list_active()` replaced the duplicated `select(Tenant)`.)* Move these into repositories:
  - the branch, building and department lookups in
    `invitations/service.py:415-453`, to `org_structure/repository.py`;
  - the 10 `session.get(Invitation, …)` calls in `invitations/tasks.py`, to
    a repository helper;
  - the `select(Tenant)` in `invitations/tasks.py:1088` and
    `reports/tasks.py:60`, to `TenantRepository.list_active()`.
- [x] 6.2 Route `platform/router.py:20,86` through the platform service.
  Re-export `phone_digits` through the service
  (`invitations/router.py:46`).
- [x] 6.3 *(As `auth/repository.py::AuditLogWriter` (`add`, `add_system_entries`). `audit_trail`'s `AuditLogRepository` stays read-only.)* Add `AuditLogRepository.add()` and use it from
  `auth/audit.py:28` and `invitations/repository.py:733`.
- [x] 6.4 *(Done: `core.database.order_clause` (5 copies and 6 inline), `core.logging.current_request_id`, `core.celery_app.DEFAULT_RETRY_KWARGS`, `PaginationMeta.build`, `core.storage.url_for_optional`, and `core/masking.py` holding both maskers. Not done: the `sort_columns` class attribute, because the roughly 12 per-repository sort maps differ per entity and stay explicit next to their whitelists.)* Move the helpers into `core/`:
  - `order_clause` (5 copies plus 6 inline);
  - `sort_columns` on `TenantScopedRepository` (about 12 sort maps);
  - `current_request_id` (4 copies plus middleware);
  - `DEFAULT_RETRY_KWARGS` (4 copies);
  - `PaginationMeta.build`;
  - `url_for_optional`;
  - masking (`core/sms.py:60` and `identity_verification/masking.py`).
- [x] 6.5 Unify the three unique-code generators (`invitations/service.py:84-130`)
  into `_unique_code`.
- [x] 6.6 *(Reviewed, no change. `paginate` always filters `deleted_at`, but `Notification` and `AuditLog` have no such column. The others use bespoke joins and subquery counts, so none fits without widening the helper.)* Move the hand-written count and page queries to `paginate`/
  `paginate_with_joins` where the shape fits: notifications, auth ×2,
  dashboard, audit_trail, devices.
- [x] 6.7 *(`InvitationApprovalStepOut` removed. `get_by_employee_code` kept: it is a real query, and its test uses it to prove a rejected create persisted nothing. `mark_deprecated` is now used by the hardening code.)* Remove dead code: `InvitationApprovalStepOut`, and
  `get_by_employee_code` (update its single test). Keep `mark_deprecated`,
  now used by 3.8.
- [x] 6.8 *(`PlatformAuditRepository` plus the `record_platform_event` background task: `platform_login` and `tenant_provisioned`. `platform_login_failed` is written inline, because FastAPI skips background tasks when the route raises.)* Start writing `PlatformAuditEvent` for superadmin login and tenant
  provisioning (part of the audit-trail delta, alongside 6.9).
- [x] 6.9 *(12 mutations via a `_FormAudit` dependency, plus `user_avatar_updated`.)* Audit the 13 form-builder mutations (`form_builder/router.py:122-319`)
  and the avatar upload (`auth/router.py:130`) off the request path. Add
  tests.
- [x] 6.10 *(14 services. `approvals`, `platform` and `invitations` keep the runtime import, because they define models or dependencies whose annotations FastAPI or Pydantic evaluate at runtime.)* Move the `AsyncSession` imports in the 17 service modules under
  `TYPE_CHECKING`, and move any runtime use to repositories (D10).
- [x] 6.11 *(Plus a sixth module, `common.py`, for helpers several modules need; leaving them in `service.py` would have created import cycles. `export_invitations` joined the existing `export.py`. Three tests now patch the module that uses the patched name.)* Split `invitations/service.py` into `creation.py`, `checkin.py`,
  `edit.py`, `approval.py` and `export.py`, with re-exports in
  `service.py`. The move-only commit must look clean under
  `git diff --color-moved`.
- [x] 6.12 *(The form validation stays inline: one linear pass whose results feed every later phase. Storage write order is unchanged.)* Break `create_invitation` (about 1,100 lines) into
  `_validate_uploads`, `_persist_uploads`, `_build_invitation_rows`,
  `_resolve_approval` and `_post_commit_notify`.
- [x] 6.13 *(20 presenters, `_attach_devices` and `_device_diff` included. `_parse_prefixed_multipart_files` stays in the router: it parses requests.)* Move the 23 presenter helpers from `invitations/router.py` into
  `invitations/presenters.py`.
- [x] 6.14 *(`_run_task` for all 10 tasks; a `_VisitorNotice` table for tracking/denial/reschedule/edit. The other six senders differ in what they send and keep their bodies.)* Make the near-identical notification tasks in
  `invitations/tasks.py` table-driven: one render-and-dispatch helper for
  each event.
- [x] 6.15 *(12 modules plus `conftest.py` (every fixture, since the autouse ones covered the whole old module) and `helpers.py`. 562 collected before and after, with identical test names.)* Move `invitations/tests.py` (15.7k lines) into an
  `invitations/tests/` subpackage, split by area. The collected test count
  must stay the same.
- [x] 6.16 *(All 44 annotated. Ruff `ANN001`/`ANN201`/`ANN202` are enabled for production code; tests, factories and scripts are exempt. The Alembic `env.py` hooks are annotated too.)* Add the 44 missing annotations listed in the audit
  (`invitations/router.py` and `tasks.py`, `main.py`, the `deps` modules,
  `core/tenancy.py`, `core/middleware.py`). Enable ruff `ANN`, excluding
  tests.
- [x] 6.17 *(Per-module strict flags, spelled out, because mypy's `strict` shorthand is not scoped by overrides. Two real issues fixed.)* Add mypy `strict = true` overrides for `vmss_api.core.*` and
  `vmss_api.auth.*` in `pyproject.toml`, then fix what it reports.
- [x] 6.18 *(Added `DB_CONNECTION`, `DATABASE_URL`, `DB_POOL_*`, `STAFF_PORTAL_URL`, `STORAGE_PUBLIC_BASE_URL` and `PUBLIC_ENDPOINT_HARDENING`. Removed `INVITATION_TOKEN_TTL_HOURS`. The `AWS_*` keys are kept because boto reads them directly.)* Sync `.env.example`:
  - add `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`,
    `DB_POOL_RECYCLE`, `STAFF_PORTAL_URL`, `STORAGE_PUBLIC_BASE_URL` and
    the new §1 and §3 settings;
  - remove `INVITATION_TOKEN_TTL_HOURS`.
  
  Never stage `.env`.
- [x] 6.19 Fix the docstring drift at `visit_info/router.py:71`. The
  check-out permission wording in the main spec is fixed by this change's
  MODIFIED delta.
- [x] 6.20 *(`sortBy` ∈ {createdAt, readAt}, `sortOrder` default desc, so the default order is unchanged.)* Add `sortBy`/`sortOrder` whitelists to `notifications/router.py:69`
  (additive).

## 7. P4 — Test coverage gaps

- [x] 7.1 *(Added return-visit tenant isolation and an OTP-lockout isolation case for identity_verification. Registrations already had parametrised isolation coverage.)* Add tenant-isolation tests for `visitor_return_visit`, and a second
  case each for `identity_verification` and `registrations`.
- [x] 7.2 Add an endpoint test for `POST /form-builder/steps/{step_id}/groups/reorder`.
- [x] 7.3 *(Added `KioskFactory`. The form_builder in-memory rows are kept on purpose because they are never persisted. platform and tenant already used factories.)* Move `kiosks`, `form_builder`, `platform` and `tenant` tests onto the
  polyfactory factories.
- [x] 7.4 *(1772 passed and 1 xfail (G38) on the full suite, plus 812 passing in the targeted rerun of the new tests. ruff, ruff format and mypy are clean.)* Final full suite run, `ruff`, `ruff format --check` and scoped strict
  mypy all clean. The pass count must be at least the §2.6 baseline plus
  the new tests.

## 8. Docs and handoff

- [x] 8.1 Update `docs/features/*` for every new setting and field: hardening,
  body caps, idempotency, timezones, `permissionCodes`, and the list-item
  and detail fields.
- [x] 8.2 Update `docs/qa/2026-10-full-stack-qa.md` with the status of F1–F13,
  L1 and T1–T4 after this change.
- [x] 8.3 *(Given to the user on 2026-10-22, grouped by priority. No follow-up changes were created.)* Turn the gap register (design.md) into a tracked list for the
  user. Do not create the follow-up changes without being asked.
- [x] 8.4 *(Web §0.2 confirmed the fields against the local API on 2026-10-22.)* Tell the web half the API is ready. The web's §0 checks for
  `permissionCodes`, the list-item fields and the detail devices.
