## Closing Summary — `complete-api-test-coverage`

## Test counts

| Point | Passed | Failed | Errors |
|---|---|---|---|
| Baseline (task 1.1, unmodified repo) | 231 | 25 | 12 |
| After the 4 bug fixes (before any new tests) | 268 | 0 | 0 |
| Final (after all 7 stages) | **296** | 0 | 0 |

Net: 65 tests fixed/added, zero regressions. `ruff check`, `ruff format --check`,
and `mypy` (on touched `core`-scoped files) are clean.

## Bugs found and fixed (design.md's "fix inline" threshold)

1. **`core/config.py` — missing storage settings (production-breaking).**
   `Settings` never declared `storage_backend`/`storage_s3_bucket`/
   `storage_s3_region`/`storage_s3_endpoint_url`/`storage_s3_presigned_url_ttl_seconds`,
   even though `core/storage.py` (and its own tests) already referenced all
   five. Every call to `storage.save()` — i.e. every file upload on
   `POST /invitations` and `POST /registrations/walk-in`, in every
   environment, not just tests — raised `AttributeError` before this fix.
   Fixed by adding the five fields (default `storage_backend = "local"`,
   preserving current behavior for every deployment that doesn't set it).
   Also brought `.env.example` and `docs/features/registrations.md` in sync
   with the real field names (`STORAGE_S3_BUCKET`/`STORAGE_S3_REGION`/
   `STORAGE_S3_ENDPOINT_URL`, replacing a prior `AWS_BUCKET`/`AWS_ENDPOINT_URL`
   naming that boto3 never actually reads on its own).
   Regression coverage: `core/tests.py`'s three storage-backend tests, plus
   every invitations/registrations test that uploads a file.

2. **`src/vmss_api/registrations/tests.py` — entire test file broken since its first commit.**
   Every one of its ~12 tests referenced a `registration_device_raw_key`
   fixture that was never defined anywhere in the repo (confirmed via
   `git log --follow -p` — absent from the initial `feat: implement API-01
   through API-14` commit). All 12 errored at fixture setup, meaning this
   feature's test suite has never actually run successfully. Fixed by adding
   the fixture (provisions a real `RegistrationDeviceKey` row, Argon2-hashed,
   for the shared `branch`/`tenant` fixtures).

3. **`invitations/notifications.py` — SMTP AUTH attempted against a no-auth mail catcher.**
   `SmtpEmailSender.send()` passed `settings.smtp_username`/`smtp_password`
   to `aiosmtplib.send()` unconditionally. When `SMTP_USERNAME`/`SMTP_PASSWORD`
   are set to an empty string (as `.env`/`.env.example` both do, for a local
   dev mail-catcher that supports no auth), `aiosmtplib` still attempts an
   AUTH login the moment the value is non-`None` — even `""` — which
   mailpit/mailhog reject, exhausting the Celery task's retries. Fixed by
   normalizing an empty string to `None` before the call. A stale comment
   in `.env.example` claimed this was already fixed in the
   `pre-commit-quality-audit` archived change; it was not — that change's
   `design.md` never mentions it. Regression coverage:
   `test_send_visit_confirmation_delivers_email_with_qr_via_mailpit`.

4. **Root `conftest.py` — `ADMIN_PERMISSION_CODES` missing `roles:view`/`roles:manage`.**
   The shared `user` fixture 403'd on all 11 role-CRUD tests in
   `auth/tests.py`. Fixed by adding both codes; a full diff of every
   permission code used across every router against this list (task 1.2)
   found no further gaps.

## Gaps closed per stage (new tests added, beyond the 4 bug fixes' regression tests)

- **Stage 1** (`platform`, `tenant`): 1 new test — documents `TenantRepository`'s
  global-schema-only, no-isolation-needed status by demonstration.
- **Stage 2** (`auth`): 6 new tests — unknown-branch on branch-role assign,
  not-found on branch-role revoke, roles list pagination + metadata, and
  not-found on get/update/delete role.
- **Stage 3** (`org_structure`): 19 new tests — a genuinely strong
  mid-transaction `/provision` rollback proof (previous rollback test only
  exercised a pre-flush validation path), plus cross-branch not-found/list
  coverage across building, floor, department, desk, and gate.
- **Stage 4** (`visitors`): 1 new test — `ApprovalWorkflowRule` update was
  the one operation across both resources with no permission-denied test
  (list/get/delete were already covered on both, contrary to the initial
  survey).
- **Stage 5** (`invitations`, `registrations`): 0 new tests — every required
  scenario (file-validation ordering, idempotency replay, rate-limit,
  not-found, device-key cases, disguised/oversized file rejection) was
  already correctly covered.
- **Stage 6** (`identity_verification`): 1 new test — Redis key-namespace
  tenant isolation. Written service-layer-only (not through the HTTP
  boundary) because `deps.py::default_tenant_id` always resolves a single
  hardcoded tenant regardless of request context — there is currently no
  way to address a second tenant from the HTTP boundary at all (see Open
  Questions below).
- **Stage 7** (`reports`): assertion coverage extended on the existing
  happy-path test — `security_gate_count` was already asserted (the initial
  survey was stale), but `totalFloors`/`totalDepartments`/
  `totalReceptionDesks`/`branchId`/`branchName` and two empty-branch zero-counts
  were not.

## Stop-and-report findings (not fixed — flagged for a follow-up)

- **`docs/features/configuration.md` documents a `MAIL_*`/`TENANT_*`-prefixed
  env var convention that `core/config.py` and the real `.env` never
  actually adopted** — the code still reads `SMTP_HOST`, `DEFAULT_TENANT_SLUG`,
  `GLOBAL_SCHEMA_NAME`, etc. (confirmed against the real `.env`, not just
  `.env.example`). This looks like the archived `standardize-environment-configuration`
  change's renaming was documented but never actually applied to `config.py`.
  This is a repo-wide naming inconsistency, not a test gap — out of scope
  here per this change's Non-Goals, but a real follow-up item since a
  deployer copying `.env.example`'s names into a real `.env` today would
  get silently-defaulted (not error-ed) wrong values for several settings.
- **`identity_verification/deps.py::default_tenant_id` hardcodes a single
  tenant** regardless of request context (already a documented, deliberate
  limitation per its own docstring, consistent with `project-rules.md`'s
  "only one tenant exists today"). Flagged again here only because it's the
  reason Stage 6's isolation test had to be service-layer-only rather than
  through the HTTP boundary — revisit once a second tenant is real.
- **`invitations:view`/`invitations:cancel`** permissions exist in the RBAC
  catalog with no endpoint using them (already flagged by the archived
  `close-api-test-coverage-gaps` change) — still true, still deferred, still
  someone else's product decision.
- A pre-existing `ruff check` import-sort violation in
  `src/vmss_api/platform/service.py` (untouched by this change, confirmed via
  `git diff` showing no modification) — flagged, not fixed, since it's
  outside this change's scope.
- A fixture-collision hazard noted by the Stage 3 audit: combining any two
  of root `conftest.py`'s `user`/`user_scoped_to_branch`/
  `user_scoped_to_other_branch` fixtures in the same test raises a
  `UniqueViolationError` on the global `permissions.code` index, because
  each branch-scoped fixture builder inserts its own fresh `PermissionFactory`
  rows. No test currently needs to combine two of them, so nothing broke,
  but a future test that does will hit this — worth a shared-fixture fix in
  a change that actually needs it.

## Docs updated

- `docs/features/registrations.md`'s storage config table, to match the
  `storage_s3_*` field names now actually implemented in `core/config.py`.
- `.env.example`, to add `STORAGE_S3_BUCKET`/`STORAGE_S3_REGION`/
  `STORAGE_S3_ENDPOINT_URL` and correct a comment that incorrectly grouped
  them with boto3's actual credential-chain env vars.
