## 1. Root-cause fix — Celery worker daemon

- [x] 1.1 Add the `vmss-api-celery-worker` entry to `.ddev/config.yaml`'s `web_extra_daemons`, per design.md's Decision 1 (exact command, `directory: /var/www/html`).
- [x] 1.2 `ddev restart`; confirm via `ddev describe` (or container logs) that the new daemon started and is running, not crash-looping.
- [x] 1.3 Manually confirm the fix: log in as `admin@example.com`, create one invitation via `POST /invitations` against the real running server, and confirm the confirmation email actually lands in Mailpit this time (previously it would not have, per proposal.md's root-cause finding).
  - Confirmed via DDEV's built-in Mailpit (`https://vmss-new-api.ddev.site:8026` — this repo has no custom Mailpit wiring; DDEV ships it by default, distinct from an unrelated stray host-level `mailpit` process on port 8025 that is not part of this project). The email landed with the correct subject, tracking ID, and QR attachment.
  - Getting there surfaced three more real, previously-hidden bugs, none anticipated in design.md — each fixed inline, same threshold as `complete-api-test-coverage`'s precedent (confined to one function, makes behavior match its already-documented/intended contract):
    1. **`invitations/tasks.py::_send_visit_confirmation`** called `asyncio.run()` per task, but `core/database.py::engine` is a single process-wide connection pool built once at import — a worker processing a *second* task on a fresh loop reused a connection bound to the first (closed) loop and crashed with `RuntimeError: ... attached to a different loop`. Never caught before because no dev worker had ever run long enough to process two real tasks. Fixed by disposing the engine at the end of every task invocation (SQLAlchemy's documented fix for switching event loops).
    2. **`auth/rbac_catalog.py::seed_default_roles`** created a standard role's permission set once, at first-seed time, and never backfilled a permission code added to `PERMISSION_CODES`/`ROLE_PERMISSIONS` afterward onto an *existing* tenant's role — confirmed directly: this dev tenant's "admin" role, seeded before `invitations:create` existed, could not create an invitation at all. Fixed as a union merge (adds a missing catalog permission, never removes a custom one).
    3. **`scripts/seed_dev_data.py`** only ran tenant Alembic migrations at first tenant creation, and returned early (skipping the role-catalog resync entirely) whenever the admin user already existed — so re-running it never actually caught a pre-existing dev tenant up to either new migrations or the fix above. The dev tenant here was 8 migrations behind (including the one adding `users.avatar_url`, which made login itself 500). Fixed by always running the tenant migration step and the role-catalog resync, gating only the branch/admin-user creation on "does the admin already exist."

## 2. `scripts/seed_demo_workflow.py` — scaffolding and prerequisite check

- [x] 2.1 Create `scripts/seed_demo_workflow.py` with the module docstring, `argparse` CLI (`--base-url`, `--invitations`, `--otp-requests`, defaults per design.md), and an `httpx.Client` (or `httpx.AsyncClient` + `asyncio.run`, matching this project's async style) pointed at `--base-url`.
- [x] 2.2 Implement the prerequisite login check (`POST /auth/login` as `admin@example.com`/`admin12345`); on failure, print a clear message pointing at `scripts/seed_dev_data.py` and exit non-zero rather than attempting to bootstrap a tenant itself.
  - Extracted `provision_device_key()` out of `scripts/provision_registration_device.py` as a small shared helper (rather than duplicating device-key creation logic), per design.md's instruction.

## 3. Org structure + visitor-type config for this run's batch

- [x] 3.1 `GET /branches`, take the existing "Main Branch". Generate this run's tag (`demo-<uuid4().hex[:8]>`).
- [x] 3.2 Create a fresh company (if `GET /company` 404s — only one company can exist, so check first, don't blindly `POST` and let it 409) → building → floor → department → reception desk → security gate, each tagged with the run id in its code/name, using the payload shapes already proven in `tests/test_workflow_staff_admin.py`.
- [x] 3.3 Create a visitor category + approval-workflow rule tagged with the run id.

## 4. Generate visible activity

- [x] 4.1 Create `--invitations` individual invitations (distinct fake visitor names/emails per invitation, real JPEG ID-proof bytes), each via `POST /invitations`; collect and print each real `trackingId`.
  - Required setting `X-Branch-ID` on the client (not anticipated in design.md) — `POST /invitations` 400s without it or an explicit `branchId` in the payload.
- [x] 4.2 Create `--otp-requests` `POST /identity-verification/otp/request` calls with distinct fake email identifiers tagged with the run id; per design.md's Non-Goals, do not attempt verify.
- [x] 4.3 Provision one fresh walk-in device key for the branch (reuse `provision_registration_device.py`'s device-key-creation logic as an imported helper, not a duplicate) and use its real raw key to call `POST /registrations/walk-in` once; print its real `trackingId`.

## 5. Summary output and docs

- [x] 5.1 Print a closing summary: every tracking id created, the run tag, the admin login used, and an explicit "check Mailpit now" / "restart ddev if you haven't since this change landed" reminder.
- [x] 5.2 Update `README.md`'s Getting Started section: add the Celery worker daemon's `ddev restart` requirement next to the existing daemon note, and add a line for running `scripts/seed_demo_workflow.py` next to the existing `seed_dev_data.py` line.
  - Also added: a "pulled new commits? re-run these two idempotent commands" note (surfaced by the migration-drift bugs found in section 1), and a note that DDEV ships a built-in Mailpit at `:8026`.

## 6. Closing gate

- [x] 6.1 Run `ruff check` and `ruff format --check` on `scripts/seed_demo_workflow.py`; fix any violation.
- [x] 6.2 Run the new script once for real against the ddev-hosted dev server; confirm it completes, prints the expected summary, and that Mailpit actually shows the new invitation-confirmation and OTP-request emails.
  - Two more real bugs surfaced and fixed inline while getting this to run clean end to end:
    1. **`identity_verification/senders.py::SmtpEmailSender.send`** had the exact same empty-string-credential-triggers-AUTH bug already fixed in `invitations/notifications.py` during `complete-api-test-coverage` — a separate, never-merged sender implementation with the identical defect. Same fix applied.
    2. The global schema (`alembic/`, not `alembic_tenant/`) was itself one migration behind (missing `registration_device_keys`, added for API-13) — same class of drift as section 1's tenant-schema finding, just the other Alembic tree. Fixed operationally (`ddev exec uv run alembic upgrade head`); the README update in task 5.2 now tells the reader to do this after pulling new commits.
  - Also hit, and fixed, the same "two `asyncio.run()` calls against one process-wide engine" bug from section 1 — this time inside the new script itself (`_resolve_tenant_id` then `_provision_walk_in_device_key`). Fixed the same way: dispose the engine at the end of the first call.
  - Final real run: 3 invitations, 2 OTP requests, 1 walk-in registration, all confirmed landing in DDEV's built-in Mailpit (`:8026`) — 21 total messages present after the debugging + final runs in this session, all with correct subjects/recipients/attachments.
- [x] 6.3 Re-run the full `ddev exec uv run pytest` suite; confirm it's still at 299 passing with zero regressions — the Celery worker daemon change must not affect test behavior, since every test that touches this dispatch already mocks it.
  - Confirmed: 299 passed, 0 failed. `ruff check`/`ruff format --check`/`mypy` all clean on every touched file.
- [x] 6.4 Write a short closing note confirming: the root cause found and fixed, the script's first real run's results (counts, any real bug found), and explicit confirmation that pytest is unaffected.
