## Why

The server team reports the dev-environment email-sending issue
(`fix-email-dispatch-diagnosability`, archived 2026-08-27) is now fixed on
their side. Before treating that as closed, two things need checking: (1)
whether the diagnosability fix itself was ever committed — `git status`
shows it still sitting unstaged in the working tree from the prior
apply/archive session, meaning it hasn't shipped even if the infra side is
fixed — and (2) whether the full API test suite is still green, since the
user asked to run it broadly and fix anything it turns up.

## What Changes

- No application behavior changes. This is a verification and housekeeping
  pass: confirm the pending code changes from `fix-email-dispatch-
  diagnosability` are committed, and confirm the full test suite passes.
- **Verification limit, stated up front**: this repo/session has no network
  access to the dev server or its Azure DevOps `API-DEV` variable group
  (confirmed — `git fetch` fails with no route to the remote host from this
  environment), and no access to the dev server's own application logs. The
  server team's fix (correcting `MAIL_HOST`/`MAIL_PORT` per
  `fix-email-dispatch-diagnosability/proposal.md`'s flagged action item) can
  only be confirmed by someone who can either send a real invitation on the
  dev environment and check it arrives, or read the dev server's logs for
  the absence of a new `smtp_email_dispatch_failed` warning once that
  diagnosability fix is deployed. This proposal's tasks cover what's
  verifiable from this environment (code committed, tests green) and call
  out the live-environment check as a follow-up for whoever has that access.
- If the full test run (§Impact) turns up failures, this change's tasks
  cover diagnosing and fixing them during apply — scope for that work is
  necessarily open until the run completes, per each finding's own root
  cause.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

(none — this is a verification/housekeeping pass, not a behavior change;
`skip_specs: true` is set in this change's `.openspec.yaml`. If the test
run in Impact below turns up a genuine functional defect, that fix gets its
own follow-up change with the appropriate spec delta rather than being
folded in here after the fact.)

## Impact

- **Git state**: `openspec/specs/invitations/spec.md`,
  `src/vmss_api/invitations/notifications.py`, and
  `src/vmss_api/invitations/tests.py` — the `fix-email-dispatch-
  diagnosability` implementation — are modified but unstaged and
  uncommitted on `bugfixing-api-tasks`. Also untracked: this repo's
  `openspec/changes/archive/2026-08-27-fix-email-dispatch-diagnosability/`
  archive folder itself.
- **Test suite**: full `ddev exec uv run pytest` run as of this proposal
  (with the pending changes above present in the working tree) passed 353/353.
  Re-run during apply to confirm that holds after committing, and to satisfy
  the user's "run the test cases for all APIs" request as a fresh,
  attributable result rather than reusing this proposal-time number.
- **No code changes** are anticipated from this proposal itself — apply's
  scope is `git add`/`git commit` of the already-implemented, already-tested
  fix, plus a confirmation test run. Any fix task only gets added if that
  re-run surfaces a failure.
