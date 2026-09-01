## 1. Baseline

- [x] 1.1 Ran `ddev exec uv run pytest -q` fresh: **605 passed, 1 failed**
      (`test_create_invitation_cross_tenant_visitor_category_id_rejected`)
      — matches design.md's recorded baseline exactly.
- [x] 1.2 `ruff check .`: clean. `ruff format --check .`: one pre-existing,
      unrelated finding — a fenced Python code sample inside
      `openspec/changes/add-invitation-lifecycle-actions/design.md` (a
      different, already-implemented change's planning doc, not source
      code). Left as-is — out of this change's scope; noted in the closing
      summary.

## 2. Root-Cause and Fix the Failing Cross-Tenant Test

- [x] 2.1 Root cause confirmed: `make_tenant_schema` (`conftest.py`) only
      ever does `CREATE SCHEMA IF NOT EXISTS` and never drops the schema —
      every ad-hoc schema these fixtures create is permanent across test
      runs on the same Postgres instance. This test commits a
      `VisitorCategory` row with a **fixed literal** `name="Other Tenant
      Category"` into `tenant_other_category_test`; a second run of the
      suite against the same database collides with the row the first run
      already left there.
- [x] 2.2 `grep -rn "Other Tenant Category"` across every `tests.py`: only
      one usage (this test) — ruled out a second test writing the same
      literal.
- [x] 2.3 Confirmed this is not a cross-schema leak: the collision is
      within the *same* schema (`tenant_other_category_test`) across two
      *different test-suite runs*, not one tenant's session reading/writing
      another tenant's schema. Schema-per-tenant isolation itself is intact.
- [x] 2.4 Fix applied in `conftest.py::make_tenant_schema`: `_make` now
      issues `DROP SCHEMA IF EXISTS "<name>" CASCADE` before
      `CREATE SCHEMA`, so every ad-hoc tenant schema these ~32 call sites
      across the suite use is genuinely fresh per test, matching the
      fixture's own "provisioning ... on demand" docstring intent. Scoped
      to this one fixture function only — the session-scoped default
      tenant schema setup (`_test_database`) is untouched.
- [x] 2.5 Re-ran the fixed test individually (passed), then confirmed no
      neighboring cross-tenant test regressed (Section 3).

## 3. Stages 1-8 (API-01..API-19) — Re-Confirm, Don't Re-Derive

- [x] 3.1 Full suite re-run after the Section 2 fix (see Section 8's
      closing-gate run for the final number); no other failures introduced.
- [x] 3.2 Spot-checked all four named regression tests: `auth/tests.py`'s
      branch-role-grant 409 test (8/8 passed), `invitations/tests.py`'s
      `approve_if_submitted`/concurrency test (passed),
      `sso/tests.py`'s SSRF-guard and rate-limit tests (4/4 passed), and
      `tests/test_workflow_full_lifecycle.py` in full (passed).
      (Two of these initially showed spurious failures caused by a leftover
      background `pytest` process from task 1.1 still mutating the shared
      `vmss_test` database concurrently — killed the zombie process and
      re-ran cleanly; not a real regression, see closing summary.)
- [x] 3.3 Nothing regressed once run without the concurrent-process
      interference — no fix needed beyond Section 2's.

## 4. Stage 9 — Notifications (Push): Re-Confirm Existing Coverage

- [x] 4.1 `notifications/tests.py` run in isolation: **16/16 passed**,
      including `test_device_token_tenant_isolation` and all three
      `test_notify_step_approver_*` role-resolution tests.
- [x] 4.2 `approvals/tests.py` run in full: **27/27 passed**, including the
      `_fake_notify_user`/`_fake_notify_role_at_branch`/
      `_fake_notify_step_approver`-backed tests against the current
      uncommitted `approvals/service.py`.
- [x] 4.3 Confirmed `alembic_tenant/versions/6f4e364ea9c8_device_tokens.py`
      applies cleanly: ran the full tenant migration chain
      (`alembic -c alembic_tenant.ini -x tenant_schema=<throwaway>
      upgrade head`) against a fresh throwaway schema in `vmss_test` — every
      migration up to and including `6f4e364ea9c8` applied without error;
      verified `device_tokens` has all 6 expected columns and all 3 expected
      indexes (`_pkey`, `ix_..._user_id`, unique `ix_..._fcm_token`), then
      dropped the throwaway schema.

## 5. Close the Dual-Channel Gap (design.md Decision 2)

- [x] 5.1 `test_create_invitation_submission_notifies_host_step_approver`:
      added an `email_calls` capture on `tasks.send_tracking_notification.
      delay` (this test's invitation is non-auto-approved, so that's the
      task `create_invitation` dispatches) alongside the existing push
      assertion.
- [x] 5.2 `test_approve_invitation_notifies_host`: `send_approval_
      notification.delay`'s args now captured and asserted
      (`invitation_id`) alongside the existing push assertion.
- [x] 5.3 `test_deny_invitation_notifies_host`: same for
      `send_denial_notification.delay`.
- [x] 5.4 `test_reschedule_invitation_notifies_host`: same for
      `send_reschedule_notification.delay`.
- [x] 5.5 Confirmed from `invitations/service.py` (only 4 `.delay(` call
      sites total: submission, approve, deny, reschedule) that
      `check_in_invitation`/`check_out_invitation` dispatch **no**
      visitor-facing email/SMS task at all — push only. Added an explicit
      docstring note to `test_check_in_invitation_notifies_host` and
      `test_check_out_invitation_notifies_host` stating this, per the task's
      own instruction not to assert something that doesn't exist.
- [x] 5.6 All 6 tests re-run individually (6/6 passed) and the full
      `invitations/tests.py` file (127/127 passed) — every existing push
      assertion unchanged, every new email/SMS assertion passes.

## 6. Mailpit-Backed Real-Delivery Tests (design.md Decision 1)

- [x] 6.1 Added `test_request_and_verify_otp_over_email_delivers_real_
      email_via_mailpit` to `identity_verification/tests.py`: OTP request is
      inline/synchronous (no Celery task, `service.py` calls
      `senders.email_sender.send` directly), so this just leaves the module
      default `SmtpEmailSender` unpatched, makes the real request, reads the
      code back from the Mailpit-received message, and completes
      `/otp/verify` with it — highest priority per proposal.md finding #2.
- [x] 6.2 Added `test_send_denial_notification_delivers_email_via_mailpit`
      to `invitations/tests.py`, colocated with the existing approval
      Mailpit test (same `_FakeInvitation`/`.apply()` helpers), asserting
      subject "Your visit request was not approved".
- [x] 6.3 Added `test_send_reschedule_notification_delivers_email_via_
      mailpit`, same location/pattern, asserting subject "Your visit has
      been rescheduled".
- [x] 6.4 All three new tests pass; Mailpit was reachable throughout at
      `localhost:8025` in this environment (confirmed via the pre-existing
      approval test before adding these) — no environment-limitation note
      needed.

## 7. State the OTP/SMTP Dev-Delivery Item Plainly

- [x] 7.1 Confirmed `identity_verification/senders.py`'s diagnostic logging
      (`smtp_host`, `smtp_port`, `exception_type`) is present and
      `test_smtp_dispatch_failure_logs_host_port_and_exception_type` passes.
- [x] 7.2 Checked git state directly rather than assuming: `git merge-base
      --is-ancestor dcac61a development` confirms commit `dcac61a` ("fix:
      log SMTP host/port and exception detail...") **is now an ancestor of
      `development`** — this branch (`feature/api-tasks-week-3`) is exactly
      `development`'s current tip plus 4 unrelated feature commits, so the
      "not yet merged" gap `diagnose-otp-email-delivery-failure` found is
      **closed** as of this run. What remains genuinely unconfirmable from
      this session/environment (no network route to `vmss-dev.mypits.org`
      or its logs, per both prior audits): whether
      `CI-CD/Azure-Pipeline-API-DEV.yml` has actually redeployed
      `development`'s current tip, and whether that resolved the live
      OTP-email delivery failure — confirming either requires someone with
      dev-server/pipeline access to check the deploy history or send a real
      OTP-over-email request there and read the (now-present) diagnostic
      log line.

## 8. Closing Gate

- [x] 8.1 Full `ddev exec uv run pytest`: **609 passed, 0 failed** (up from
      the 605-passed/1-failed baseline: +1 for the fixed cross-tenant test,
      +3 for the new Mailpit tests). Two background-process false starts
      during this run (the tool's shell wrapper died on a 300s timeout
      while the actual `ddev exec`-nested pytest process kept running
      underneath it) cost wall-clock time but not correctness — the final
      run captured to a plain log file inside the repo confirms the number
      above cleanly.
- [x] 8.2 `ruff check .`: clean. `ruff format --check .`: same single
      pre-existing, unrelated finding as the 1.2 baseline (unrelated
      change's `design.md` doc sample) — nothing introduced by this
      change's edits.
- [x] 8.3 `mypy` on `core/`, `auth/`, `notifications/`: clean, 35 source
      files, no issues.
- [x] 8.4 Closing summary written below (in the apply-session response).
- [x] 8.5 No `git add`/`git commit` run — working tree left for the user's
      review and explicit commit instruction.
