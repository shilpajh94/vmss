# Background Jobs (API-17)

The Celery job-runner infrastructure this API's async work runs on, plus the
conventions every task in this codebase follows — see
`.claude/rules/background-jobs.md` for the source rules this doc's
requirements are checked against, and `openspec/specs/background-jobs/spec.md`
for the formal spec (add-background-jobs-and-integration-tests).

`background-jobs` owns no table and exposes no endpoint — it's
infrastructure (`core/celery_app.py`) plus two concrete tasks living in the
feature packages that need them (`invitations/tasks.py`,
`reports/tasks.py`).

## Worker and beat

Two daemons, both defined in `.ddev/config.yaml` alongside the `vmss-api`
uvicorn daemon:

| Daemon | Command | Job |
|---|---|---|
| `vmss-api-celery-worker` | `uv run celery -A vmss_api.core.celery_app:celery_app worker` | Executes tasks — request-triggered (`.delay()`) and scheduled alike. |
| `vmss-api-celery-beat` | `uv run celery -A vmss_api.core.celery_app:celery_app beat` | Enqueues scheduled tasks on their configured schedule. Enqueues only — never executes a task itself; the worker daemon above does that. |

Without the worker, anything dispatched via `.delay()` (request-triggered or
beat-enqueued) queues in Redis forever with nothing consuming it. Without
beat, a `beat_schedule` entry is configured but nothing ever triggers it —
see `add-celery-worker-and-demo-seed-script`'s investigation for the
request-triggered case this exact failure mode was first diagnosed from.

## Deployment requirements

The deployment target is still undecided (`project-rules.md`). Wherever it
lands, it must run:

- **Exactly one `celery beat` process per environment.** With none,
  nothing scheduled ever runs. That means no visit-lifecycle sweep (expired
  check-ins stay "inside" forever, no-shows are never archived) and no
  daily rollups. With two, every schedule fires twice. Both tasks are
  idempotent, but it is still wasted work and duplicate audit noise.
- **At least one worker consuming each queue**, including the cron queue
  the sweep is routed to and the notifications queue every email and push
  goes through.

The visit-lifecycle sweep is deliberately silent: it sends no email or
push. It also leaves `submitted` requests alone even after their date has
passed. Both were explicit product decisions
(`auto-checkout-and-archive-no-shows`), not gaps.

## Scheduled (beat-triggered) tasks

`core/celery_app.py`'s `celery_app.conf.beat_schedule` is the single place
every recurring task is registered:

| Schedule name | Cadence | Task |
|---|---|---|
| `dispatch-daily-rollup-snapshots` | Daily, 02:00 UTC | `reports.tasks.dispatch_daily_rollup_snapshots` — see `docs/features/reports.md`'s "Scheduled snapshot" section. |
| `visit-lifecycle-sweep` | Every 15 minutes | `invitations.tasks.dispatch_visit_lifecycle_sweep`. It fans out to `sweep_tenant_visit_lifecycle` per tenant, which auto-checks-out expired check-ins and archives approved no-shows. See `docs/features/invitations.md`'s "Automatic check-out and archived no-shows" section. Both tasks are routed to the cron queue by exact name, ahead of the `vmss_api.invitations.tasks.*` → notifications glob. If beat or the cron worker isn't running, nothing is swept. |

Adding a new scheduled task: register it in `beat_schedule`, add its module
to `celery_app.autodiscover_tasks([...])` if it's a new feature package, and
follow the fan-out shape below if it needs to act on every tenant.

## Fan-out shape for a tenant-iterating scheduled task

A scheduled task that needs to act on every tenant is two Celery tasks, not
one:

1. A **dispatcher** (the actual beat-scheduled task) — lists active
   tenants from the global schema and calls `.delay()` on the per-tenant
   task for each one. Touches no tenant schema, sends nothing itself.
2. A **per-tenant task** — does the real work for exactly one tenant.

This means one tenant's failure is a separate Celery message from every
other tenant's — it can't block or delay them, and Celery's own retry
mechanism applies to that one tenant's task in isolation. `reports/tasks.py`
(`dispatch_daily_rollup_snapshots` / `send_tenant_rollup_snapshot`) is the
reference implementation. `invitations/tasks.py`'s visit-lifecycle sweep
follows the same shape. It needs no Redis run-marker, because its
conditional bulk `UPDATE`s already match nothing on a redelivered run.
A single task that loops over every tenant inline does not satisfy this.

## Every task's contract

Formalized in `openspec/specs/background-jobs/spec.md`, already followed by
both `invitations/tasks.py::send_visit_confirmation` and every
`reports/tasks.py` task:

- **Idempotent body.** Check state before acting; a redelivered/retried
  execution must not repeat a side effect it already performed. A
  request-triggered task typically has nothing further to check (its
  triggering event enqueues it exactly once); a scheduled task has no such
  guarantee and needs its own guard — `reports/tasks.py` uses a Redis
  `SET NX EX` run-marker (`vmss:{tenant_id}:reports:snapshot-sent:{date}`,
  `database-architecture.md` §6's key convention) since it has no
  client-supplied idempotency key to reuse.
- **Explicit retry policy** for any task calling an external system —
  `autoretry_for`, `retry_backoff`, `max_retries`. Both task modules share
  the same `_RETRY_KWARGS` shape.
- **Retry exhaustion logs `ERROR`** with the tenant id and entity being
  acted on, so a human can find and manually reprocess it.
- **Tenant schema resolved explicitly** from a `tenant_schema` task
  argument, via `core/database.py::tenant_session_scope` — never an ambient
  default.
- **`engine.dispose()` after every task body's DB work.** `core.database.engine`
  is one process-wide `AsyncEngine`; each task body runs its own
  `asyncio.run()` call on a fresh event loop, and a pooled asyncpg
  connection checked out on a prior loop can't be reused on this one
  without erroring. Same reasoning applies to Redis — `reports/tasks.py`
  opens (and closes) a dedicated client per call rather than reusing
  `core/redis.py`'s shared module-level client, for the same reason.

## Shared email-sending primitive

`core/emailing.py` holds the SMTP-sending primitive (`EmailSender`
protocol, `SmtpEmailSender`, attachment helpers) both `invitations/tasks.py`
and `reports/tasks.py` use. It's deliberately not a general multi-channel
`notifications/` package — the two callers have nothing else in common (no
shared template, no second channel), so a plain shared sender is enough.
`invitations/notifications.py` re-exports the pieces it needs so its
existing call sites (`notifications.email_sender`,
`notifications.make_attachment`) didn't need to change; it still owns the
SMS and WhatsApp senders (the shared Fast2SMS clients in
`core/sms.py`/`core/whatsapp.py`; reports has no SMS need).

## Not yet built (flagged, not silently dropped)

- **Auto-checkout.** API-17's original scope named this alongside
  notifications and reports. There is no check-in/check-out event model in
  this codebase yet (`checkin/` — see `project-rules.md`'s directory
  structure) for a background job to act on. Deferred until that feature
  exists, per the decision recorded in
  `openspec/changes/add-background-jobs-and-integration-tests/proposal.md`.
