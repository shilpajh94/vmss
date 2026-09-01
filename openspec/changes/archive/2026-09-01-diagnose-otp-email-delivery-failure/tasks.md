## 1. Confirm the Local Fix Is Sound

- [x] 1.1 Re-run `identity_verification/tests.py::test_smtp_dispatch_failure_logs_host_port_and_exception_type`
      to reconfirm the diagnostic logging (`smtp_host`, `smtp_port`,
      `exception_type`) is present and correct on `bugfixing-api-tasks`
      before pointing at a branch/deploy gap as the cause. Passed.
- [x] 1.2 Confirm (via `git diff development bugfixing-api-tasks --
      src/vmss_api/identity_verification/senders.py`) that this is still
      the only difference relevant to this failure, in case other commits
      have landed on either branch since this proposal was written.
      `git fetch` still fails (no network route to the remote from this
      environment — unchanged from `verify-email-fix-and-run-tests`'s
      finding), so this only confirms no *local* drift: `merge-base
      development bugfixing-api-tasks` is still `development`'s own tip
      (568866d) — `bugfixing-api-tasks` remains exactly `development` +
      commit `fcee20e`, and `identity_verification/senders.py` is still the
      only diff relevant to this failure (the full 47-file diff between the
      branches is otherwise unrelated feature work bundled into that same
      commit). Whether anything *new* has landed on the remote
      `development` since this session's last sync can't be checked from
      here.

## 2. Get the Diagnostics Deployed (requires explicit go-ahead before any push/merge)

- [x] 2.1 Confirm with the user/release owner whether to merge or
      cherry-pick commit `fcee20e` from `bugfixing-api-tasks` into
      `development` — do not merge or push to a shared branch without
      explicit confirmation.
      **User explicitly confirmed** preparing a local-only merge (not a
      push). Performed: `git checkout development && git merge --ff-only
      bugfixing-api-tasks` — a clean fast-forward from `568866d` to
      `dcac61a` (brings in both `fcee20e` and `dcac61a`), since
      `bugfixing-api-tasks` was a direct linear descendant of the local
      `development` ref. Then switched back to `bugfixing-api-tasks` (the
      user's working branch) to avoid leaving the working tree on a
      different branch than expected.
      **Important caveat surfaced by the merge itself**: local
      `development` was already 7 commits behind `origin/development`
      *before* this fast-forward (this environment has no fetch access, so
      that staleness couldn't be detected beforehand). After the local
      fast-forward, `git status` shows local `development` is now `ahead 1,
      behind 6` of `origin/development` — **not push-ready as-is**.
      Whoever pushes this must first `git fetch && git rebase
      origin/development` (or merge) from a machine with real credentials,
      reconcile with those 6 unknown upstream commits, resolve any
      conflicts, and only then push — this session cannot do that step or
      see what those 6 commits contain.
- [ ] 2.2 Once merged, confirm (or ask whoever owns the pipeline to
      confirm) that `Azure-Pipeline-API-DEV.yml` redeployed
      `vmss-dev.mypits.org` from the updated `development`.
      Blocked on 2.1's real push (see caveat above) actually landing on
      `origin/development` first — not done.

## 3. Root-Cause From the Redeployed Logs

- [ ] 3.1 Reproduce the OTP email-request failure again against
      `vmss-dev.mypits.org` after redeploy.
- [ ] 3.2 Retrieve the matching `smtp_email_dispatch_failed` log line
      (needs dev-server log access this session doesn't have) and record
      its `smtp_host`, `smtp_port`, and `exception_type`.
- [ ] 3.3 Based on that evidence, determine whether this is the
      previously-flagged `MAIL_HOST`/`MAIL_PORT` misconfiguration still
      unresolved, or a distinct failure (e.g. relay reachable but rejecting
      auth/TLS) — and scope a follow-up change for whichever it is, rather
      than guessing further from this environment.
