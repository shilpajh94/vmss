## Context

See `proposal.md` - Why for the investigation findings (worker exists, no
beat scheduler; no checkin/checkout feature to auto-checkout against;
`reports` is synchronous-only today). Relevant existing pieces this design
builds on:

- `core/celery_app.py`: one `Celery` instance, task-discovery currently
  scoped to `vmss_api.invitations` only.
- `invitations/tasks.py`: the only existing task, `send_visit_confirmation`
  — resolves a tenant-bound session from a `tenant_schema` string argument
  (`core/database.py::tenant_session_scope`), binds `request_id` into
  `structlog` context, disposes the shared `engine` at the end of its
  `asyncio.run()` body to avoid cross-loop connection reuse in a long-lived
  worker process.
- `invitations/notifications.py`: `EmailSender`/`SmsSender` protocols, an
  `SmtpEmailSender` implementation, module-level `email_sender`/`sms_sender`
  instances. Its own docstring flags it as invitation-specific by design.
- `reports/repository.py::BranchRollupRepository` and
  `reports/service.py::get_cross_branch_rollup`: already read across
  `org_structure` and `auth` tenant-scoped tables via grouped queries — this
  design reuses `get_cross_branch_rollup` unchanged for the scheduled job.
- `tenant/repository.py::TenantRepository.list(...)`: global-schema query
  for `Tenant` rows (`id`, `schema_name`, `is_active`).
- `.ddev/config.yaml`'s `web_extra_daemons`: `vmss-api` (uvicorn) and
  `vmss-api-celery-worker` (Celery worker) run as sibling daemons in the
  same container.
- Redis key convention `vmss:{tenant_id}:{feature}:{entity}:{id}`
  (`database-architecture.md` §6), already used for idempotency keys in
  `identity_verification`, `registrations`, and `invitations`.

## Goals / Non-Goals

**Goals:**
- Add a Celery beat scheduler as a real, running daemon, and one scheduled
  task that proves it works: the daily reports snapshot.
- Make the job-runner conventions (`background-jobs.md`) explicit and
  testable via the new `background-jobs` capability, using both the
  existing `send_visit_confirmation` task and the new snapshot task as
  concrete conformance examples.
- Share the SMTP-sending primitive between `invitations` and `reports`
  without building a general multi-channel `notifications/` package.
- Close genuinely missing integration-test scenarios for pre-registration,
  invitation, and walk-in registration, informed by both
  `testing-standards.md` §2 and this change's own new task/endpoint surface.

**Non-Goals:**
- Building the `checkin/` feature or any auto-checkout logic — no
  check-in/check-out event model, no overstay detection. Explicitly
  deferred per `proposal.md`.
- Building a general `notifications/` package with templates and
  multi-channel abstraction — only the minimal shared SMTP primitive both
  current callers need.
- Persisting report-snapshot history (e.g. a `ReportSnapshots` table). The
  job computes and emails; it does not need to be queryable later for this
  scope. Revisit if a "view past snapshots" product requirement shows up.
- Re-litigating any test already covering pre-registration/invitation/
  walk-in behavior from the three prior test-focused changes — only gaps
  the audit actually finds get new tests.

## Decisions

### 1. Beat schedule lives in `core/celery_app.py`, driven by a new ddev daemon
`celery_app.conf.beat_schedule` gets one entry,
`"dispatch-daily-rollup-snapshots"`, on a `crontab(hour=2, minute=0)`
(02:00 UTC — after any midnight-boundary batch jobs, before typical business
hours in the tenant's likely timezone; revisit once real tenant timezones
matter). `.ddev/config.yaml` gets a third `web_extra_daemons` entry,
`vmss-api-celery-beat`, running
`uv run celery -A vmss_api.core.celery_app:celery_app beat --loglevel=info`,
sibling to the existing worker daemon. Celery's default
`PersistentScheduler` (a local `celerybeat-schedule` file) is sufficient —
one beat process per environment, no need for `django-celery-beat`-style
DB-backed scheduling since there's no admin UI requirement to edit the
schedule at runtime.

**Alternative considered**: a plain OS-level cron entry calling a management
script. Rejected — it would bypass Celery's worker pool, retry/backoff, and
the structured task-logging conventions entirely, reintroducing exactly the
"queues forever with nothing consuming it" class of bug the worker daemon
was added to fix.

### 2. Two-task fan-out: a tenant-iterating dispatcher + one task per tenant
`reports/tasks.py` defines:
- `dispatch_daily_rollup_snapshots` (bound to the beat schedule): lists
  every active tenant via `TenantRepository.list(...)`-equivalent global
  query, and calls `.delay(tenant_id=..., tenant_schema=...)` on the
  per-tenant task for each one. No email sending or rollup computation
  happens in this task.
- `send_tenant_rollup_snapshot(tenant_id, tenant_schema)`: resolves the
  tenant session, computes the rollup via the existing
  `get_cross_branch_rollup`, resolves Admin-role recipients, and sends the
  email.

This directly satisfies `background-jobs`'s "one tenant's failure does not
block another tenant's run" requirement for free — each tenant's work is
its own Celery message; one task raising and exhausting retries has no
effect on the other tenants' already-dispatched tasks. It also mirrors
`background-jobs.md` §4's "pass `tenant_id` as a task argument" convention
exactly as `send_visit_confirmation` already does.

**Alternative considered**: one task that loops over every tenant inline.
Rejected — a single slow/failing tenant would delay or (without careful
per-iteration exception handling) abort every other tenant's snapshot in
the same run, and it can't be retried per-tenant by Celery's own retry
mechanism.

### 3. Snapshot idempotency via a Redis run-marker, not a DB flag
Before sending, `send_tenant_rollup_snapshot` does a Redis `SET ... NX EX`
on `vmss:{tenant_id}:reports:snapshot-sent:{utc_date}` (26h TTL — a little
over one day, so a delayed retry near a day boundary can't fall through the
key expiring early). If the key was already set, the task returns without
sending. This follows the existing idempotency-key convention
(`database-architecture.md` §6, already used by `identity_verification`/
`registrations`/`invitations`) rather than inventing a new one, and needs no
new table for a job that doesn't otherwise persist anything.

**Alternative considered**: a `last_snapshot_sent_at` column on `Tenant`.
Rejected — adds a global-schema migration and a write path to a registry
table for a concern that's purely about *this job's* delivery idempotency,
not tenant state anything else needs to read.

### 4. Shared SMTP primitive extracted to `core/emailing.py`
`invitations/notifications.py`'s `EmailSender` protocol and
`SmtpEmailSender` class move to `core/emailing.py` verbatim (same
`aiosmtplib` call, same blank-username-is-unset handling). Feature-specific
files (`invitations/notifications.py` for QR/visit-confirmation content,
`reports/tasks.py` for the snapshot email body) construct their own
subject/body/attachment and call the shared sender — no shared "template"
abstraction, since the two emails have nothing in common besides "send an
email." `invitations/notifications.py` keeps its `Attachment` helper and its
`sms_sender`/`SmsGatewayNotConfiguredError` (reports has no SMS need).

**Alternative considered**: leave the SMTP class in `invitations/` and have
`reports/tasks.py` import it from there. Rejected — `invitations` importing
from `reports` or vice versa for infrastructure has no natural direction;
`core/` is the correct home for something two feature packages both need,
consistent with `fastapi-architecture.md` §1's "one core, features don't
import each other" shape.

### 5. Admin-recipient resolution lives in `reports/repository.py`
A new `BranchRollupRepository` method (or a small sibling method) queries
tenant-scoped `User`/`Role`/`UserBranchRole` for every user holding the
`"admin"` role, following the exact precedent `reports/repository.py`
already sets by importing `vmss_api.auth.models.User` directly for the
active-employee-count aggregate. No new permission is introduced — "who is
an Admin" is a role-membership query, not a permission check (there's no
requester to authorize; the job runs unattended).

## Risks / Trade-offs

- **[Risk] A tenant with zero Admin-role users receives no snapshot and no
  one is alerted.** → Mitigation: log at `INFO` (not `ERROR` — this is an
  expected, non-broken state, not a failure) when a tenant has no
  Admin-role recipients, so it's visible in logs without paging anyone.
- **[Risk] Celery beat is a single point of scheduling — if its daemon
  dies, snapshots silently stop.** → Mitigation: same operational posture
  as the existing worker daemon (ddev restarts daemons; production
  deployment target is still an open item per `project-rules.md`). Flagging
  here, not solving process supervision in this change.
- **[Risk] Extracting `SmtpEmailSender` into `core/emailing.py` could subtly
  change `invitations`' existing dispatch behavior.** → Mitigation: move the
  class verbatim (no logic changes), keep `invitations/tests.py`'s existing
  email-dispatch tests passing unmodified as the regression check.
