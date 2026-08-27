## Why

Invitation confirmation emails were reported by the front-end team as "not sending"
on the development server, while working correctly on every local machine (against
Mailpit) during integration testing. Investigation traced this to a diagnosability
gap, not a functional regression: `core/emailing.py::SmtpEmailSender` (shared by
`invitations/tasks.py` and `reports/tasks.py`) has no failure logging at all around
its `aiosmtplib.send` call, so when the dev server's `MAIL_HOST`/`MAIL_PORT` differ
from a developer's local Mailpit instance (or aren't reachable there), the resulting
SMTP failure surfaces only as a bare Celery retry-exhaustion `ERROR` with no host,
port, or exception detail — there is nothing in the logs to tell a server/environment
misconfiguration apart from a code defect. This is the exact failure mode
`add-identity-verification-otp`'s dispatch path already had and
`fix-public-org-listings-and-email-diagnostics` (2026-08-24) already fixed for
`identity_verification/senders.py::SmtpEmailSender` — that fix was never carried
over to the shared sender `invitations` and `reports` use, so the same
un-diagnosable failure recurred here.

## What Changes

- `core/emailing.py::SmtpEmailSender.send` now catches `aiosmtplib.SMTPException`,
  logs a `WARNING` with the configured SMTP host/port and the underlying
  exception's type and message, then re-raises so the existing Celery
  retry/backoff/exhaustion behavior (`invitations/tasks.py`,
  `reports/tasks.py`) is unchanged — this mirrors the pattern already applied to
  `identity_verification/senders.py::SmtpEmailSender.send`.
- No change to retry counts, backoff, task signatures, or any client-facing
  response — this is a logging-only fix so a future dev-server-only failure is
  root-caused from logs in minutes instead of requiring local reproduction.
- Confirmed (not a code fix, tracked here as an explicit action item): the
  Azure DevOps `API-DEV` variable group is the actual source of `MAIL_HOST`/
  `MAIL_PORT` for the development deployment (`CI-CD/k8s.yml` /
  `CI-CD/Azure-Pipeline-API-DEV.yml`); `core/config.py`'s `MAIL_HOST=localhost`/
  `MAIL_PORT=1025` defaults intentionally target a local Mailpit instance
  (`.env.example`) and were never meant to resolve on a server, so the
  dev-server delivery failure itself is most likely that variable group not
  pointing at a real/reachable mail relay, not a coding defect. This proposal
  does not change infra configuration — flagging it so whoever owns the
  `API-DEV` variable group can verify/correct it; the logging added here is
  what confirms that diagnosis conclusively once deployed.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `invitations`: an invitation confirmation/approval email dispatch failure now
  logs the configured SMTP host/port and the underlying exception's type and
  message, not just a bare retry-exhaustion log with tenant/invitation ids.
- `reports`: a scheduled rollup snapshot email dispatch failure now logs the
  same SMTP host/port and underlying exception detail.

## Impact

- **Code**: `src/vmss_api/core/emailing.py` (`SmtpEmailSender.send`) only. No
  changes to `invitations/tasks.py`, `reports/tasks.py`, or any router/schema —
  both already propagate the exception into their existing retry/exhaustion
  logging unchanged.
- **Logs**: a new `WARNING`-level `smtp_email_dispatch_failed` log line (no
  recipient address, no PII, no credentials) precedes the existing exhaustion
  `ERROR` line when SMTP dispatch fails, matching
  `identity_verification/senders.py`'s existing log shape.
- **Tests**: `invitations/tests.py` and/or a shared `core` test gains a case
  asserting the new warning log is emitted with host/port/exception detail on
  SMTP failure, mirroring `identity_verification/tests.py`'s existing coverage
  of the same behavior on that sender.
- **No change** to client-facing responses, retry policy, or task signatures.
- **Out of scope**: correcting the actual `MAIL_HOST`/`MAIL_PORT` value in the
  `API-DEV` Azure DevOps variable group — that's an infra/ops action, not a
  code change, and isn't visible to or modifiable from this repository.
