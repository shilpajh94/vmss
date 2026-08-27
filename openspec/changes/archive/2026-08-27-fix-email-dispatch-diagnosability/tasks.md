## 1. Sender Logging

- [x] 1.1 In `src/vmss_api/core/emailing.py`, import the centralized `logger`
      from `vmss_api.core.logging` and wrap the `aiosmtplib.send(...)` call in
      `SmtpEmailSender.send` with `try`/`except aiosmtplib.SMTPException`.
      **Adapted**: the checked-out branch (`bugfixing-api-tasks`) predates the
      `core/emailing.py` extraction — that module doesn't exist here yet, and
      `reports/tasks.py` doesn't exist on this branch either (no scheduled
      snapshot job). Applied the equivalent fix directly to
      `src/vmss_api/invitations/notifications.py::SmtpEmailSender.send`,
      which is where this branch's inline SMTP sender actually lives (user
      confirmed: implement against the current branch).
- [x] 1.2 In the `except` block, log a `WARNING` (`smtp_email_dispatch_failed`)
      carrying `smtp_host`, `smtp_port`, `exception_type`, and `error`
      (`str(exc)`) — no recipient address, no credentials — then re-raise
      (bare `raise`) so `invitations/tasks.py`'s existing retry/exhaustion
      handling is unaffected. (`reports/tasks.py` doesn't exist on this
      branch — see 1.1 note; that half of the spec delta doesn't apply here.)

## 2. Tests

- [x] 2.1 Add a test (in `src/vmss_api/core/` test coverage, or alongside
      `invitations/tests.py` if that's where SMTP-sender coverage already
      lives) asserting that a simulated SMTP failure from `SmtpEmailSender.send`
      emits the `smtp_email_dispatch_failed` warning with host, port, and
      exception detail, and that the original exception still propagates
      unchanged. Added
      `invitations/tests.py::test_smtp_dispatch_failure_logs_host_port_and_exception_type`,
      mirroring `identity_verification/tests.py`'s existing equivalent.
- [x] 2.2 Confirm existing `invitations/tests.py` and `reports/tests.py`
      coverage for dispatch-failure retry/exhaustion behavior still passes
      unmodified (the change adds a log line, not new control flow).
      `reports/tests.py` has no email-dispatch test on this branch (no
      `reports/tasks.py` here — see 1.1 note); verified via the full suite
      run in step 3.1.

## 3. Verification

- [x] 3.1 Run `ddev exec uv run pytest` — full suite green. 353 passed (a
      stale local `vmss_test` database from a prior session was dropped and
      recreated first — unrelated pre-existing drift, not caused by this
      change; see note below).
- [x] 3.2 Run `ddev exec uv run ruff check` and `ddev exec uv run ruff format --check`.
      Clean on both changed files.
- [x] 3.3 Run `ddev exec uv run mypy` scoped per `project-rules.md` (this
      module isn't in the mandatory strict scope, but keep it clean).
      `mypy src/vmss_api/invitations/notifications.py` — no issues.
