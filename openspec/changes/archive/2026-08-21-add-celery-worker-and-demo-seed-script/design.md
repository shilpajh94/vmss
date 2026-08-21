## Context

See proposal.md - Why for the root-cause finding. Additional facts confirmed
by reading the actual code (not assumed), which shape the script's design:

- `identity_verification/service.py` stores only an HMAC-SHA256 hash of the
  OTP code in Redis (`_hash_code`, keyed by `settings.jwt_secret_key`) —
  never the plaintext code, by design
  (`security-architecture.md` §2's "never log OTP in plaintext, not even at
  DEBUG" extends to storage too). There is no way for anything outside the
  real email/SMS the code was sent to — not the DB, not Redis, not the API
  response — to recover the raw code.
- No Mailpit/mail-catcher wiring exists anywhere in this repo's committed
  `.ddev/` config. Whatever lets the user see any email today (the "2-3
  mails") is either a host-level Mailpit instance reachable at
  `smtp_host`/`smtp_port`'s configured address, or a separate setup outside
  this repo's committed files. This change does not attempt to add or fix
  Mailpit wiring itself — only the confirmed, in-repo, root-cause gap (no
  Celery worker) is addressed.
- `scripts/seed_dev_data.py` already provisions the default dev tenant,
  its "Main Branch", the RBAC role catalog, and an admin
  (`admin@example.com` / `admin12345`) — idempotently, safe to re-run. This
  change's new script builds on top of that, rather than re-implementing
  tenant/admin bootstrap.
- `scripts/provision_registration_device.py` is the only way to create a
  walk-in device key — there is no HTTP endpoint for it (its own docstring
  says so), and the raw key it prints is unrecoverable afterward (only an
  Argon2 hash is stored). Same shape of "one non-API step" already
  documented in the two prior archived changes' seed logic.

## Goals / Non-Goals

**Goals:**
- Fix the confirmed root cause (no Celery worker in dev) so invitation
  confirmation emails actually get delivered going forward.
- Give the user a repeatable way to generate real, visible activity against
  the actually-running dev API: real emails they can see land in Mailpit,
  real rows they can browse in the dev database afterward.
- Make the script additive and safe to re-run — each run should visibly add
  more data, not silently no-op.

**Non-Goals:**
- Not adding Mailpit itself to the ddev config — out of scope; the user
  already has some way to see emails today, and this change only fixes the
  confirmed in-repo gap (the missing worker).
- Not attempting to auto-complete OTP verification in the script. Given the
  Context above, this isn't a simplification choice — it's the only
  option: the raw code is deliberately unrecoverable from anywhere the
  script can reach. The script requests OTPs (so the user sees a real email
  land) and stops there for that part of the chain; verifying by hand (via
  `/docs` or the portal) is the user's own final step if they want it,
  consistent with why the code is unrecoverable in the first place.
- Not adding a Celery Beat daemon — unrelated to the reported symptom
  (no scheduled task in this codebase is implicated), avoid scope creep.
- Not a fix to any test — the automated suite already mocks this dispatch
  deliberately (`background-jobs.md` §2's idempotency concerns aside, tests
  should stay fast/deterministic); this change doesn't touch `tests.py`
  files or `conftest.py`.

## Decisions

### Celery worker daemon: mirror the existing `vmss-api` entry exactly

Add to `.ddev/config.yaml`'s `web_extra_daemons`:
```yaml
  - name: "vmss-api-celery-worker"
    command: "uv run celery -A vmss_api.core.celery_app:celery_app worker --loglevel=info"
    directory: /var/www/html
```
The explicit `:celery_app` in `-A` is required — `core/celery_app.py`'s
instance isn't named `app`, Celery's convention-based default. No new
exposed port needed (a worker has nothing to serve over HTTP). Requires
`ddev restart` to pick up, same as the existing daemon — noted in the
README update.

### `scripts/seed_demo_workflow.py`: real HTTP against the running dev server, not direct service calls

Unlike every existing `scripts/*.py` (which call service/repository
functions directly, in-process), this script uses `httpx.Client` against
the actual base URL (`https://vmss-new-api.ddev.site:8443`, overridable via
a `--base-url` flag for a non-ddev setup) — because the entire point is to
exercise the real HTTP layer, real Celery dispatch, and real SMTP, not to
shortcut around them. It is a standalone script (`if __name__ ==
"__main__":`), not a pytest fixture/test — nothing about it runs under
`pytest`, so it has zero interaction with the `vmss_test` database or any
test fixture.

Sequence, each step's real response feeding the next (same discipline as
the two archived workflow-test changes, applied here against a real
server instead of an ASGI test transport):
1. **Prerequisite check, not re-implementation**: `POST /auth/login` as
   `admin@example.com` (the fixed credentials `seed_dev_data.py` creates).
   If this 401s/404s, exit with a clear error telling the user to run
   `ddev exec uv run python scripts/seed_dev_data.py` first — this script
   does not provision a tenant/admin itself, to avoid a second, divergent
   bootstrap path.
2. Fetch the existing "Main Branch" via `GET /branches` (created by
   `seed_dev_data.py`); if a demo-tagged company/building/floor/department/
   desk/visitor-category from a prior run doesn't already exist for this
   batch, create a fresh set tagged with a run id
   (`demo-<uuid4().hex[:8]>`) in each entity's code/name — same payload
   shapes already proven correct by
   `tests/test_workflow_staff_admin.py`.
3. Create `--invitations` (default 3) individual invitations for distinct
   fake visitors, each via `POST /invitations` with a real ID-proof file
   upload — this is what actually triggers `send_visit_confirmation.delay()`,
   now consumed by the worker from Decision 1.
4. Create `--otp-requests` (default 2) `POST /identity-verification/otp/request`
   calls with distinct fake email identifiers (per Non-Goals: request only,
   no verify).
5. **The one non-API step**: directly provision a fresh walk-in device key
   for the branch (same DB-insert `provision_registration_device.py`
   already does, reused as a local helper here — not duplicated logic,
   imported) — needed because there is no HTTP endpoint for this. Then
   `POST /registrations/walk-in` once with it, using the real raw key just
   provisioned.
6. Print a summary: every tracking id created, the admin login used, and an
   explicit reminder to check Mailpit and to restart the worker daemon if
   this is the first run since the config change.

### Idempotency: additive by design, not skip-if-exists

Every entity this script creates (branch children, invitations, OTP
identifiers, the device key) is tagged with a fresh run id, so re-running
never 409s and always visibly adds more data — directly serving "I want to
see more activity," not silently becoming a no-op like
`seed_dev_data.py`'s admin-bootstrap step correctly is for its own,
different purpose (a bootstrap step should be idempotent; a demo-data
generator should be additive).

## Findings during implementation (not anticipated above)

Verifying Decision 1 actually works (task 1.3) surfaced three further real
bugs, none visible from reading the code in isolation — only from actually
running a persistent worker against a real, previously-existing dev tenant:

1. `invitations/tasks.py`'s per-task `asyncio.run()` is incompatible with
   `core/database.py`'s process-wide, import-time-built connection pool once
   a worker handles a second task in its lifetime (`... attached to a
   different loop`). Fixed by disposing the engine at the end of each task.
2. `auth/rbac_catalog.py::seed_default_roles` never backfilled a permission
   code added after a standard role's first seed onto an *existing*
   tenant's role — this dev tenant's "admin" role couldn't create an
   invitation until fixed (union-merge backfill).
3. `scripts/seed_dev_data.py` skipped both the tenant-migration step and the
   role-catalog resync whenever the admin user already existed, so
   re-running it never actually caught a pre-existing dev tenant up to
   anything — including 8 pending Alembic migrations, one of which made
   login itself 500 (`users.avatar_url` didn't exist yet in this schema).

All three are fixed inline, confined to one function each, matching the
same "fix inline" threshold `complete-api-test-coverage` established. None
required a spec-level behavior change — see proposal.md's Capabilities.

## Risks / Trade-offs

- **[Running this against a real dev server sends real emails through
  whatever SMTP target `settings.smtp_host`/`smtp_port` point at]** →
  acceptable and intended; this is the entire point. Not safe to point at
  a real production SMTP relay — the script's docstring says so
  explicitly, matching this repo's existing dev-only script convention.
- **[The Celery worker daemon adds a second long-running process inside
  the web container]** → mirrors the existing `vmss-api` daemon's own
  resource footprint; no new container/service is introduced, so this is a
  marginal addition, not a new moving part.
- **[A user who never restarts ddev after this change won't see the fix
  take effect]** → mitigated by the README note in `proposal.md`'s What
  Changes, stating `ddev restart` is required, matching how the existing
  `vmss-api` daemon note is already phrased.
- **[Accumulating demo data in the dev DB across many runs]** → accepted;
  this is dev-only, human-inspected data, explicitly requested to
  accumulate — not a production or test-suite concern.
