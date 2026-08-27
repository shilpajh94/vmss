## Context

`core/emailing.py::SmtpEmailSender.send` is the shared `aiosmtplib`-based sender
used by both `invitations/notifications.py` (re-exported as
`invitations.notifications.email_sender`) and `reports/tasks.py`'s scheduled
snapshot job. It has no `try`/`except` around the `aiosmtplib.send` call — an SMTP
failure propagates as a bare `aiosmtplib.SMTPException` (or a connection-level
`OSError` for a host that refuses the connection) straight to the caller's Celery
task, whose only failure logging is a generic exhaustion `ERROR` after retries run
out (`invitations/tasks.py`, `reports/tasks.py`), carrying tenant/invitation ids
but no SMTP host, port, or exception detail.

`identity_verification/senders.py::SmtpEmailSender.send` already solves exactly
this for the OTP-email path (added in `fix-public-org-listings-and-email-
diagnostics`, 2026-08-24): it catches `aiosmtplib.SMTPException`, logs a
`WARNING` with `smtp_host`, `smtp_port`, `exception_type`, and `error`, then
raises a dedicated `EmailDispatchError`. See proposal.md for why this same gap
in the shared sender is what turned this incident into "reproduce locally to find
out" instead of "read the dev-server log."

## Goals / Non-Goals

**Goals:**
- Give `core/emailing.py::SmtpEmailSender.send` the same failure-context logging
  `identity_verification/senders.py::SmtpEmailSender.send` already has, so a
  dev-server-only SMTP failure is diagnosable from logs alone for the
  `invitations`/`reports` dispatch paths too.

**Non-Goals:**
- Merging `core/emailing.py` and `identity_verification/senders.py` into one
  shared sender abstraction. They already diverged deliberately (see
  `identity_verification/senders.py`'s module docstring); this change keeps
  that boundary and duplicates the logging pattern rather than adding a new
  cross-feature dependency.
- Changing retry policy, backoff, or task signatures in `invitations/tasks.py`
  or `reports/tasks.py` — both already handle the exception their sender
  raises today; only the exception's logged context changes.
- Correcting the `API-DEV` Azure DevOps variable group's `MAIL_HOST`/
  `MAIL_PORT` value — that's an infra action tracked in proposal.md, not
  something this repo's code can fix.

## Decisions

- **Catch `aiosmtplib.SMTPException` only, not bare `Exception`.** Matches
  `identity_verification/senders.py`'s existing precedent and
  `background-jobs.md` §2/§3's expectation that a task's `except Exception`
  (already present one level up in `invitations/tasks.py`/`reports/tasks.py`)
  remains the catch-all for retry purposes — this addition only adds logging
  context on the specific SMTP failure path, it doesn't change what gets
  retried. A connection-level `OSError` (e.g. DNS failure, connection refused)
  is not an `aiosmtplib.SMTPException` subclass; `aiosmtplib.send` wraps
  transport-level failures into its own exception hierarchy
  (`aiosmtplib.SMTPConnectError`, etc.), which is what's actually raised for a
  dev-server "nothing listening on `MAIL_HOST:MAIL_PORT`" failure, so this
  catch clause covers the incident's actual failure mode.
- **Log, then re-raise the same exception type callers already handle** —
  don't introduce a new `EmailDispatchError` type in `core/emailing.py`, unlike
  `identity_verification/senders.py`. That module's callers distinguish
  `EmailDispatchError` from `GatewayNotConfiguredError` for idempotency-key
  caching purposes (design.md of `add-identity-verification-otp`); `invitations`
  and `reports` have no equivalent distinction — both currently rely on a bare
  `except Exception` at the Celery task level — so introducing a new exception
  type here would be an unused abstraction. `raise` (bare, inside the `except`
  block) preserves the original type and traceback.
- **Omit the recipient address from the new log line.** Neither
  `invitations/tasks.py` nor `reports/tasks.py` logs a raw recipient today
  (they log `tenant_schema`/`invitation_id`/`tenant_id` instead, per
  `logging-observability.md` §2's PII caution); the new `WARNING` follows that
  existing pattern rather than importing `identity_verification/masking.py`'s
  `mask_identifier` across a feature boundary for a one-line log call. The
  tenant/invitation/tenant-id context the surrounding task already binds via
  `structlog.contextvars` is enough to locate the affected record.

## Risks / Trade-offs

- [A non-`SMTPException` failure (e.g. a raw `TimeoutError` from the underlying
  transport) still bypasses the new logging and falls straight through to the
  task's generic exhaustion log, same as today] → Acceptable: this mirrors
  `identity_verification/senders.py`'s existing scope exactly, and the
  dev-server incident's actual failure (connection refused/timeout against an
  unreachable `MAIL_HOST:MAIL_PORT`) is raised by `aiosmtplib` as a subclass of
  `SMTPException` (`SMTPConnectError`), so it's covered.

## Migration Plan

Logging-only change, no data migration. Deploy normally; no rollback
considerations beyond a standard revert.
