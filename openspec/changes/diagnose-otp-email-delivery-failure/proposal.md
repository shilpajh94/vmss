## Why

A live request against `https://vmss-dev.mypits.org/api/v1/identity-verification/otp/request`
with an email identifier returned
`{"success": false, "message": "This delivery channel is temporarily
unavailable", "errors": null}`. That exact wording only comes from
`identity_verification/router.py`'s `except (SmsDispatchError,
EmailDispatchError)` branch — a **configured** gateway that failed
mid-send, not `GatewayNotConfiguredError`'s different message
("not available right now"). Confirmed with the user: the request used an
email identifier, so this is `EmailDispatchError` — the dev server's SMTP
delivery for OTP email is still failing, despite the server team's earlier
report that the mail issue (`fix-email-dispatch-diagnosability`,
archived 2026-08-27) was fixed.

Investigation traced this to a **branch/deployment gap**, not a code defect
on the currently checked-out branch. `CI-CD/Azure-Pipeline-API-DEV.yml`
triggers off the `development` branch — that's what's actually running at
`vmss-dev.mypits.org`. `git merge-base development bugfixing-api-tasks`
equals `development`'s own tip, i.e. the current branch
(`bugfixing-api-tasks`) is exactly `development` **plus one local commit**,
`fcee20e` ("fix: employee listing after add, invitation approval flow, and
public org listings"). That commit's own message states it "add[s]
structured SMTP failure diagnostics to identity verification's email
sender so a dev-server delivery failure can be root-caused from logs" — and
a direct diff confirms `development`'s copy of
`identity_verification/senders.py::SmtpEmailSender.send` is missing the
`smtp_host`, `smtp_port`, and `exception_type` fields on its
`smtp_email_dispatch_failed` warning; it only logs the masked identifier
and the bare exception string. **The diagnosability fix needed to actually
root-cause this failure from the dev server's own logs exists locally but
was never merged/deployed to the branch running there.**

## What Changes

- No application code changes on this branch — `identity_verification/senders.py`
  already carries full diagnostic logging (`smtp_host`, `smtp_port`,
  `exception_type`, masked identifier) here, and its dispatch-failure test
  (`identity_verification/tests.py::test_smtp_dispatch_failure_logs_host_port_and_exception_type`)
  already passes.
- This change's scope is getting the existing fix live and then actually
  reading the evidence it produces, not writing new code:
  1. Get commit `fcee20e` (already pushed to `origin/bugfixing-api-tasks`)
     merged into `development` and redeployed to
     `vmss-dev.mypits.org` — this requires the user/release-owner's
     go-ahead, since merging into a shared branch and triggering a
     redeploy is outside what this session should do unilaterally.
  2. Once redeployed, reproduce the OTP-email-request failure again and
     pull the dev server's `smtp_email_dispatch_failed` warning for that
     request — its `smtp_host`/`smtp_port`/`exception_type` fields are what
     actually distinguish "still the old `MAIL_HOST`/`MAIL_PORT`
     misconfiguration" from a new, different failure (e.g. the relay is now
     reachable but rejecting auth, or TLS negotiation is failing).
  3. Re-flag the open item from `fix-email-dispatch-diagnosability`'s
     proposal: the Azure DevOps `API-DEV` variable group's `MAIL_HOST`/
     `MAIL_PORT` needs re-verification — the previously reported fix has not
     actually resolved delivery, per this live reproduction.
  4. Separately, note (not new scope here, just a dependency to track): the
     `invitations`-side diagnosability fix from this session's earlier
     `fix-email-dispatch-diagnosability` change is still uncommitted per
     `verify-email-fix-and-run-tests`'s pending tasks — once committed, it
     will have the same "not on `development`" gap as `fcee20e` does now,
     so both should go through the same merge when it happens.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

(none — no spec-level behavior changes on this branch; `skip_specs: true`
is set in this change's `.openspec.yaml`. If the redeployed diagnostic log
reveals a genuine new code-level defect once read, that gets its own
follow-up change scoped to the actual root cause.)

## Impact

- **Code**: none on `bugfixing-api-tasks` — the fix already exists and is
  tested here.
- **Deployment/process**: `fcee20e` needs to reach `development` (merge or
  cherry-pick) and `vmss-dev.mypits.org` needs a redeploy before the
  dev server's logs carry enough detail to root-cause this specific
  failure. This is a coordination/release step, not a code task — flagged
  for explicit confirmation before any branch merge is attempted.
- **Still unresolved**: whether the underlying SMTP delivery failure itself
  is the same `MAIL_HOST`/`MAIL_PORT` issue recurring or something new. That
  can only be confirmed once the diagnostic log line above is actually read
  — this proposal cannot close that question from this environment (no
  network route to the dev server, confirmed in the prior
  `verify-email-fix-and-run-tests` change).
