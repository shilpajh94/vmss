## Why

The user reported checking Mailpit after exercising the API and seeing only
2-3 emails, and asked whether test scenarios were missed and for a way to
see real, browsable data land in the database. Investigation found the
actual cause is **not** a test-coverage gap: `.ddev/config.yaml` runs only
one daemon — the FastAPI app itself (`web_extra_daemons: vmss-api`). There
is no Celery worker daemon anywhere in this repo's dev environment.
`invitations/service.py::create_invitation` dispatches its confirmation
email via `tasks.send_visit_confirmation.delay(...)` (Celery,
`background-jobs.md` §5) — with no worker process ever consuming that
queue, every one of those emails silently sits in Redis and is never sent.
`identity_verification/service.py`'s OTP dispatch, by contrast, calls
`await senders.email_sender.send(...)` **inline**, synchronously — it
always fires. That difference exactly explains "2-3 mails": those are the
synchronous OTP sends; the queued invitation-confirmation emails never had
a consumer. This is a real, confirmed dev-environment gap, and it also
means nothing has ever manually verified this specific email path end to
end in this environment, separate from the two already-archived test
changes (`complete-api-test-coverage`, `add-end-to-end-workflow-tests`),
which mock or stub this exact dispatch in every test and therefore never
exercise the real worker/broker/SMTP path at all.

The user also separately asked for a way to generate real, visible activity
against the running dev API — real emails landing in Mailpit, real rows
landing in the dev database they can browse — as their own way of confirming
the workflows actually work, distinct from and in addition to the automated
test suite.

## What Changes

- **Add a Celery worker daemon to `.ddev/config.yaml`**, mirroring the
  existing `vmss-api` uvicorn daemon's pattern (`web_extra_daemons`, same
  `directory: /var/www/html`), running
  `uv run celery -A vmss_api.core.celery_app:celery_app worker --loglevel=info`
  (the explicit `:celery_app` is required — that module's Celery instance
  isn't named `app`, Celery's own convention-based default). This
  is the root-cause fix: once a worker is actually running, every
  Celery-dispatched task this API defines today (currently just
  `send_visit_confirmation`) actually executes instead of queuing forever.
- **Add `scripts/seed_demo_workflow.py`**, a new dev-only script that
  drives the *actually running* dev API over real HTTP (not direct
  service-layer calls, unlike the existing `seed_dev_data.py`/
  `provision_registration_device.py` scripts) — logging in as the
  already-seeded dev admin, then creating a batch of realistic org
  structure, visitor categories, multiple invitations (each triggering a
  real confirmation email, now actually delivered once the worker fix
  above lands), and multiple OTP request/verify cycles. Every run leaves
  its data in the dev database (no rollback, no cleanup) and is safe to
  run repeatedly — each run adds a fresh, uniquely-tagged batch rather than
  silently no-op'ing on a second run.
- **Re-verify the full automated `pytest` suite** as this change's closing
  gate, confirming the 299-passing state from the last two archived
  changes hasn't regressed — directly answering the "make sure all test
  cases pass properly" half of the request. This is verification, not new
  test-writing: the per-endpoint and chained-workflow scenarios were
  already built and audited by `complete-api-test-coverage` and
  `add-end-to-end-workflow-tests`.
- Document the new script and the worker-daemon prerequisite in
  `README.md`'s "Getting Started" section, next to the existing
  `seed_dev_data.py` line.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — this changes dev-environment tooling/infrastructure (a ddev daemon
definition, a new standalone script, a README note) and re-verifies
existing behavior; it does not change any API endpoint's request/response
contract or status codes. This change sets `skip_specs: true` in
`.openspec.yaml` accordingly.

## Impact

- **Affected config**: `.ddev/config.yaml` (new `web_extra_daemons` entry).
- **New file**: `scripts/seed_demo_workflow.py`.
- **Affected docs**: `README.md`'s Getting Started section.
- **No changes to any feature's `router.py`/`service.py`/`repository.py`/
  `tests.py`, no schema/migration changes, no dependency changes.**
- **No breaking changes.** Existing tests never depend on a real Celery
  worker (every test that touches this dispatch monkeypatches `.delay()`
  or the sender directly), so adding a worker daemon changes only the
  *dev* environment's runtime behavior, not test behavior.
