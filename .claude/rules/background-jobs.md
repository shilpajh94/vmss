---
trigger: model_decision
description: Apply when adding or modifying a Celery task — notification dispatch, scheduled report generation, data-retention purge jobs, or approval reminder nudges.
---

# Background Job Conventions — VMSS_API

`database-architecture.md` §6 says what belongs in Celery vs. inline; this covers
how a task is written so a redelivery or a crash mid-run doesn't corrupt state.

## 1. Location & Registration

- Tasks live in `src/vmss_api/<feature>/tasks.py`, added to a feature package only
  once it has actual async work — not scaffolded pre-emptively alongside
  `router.py`/`service.py`/etc. Register with the shared Celery app instance from
  `core/celery_app.py`; don't create a second `Celery()` instance anywhere.

## 2. Idempotent Task Bodies (mandatory)

- Celery's at-least-once delivery means a task can run twice for the same logical
  event (broker redelivery after a worker crash, a retry after a false-timeout).
  Every task must be safe to execute twice with the same input: check the current
  state before acting (e.g. "has this notification already been marked `sent`?")
  rather than assuming "this is the first and only run."
- Example: a notification-dispatch task checks
  `notification.status != NotificationStatus.SENT` before calling the provider API
  and updating status, inside the same transaction — not "call the provider, then
  hope the status update after it never gets skipped by a crash."

## 3. Retries

- Every task that calls an external system (email/SMS/push provider, object
  storage) declares explicit `autoretry_for`, `retry_backoff`, and `max_retries` —
  no bare task that either fails silently on a transient error or retries forever
  with no backoff and hammers a struggling downstream service.

## 4. Failure Visibility

- A task that exhausts its retries logs at `ERROR` (see `logging-observability.md`
  §3) with enough context — `tenant_id`, entity type + id, the exception —
  that someone can find and manually reprocess it. A task that fails and just
  disappears is how a pending-approval reminder silently never goes out.
- A task that needs to query the database is a tenant-scoped operation like any
  other — pass `tenant_id` as a task argument and resolve the schema
  (`core/database.py::tenant_session_scope`) at the top of the task body, the
  same way `auth/service.py`'s login flow does. Never assume a single shared
  schema is already in scope.

## 5. Don't Block the Request Path

- Enqueue with `.delay()`/`.apply_async()` from the service layer, then return.
  Never call a task function directly (`my_task(args)` instead of
  `my_task.delay(args)`) — that runs it synchronously in the request thread and
  defeats the entire point of offloading it.
