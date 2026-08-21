## Why

API-17 ("Background job runner (Celery/RQ) for notifications, auto-checkout,
reports") and API-18 ("Integration tests for pre-registration, invitation,
and walk-in registration endpoints") are the next two items on the delivery
list. Investigation before scoping this found:

- A Celery **worker** already runs (`.ddev/config.yaml`'s
  `vmss-api-celery-worker` daemon, added in `add-celery-worker-and-demo-seed-script`),
  and `invitations/tasks.py::send_visit_confirmation` is the one task that
  exercises it end to end. There is no Celery **beat** scheduler anywhere,
  so nothing in this codebase can run on a recurring schedule today — every
  existing task is request-triggered, never time-triggered.
- **Auto-checkout has no state to act on.** `project-rules.md` itself lists
  `checkin/` ("check-in/out, badges, overstay detection") as **not yet
  built** — there is no check-in/check-out event model anywhere in
  `src/vmss_api/`, only `registrations/`'s walk-in *intake* record. A
  background job cannot auto-checkout a visitor that the system has no
  concept of checking in. Per direction from the user, this is scoped out
  of API-17 rather than silently building a checkin feature to backfill it.
- `reports/` today is a purely synchronous, on-demand endpoint
  (`GET /reports/branches/rollup`). Per direction from the user, API-17's
  "reports" background job is a genuinely new capability — a scheduled
  snapshot, not a duplicate of the existing endpoint — rather than an
  async wrapper around the same on-demand call.
- API-18's three target areas (`invitations`, `registrations`'s walk-in
  path, and `tests/test_workflow_visitor.py`'s chained journeys) already
  carry extensive permission-denied, tenant-isolation, and idempotency
  coverage from three prior test-focused changes
  (`complete-api-test-coverage`, `add-end-to-end-workflow-tests`,
  `close-api-test-coverage-gaps`). Per direction from the user, this change
  treats that as the baseline and audits for genuinely missing scenarios —
  including the new coverage the background-jobs work below itself
  requires — rather than re-writing what already exists.

## What Changes

- **Add a Celery beat scheduler** alongside the existing worker
  (`.ddev/config.yaml`'s `vmss-api-celery-beat` daemon;
  `core/celery_app.py`'s `beat_schedule` config) — the first recurring,
  time-triggered job this codebase runs.
- **Add a scheduled reports snapshot job** (`reports/tasks.py`): once daily,
  for every active tenant, compute the existing cross-branch rollup and
  email a summary to that tenant's Admin-role users. This is the second
  feature to need outbound email after `invitations`, so the shared SMTP-
  sending primitive is extracted out of `invitations/notifications.py` into
  a small `core/emailing.py` module both features call — not a new
  multi-channel `notifications/` package (no second channel/template need
  exists yet to justify that).
- **Formalize the job-runner's cross-cutting conventions as a spec** —
  idempotent task bodies, explicit retry/backoff, failure-visibility
  logging at `ERROR` on retry exhaustion, and request-id/tenant
  correlation into `structlog` — already followed ad hoc by
  `send_visit_confirmation` and now required of the new reports task too.
- **Explicitly deferred, not silently dropped**: an auto-checkout background
  job. Recorded here as blocked on a check-in/check-out feature (`checkin/`)
  that does not exist yet — building that feature is a separate, much
  larger change.
- **Audit and close integration-test gaps** for pre-registration
  (`invitations`), invitation tracking/listing, and walk-in registration
  (`registrations`), against `testing-standards.md` §2, on top of the
  existing coverage from the three prior test changes. Add coverage for
  whatever the audit finds missing, plus new tests for the reports
  snapshot task itself (permission scoping of who gets emailed, retry/
  idempotency behavior, per-tenant isolation of the beat job).

## Capabilities

### New Capabilities
- `background-jobs`: cross-cutting Celery worker+beat job-runner
  requirements (idempotent task bodies, retry/backoff, failure-visibility
  logging, request-id/tenant correlation) that any current or future
  background task must satisfy — formalizing `background-jobs.md` and
  `logging-observability.md` §1 into testable requirements, using the new
  reports snapshot task as the second implementation proving the
  conventions are generic, not `invitations`-specific.

### Modified Capabilities
- `reports`: adds a scheduled snapshot-and-notify requirement — the
  cross-branch rollup can now also run automatically on a daily schedule
  and be emailed to each tenant's admins, in addition to the existing
  on-demand endpoint (behavior addition, not a change to the existing
  endpoint's contract).

## Impact

- **Code**: `core/celery_app.py` (beat schedule registration),
  `.ddev/config.yaml` (new beat daemon), `core/emailing.py` (new, shared
  SMTP-sending primitive), `invitations/notifications.py` (refactored to
  use it, no behavior change), `reports/tasks.py` (new), `reports/service.py`
  (rollup-computation reused by the task).
- **Tests**: `reports/tests.py` (new task tests: idempotency, retry,
  per-tenant scoping, admin-recipient resolution); targeted additions to
  `invitations/tests.py`, `registrations/tests.py`, and
  `tests/test_workflow_visitor.py` wherever the audit finds a gap against
  `testing-standards.md` §2.
- **No breaking changes**: the existing `GET /reports/branches/rollup`
  endpoint's contract is unchanged; `invitations`' existing dispatch
  behavior is unchanged (implementation detail moved, not behavior).
- **Out of scope, explicitly deferred**: an auto-checkout background job
  (blocked on the not-yet-built `checkin/` feature) and a general
  multi-channel `notifications/` package (no second channel/template need
  yet).
