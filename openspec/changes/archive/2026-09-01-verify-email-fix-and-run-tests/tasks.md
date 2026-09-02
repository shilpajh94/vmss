## 1. Commit the Pending Diagnosability Fix

- [x] 1.1 Review `git status`/`git diff` on `bugfixing-api-tasks` and confirm
      only `fix-email-dispatch-diagnosability`'s three files are staged:
      `src/vmss_api/invitations/notifications.py`,
      `src/vmss_api/invitations/tests.py`,
      `openspec/specs/invitations/spec.md` — plus the archived change folder
      `openspec/changes/archive/2026-08-27-fix-email-dispatch-diagnosability/`.
      Do NOT stage the unrelated untracked files already sitting in the
      working tree (`Requirements/`, `SSO_Login_Requirement_Simple (1).docx`,
      `visit-info-lookup-api-spec.md`) — out of scope for this change.
      Confirmed exactly those files staged, nothing else.
- [x] 1.2 Commit with a Conventional Commits message
      (`git-workflow.md` §1), e.g. `fix: log SMTP host/port and exception
      detail on invitation email dispatch failure`. Committed as `dcac61a`
      on `bugfixing-api-tasks` (done as part of applying
      `diagnose-otp-email-delivery-failure`, which needed this committed
      before its own branch-merge step). Not pushed to `origin` — this
      environment has no network route/credentials to
      `devops.pitsolutions.com` (`git fetch`/`push` fail with "No such
      device or address"), confirmed both here and in
      `diagnose-otp-email-delivery-failure`.

## 2. Re-Verify the Test Suite

- [x] 2.1 Run `ddev exec uv run pytest` fresh, post-commit, as the
      attributable "ran the test cases for all APIs" result the user asked
      for (not a reuse of the proposal-time run). 353 passed, 0 failed.
- [x] 2.2 Run `ddev exec uv run ruff check` and `ddev exec uv run ruff
      format --check` on the full tree. Both clean (`All checks passed!`,
      279 files already formatted).
- [x] 2.3 If any test or lint failure surfaces, diagnose its root cause and
      fix it, then re-run until green. Record what was found and fixed (or
      confirm nothing was found) in this task's notes at apply time.
      Nothing found — full suite (353), ruff check, and ruff format --check
      were all already green; no fixes needed.

## 3. Document the Live-Environment Verification Gap

- [x] 3.1 Note explicitly (in the apply summary, not a code change) that
      confirming the server team's dev-environment `MAIL_HOST`/`MAIL_PORT`
      fix actually resolved delivery requires either sending a real
      invitation against the dev environment or reading its application
      logs for the absence of a new `smtp_email_dispatch_failed` warning
      once this diagnosability fix is deployed there — neither is reachable
      from this environment (no network route to the dev server or its
      Azure DevOps variable group), so this stays an open item for whoever
      has that access, not something this change can close on its own.
      Superseded/confirmed by `diagnose-otp-email-delivery-failure`'s
      investigation: a live repro against `vmss-dev.mypits.org` came back
      with the exact "temporarily unavailable" (configured-gateway-failed)
      error, and the root cause traced to `identity_verification`'s
      diagnostics not yet being deployed on `development` — the same
      verification gap, now with a concrete live data point instead of a
      hypothetical.
