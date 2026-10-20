## Why

After `rebrand-to-guestify` (56d023a), emails sent on a local machine still show the
Visimio logo and the "Visimio" From name. The rebrand code is correct. The DDEV Celery
worker that renders and sends every email had been running since before that commit
(supervisor uptime ~6 h at 12:48 IST, 2026-10-20; commit at 12:15 IST), and nothing
restarts it when code changes. Evidence from Mailpit's latest messages (12:46 IST):

- From: `Visimio <no-reply@vmss.local>`. The current code defaults `SMTP_FROM_NAME` to `Guestify`.
- Header `<img src=".../public/email-assets/visimio-logo.png">`. The current code emits `guestify-logo.png`.

uvicorn runs with `--reload`, so the API process *does* serve the new logo bytes at both
URLs. The worker and beat daemons have no reload. The rebrand verification also missed
this, because `scripts/send_email_previews.py` renders in its own process and never goes
through the worker. This is the second bug of this kind: on 2026-10-15 a stale worker
silently dropped a newly added task as "unregistered." A manual `supervisorctl restart`
after every pull is easy to forget, and forgetting it looks exactly like a product bug.

## What Changes

- The local (DDEV) Celery **worker** and **beat** daemons restart automatically when files
  under `src/` change. This covers Python modules, email templates (`.html`/`.txt`) and
  email image assets. They no longer keep running whatever code was current when the
  container started.
- `watchfiles` becomes an explicit dev dependency. It is already in the lock file through
  `uvicorn[standard]`, and uvicorn's own `--reload` uses it.
- Docs (`README.md`, `docs/features/background-jobs.md`) describe the auto-reload and drop
  the "restart the worker after pulling" step.
- Deployed environments are **not** affected. Auto-reload is local-only.
- One-off remediation (no code): restart the worker once so the current local container
  picks up the rebrand. Emails already stored in Mailpit keep the old rendering, and a
  browser that cached `visimio-logo.png` under its `immutable` header can keep showing
  the old image for that URL until its cache is cleared. New emails use
  `guestify-logo.png`, so they are unaffected.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `background-jobs`: adds a requirement that local background workers always execute the
  code currently checked out, without a manual restart.

## Impact

- `.ddev/config.yaml`: `web_extra_daemons` commands for `vmss-api-celery-worker` and
  `vmss-api-celery-beat`.
- `pyproject.toml` / `uv.lock`: `watchfiles` added under the dev dependency group.
- `README.md`, `docs/features/background-jobs.md`: local-dev notes.
- No application code, API contract, schema, or migration changes. The rebrand code in
  `core/email_assets.py`, `core/email_rendering.py` and `core/config.py` is already correct.
