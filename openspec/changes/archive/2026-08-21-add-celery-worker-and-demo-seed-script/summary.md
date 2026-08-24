## Closing Summary — `add-celery-worker-and-demo-seed-script`

## The original question, answered

"Only 2-3 mails in Mailpit" was not a test-coverage gap. The real cause: no
Celery worker ran in this dev environment at all, so every invitation
confirmation email (Celery-dispatched) silently queued in Redis forever,
while OTP emails (sent synchronously, inline) always got through — hence
"2-3 mails," not zero. Fixed by adding a `vmss-api-celery-worker` daemon to
`.ddev/config.yaml`, mirroring the existing `vmss-api` daemon.

Getting that fix to actually work end-to-end, and building the requested
demo/seed script on top of it, surfaced **six** real, previously-hidden bugs
— none visible from reading any one file in isolation, all found only by
actually running a persistent worker and a real HTTP client against a
real, previously-existing dev environment. All six are fixed, all confined
to one function/script each, matching `complete-api-test-coverage`'s
established "fix inline" precedent. Zero required a spec-level behavior
change.

## Bugs found and fixed

1. **`invitations/tasks.py::_send_visit_confirmation`** — `asyncio.run()`
   per Celery task against `core/database.py`'s single, process-wide
   connection pool crashes on a worker's *second* task
   (`RuntimeError: ... attached to a different loop`). Never caught before
   because no dev worker had ever run long enough to process two real
   tasks. Fixed: dispose the engine at the end of every task invocation.
2. **`auth/rbac_catalog.py::seed_default_roles`** — backfilled new
   *permissions* onto the catalog, but never backfilled a new permission
   code onto an *existing* tenant's already-seeded standard role. This dev
   tenant's "admin" role, seeded before `invitations:create` existed,
   could not create an invitation at all until fixed. Fixed as a union
   merge (adds missing catalog permissions, never removes a custom grant).
3. **`scripts/seed_dev_data.py`** — returned early (skipping both the
   tenant-migration step and the role-catalog resync) whenever the admin
   user already existed, so re-running it never actually caught a
   pre-existing dev tenant up to anything. This dev tenant was 8 tenant
   migrations behind, including the one adding `users.avatar_url` — which
   made login itself 500. Fixed: always run the migration + role-resync
   steps; only the branch/admin-user creation is gated on "does the admin
   already exist."
4. **`identity_verification/senders.py::SmtpEmailSender.send`** — the
   identical empty-string-credential-triggers-AUTH bug already fixed in
   `invitations/notifications.py` during `complete-api-test-coverage`,
   independently present in this feature's own, separate SMTP sender
   implementation (never merged, per this codebase's own documented
   Non-Goal). Same fix applied.
5. **The global Alembic tree** (`alembic/`, not `alembic_tenant/`) was
   itself one migration behind — missing `registration_device_keys`
   (added for API-13/walk-in registration). Same class of drift as #3, the
   other Alembic tree. Fixed operationally
   (`ddev exec uv run alembic upgrade head`); the README now tells the
   reader to re-run this after pulling new commits.
6. **`scripts/seed_demo_workflow.py` itself** hit the identical bug as #1
   — two separate `asyncio.run()` calls (`_resolve_tenant_id`, then
   `_provision_walk_in_device_key`) against the same process-wide engine.
   Fixed the same way, in the new script, before it ever shipped.

## What was built

- `.ddev/config.yaml`: `vmss-api-celery-worker` daemon.
- `scripts/seed_demo_workflow.py`: real-HTTP demo/data-seeding script —
  org structure + visitor-type config, 3 invitations, 2 OTP requests, 1
  walk-in registration per run, all tagged with a fresh run id so repeated
  runs are additive, not idempotent-no-ops.
- `scripts/provision_registration_device.py`: extracted a small
  `provision_device_key()` helper, reused by the new script instead of
  duplicating the logic.
- `README.md`: documents the worker daemon's `ddev restart` requirement,
  the new script, DDEV's built-in Mailpit URL, and a "re-run these two
  idempotent commands after pulling new commits" note (directly motivated
  by bugs #3/#5 above).

## Verification

- Ran the script for real against the ddev-hosted server: 3 invitations, 2
  OTP requests, 1 walk-in registration, all confirmed landing in DDEV's
  built-in Mailpit (`https://vmss-new-api.ddev.site:8026/api/v1/messages`)
  with correct subjects, recipients, and (for confirmations) the QR
  attachment.
- Full suite: **299 passed, 0 failed** — unchanged from before this change,
  confirming the Celery worker daemon and all six bug fixes introduced zero
  regressions (every test touching this dispatch already mocks it, per
  design).
- `ruff check`, `ruff format --check`, `mypy` all clean on every touched
  file.

## One correction to a pre-existing documented "fix"

`.env.example`'s comment about the SMTP-AUTH-with-empty-credentials issue
claimed it was already fixed in the archived `pre-commit-quality-audit`
change — confirmed (again, independently of `complete-api-test-coverage`'s
earlier finding) that this was never true for `identity_verification`'s own
sender. Both sender implementations are now actually fixed.
