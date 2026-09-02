## 1. Baseline

- [x] 1.1 Run `ddev exec uv run pytest -q` fresh and confirm it still matches
      this design's recorded baseline (**645 passed, 0 failed**) before
      making any change — if it doesn't match, stop and reconcile why before
      proceeding. Re-run: **645 passed, 0 failed** (`0:06:43`) — matches
      exactly.
- [x] 1.2 Run `ruff check .` and `ruff format --check .`; confirm both are
      clean or note any pre-existing, unrelated finding (do not fix
      anything outside this change's scope). `ruff check`: clean.
      `ruff format --check`: one pre-existing, unrelated finding — a
      fenced code sample inside `openspec/changes/add-invitation-lifecycle-
      actions/design.md` (a different, already-implemented change's
      planning doc, not source code) — same finding the prior audit noted;
      left as-is.
- [x] 1.3 Run `mypy` on `core/`, `auth/`, and `audit_trail/`
      (`project-rules.md`'s strict-typing scope, since `audit_trail` is
      audit/PII-adjacent); confirm clean. Clean: no issues found in 34
      source files.

## 2. Delegation + relevantToMe: Extend `test_workflow_full_lifecycle.py`

- [x] 2.1 Read the existing scenario's host/approval-chain setup (the
      `# --- Staff-created invitation at Branch A, then manual approval ---`
      stage) and its second-staff-user/branch-role-grant machinery (the
      pattern used in `test_workflow_staff_admin.py`'s
      `# --- Second staff user + branch-role grant ---` stage) closely
      enough to reuse both without duplicating setup logic. Found the
      existing scenario already provisions everything needed without a new
      user: `staff_user_id` ("Branch A Staff") already holds the reception
      role at Branch A from the earlier role-management stage, and the
      "Interview Candidate" visitor category + its `stepOrder=1`
      `reception`-role approval-workflow rule already exist too — both were
      created but never actually used by `invitation_a` (which uses the
      default no-workflow category). Reused both as-is instead of adding
      new setup.
- [x] 2.2 Add a delegation stage immediately after the host's own
      (`stepOrder=0`) step is approved and before the chain's next
      role-identified step is approved directly: host calls
      `POST /invitations/{id}/approval-steps/{stepId}/delegate` naming a
      second staff user who holds that step's role at the branch. Created a
      new invitation under the "Interview Candidate" category with
      `hostId` set to the admin's own user id (resolved via
      `decode_token(...)["sub"]`) so the implicit `stepOrder=0` host step is
      created; admin approves it, then delegates `stepOrder=1` to
      `staff_user_id`.
- [x] 2.3 Assert the delegate — not just any holder of the step's role —
      can now list the invitation via `GET /invitations?relevantToMe=true`,
      and that the invitation is retrievable this way regardless of the
      delegate's own `invitations:view` permission at that branch. Minted
      the delegate's bearer token directly via `create_access_token`
      (non-Admin staff can't use `POST /auth/login`, per
      `separate-admin-staff-login` — same approach `conftest.py::
      issue_token` uses) and confirmed the invitation's `trackingId`
      appears in the `relevantToMe=true` response.
- [x] 2.4 Assert the delegate can approve the delegated step
      (`POST .../approve`) and that this correctly advances the workflow
      the same way a direct role-holder's approval would. Confirmed —
      status moves to `approved` (this was the workflow's last step, so it
      finalizes the invitation).
- [x] 2.5 Add push-notification capture for this stage using the same
      monkeypatch-`.delay`-before/restore-after pattern already used in
      this file for `send_approval_notification`/`send_tracking_notification`
      (design.md Risk 2's mitigation) — confirm the expected push fires
      when the step first becomes current, and that delegation itself does
      not silently trigger an unexpected second one. Monkeypatched
      `notifications.tasks.send_push.delay`. Confirmed: 1 push on
      submission (host step), 1 more when the role step activates
      (broadcast to Branch A's reception-role holders, which already
      includes the eventual delegate), 0 additional from the delegate call
      itself, and 1 more (3 total) from finalization's separate "Invitation
      approved" host push (`invitations/service.py::approve_invitation`) —
      a real push this design didn't anticipate in advance, not a bug;
      asserted its title explicitly once found.
- [x] 2.6 Run `test_workflow_full_lifecycle.py` alone and confirm it passes
      before moving on. Passed (1 passed).

## 3. Audit Trail: Close the Write/Read Loop

- [x] 3.1 In `audit_trail/tests.py`, add a test that performs one real
      mutating call through another feature's router that is known to call
      `record_audit_log` (e.g. an approval, a delegation, or a check-in —
      confirm which call sites currently exist via
      `grep -rn "record_audit_log" src/vmss_api/*/router.py` first, don't
      assume) using the existing test client/fixtures. Chose
      `POST /auth/login` (`auth/router.py`) as the mutating call — it's the
      simplest available one that needs no extra setup beyond the file's
      existing `user`/`client`/`issue_token` fixtures. Added
      `test_login_action_is_retrievable_via_audit_trail`. (The workflow-file
      stage in Section 2 also spot-checks the same loop for the
      `invitation_approval_step_delegated` action, per design.md Decision
      2's note that a same-purpose assertion there is cheap once the
      delegation stage exists — this test is the primary, dedicated one.)
- [x] 3.2 Confirm how `BackgroundTasks`-dispatched work is made observable
      to the test before asserting on it (design.md Risk 3) — check for an
      existing pattern elsewhere in the codebase rather than adding a sleep
      or ad-hoc retry loop. Confirmed: `httpx.AsyncClient` over
      `ASGITransport` runs the whole app in-process on the same event loop,
      so Starlette's `BackgroundTasks` complete before `await client.post`
      returns — no sleep/retry needed, and the test asserts immediately.
- [x] 3.3 Assert the resulting entry is retrievable via `GET /audit-trail`
      with the correct `action`, `entityType`, `entityId`, and actor
      (`actorUserId`), and via `GET /audit-trail/{id}` with the correct
      diff content. Confirmed (login's `diff` is `None` — the endpoint
      doesn't pass one).
- [x] 3.4 Run `audit_trail/tests.py` alone and confirm it passes. **17/17
      passed** (16 pre-existing + 1 new).

## 4. Delegate-Push Investigation (design.md Decision 3)

- [x] 4.1 Read `docs/features/notifications.md`'s recipient-resolution table
      and `openspec/specs/approvals/spec.md`'s delegation requirements to
      check whether a delegate-specific push was ever an intended
      requirement, distinct from the broadcast-to-role-holders push already
      sent when the step activates. Confirmed neither describes one:
      `notifications.md`'s table enumerates exactly two approval-related
      push events ("Invitation submitted" and "A step is approved,
      activating the next step") — delegation is not a third row.
      `approvals/spec.md`'s "Host Delegates the Step Following Their Own to
      a Specific Person" requirement and its 9 scenarios describe
      delegation's authorization/state effects exhaustively (who may
      delegate, when, to whom, and that it "does not itself change the
      step's `pending` status") but never a notification effect.
- [x] 4.2 State the conclusion plainly in the closing summary: either
      "confirmed as intended — no delegate-specific push needed because
      [reason]" or "flagged as a follow-up — [what's missing and why it's
      out of this change's scope]." Do not add a new notification path
      un-grounded in either the docs/specs or an explicit user decision.
      **Confirmed as intended.** The delegate, by construction
      (`_user_holds_role_at_branch` is checked before delegation succeeds),
      always already held the step's role at the branch and so was already
      in the broadcast-push recipient set sent when the step first became
      current. Delegation only narrows *who may subsequently act* on an
      already-notified step — it does not inform anyone of a step's
      existence they didn't already know about. No spec or doc anywhere
      describes a second, delegate-specific notification as intended
      behavior, so this is not a gap.

## 5. Re-Confirm Existing Coverage Not Directly Touched

- [x] 5.1 Run `invitations/tests.py`, `approvals/tests.py`, and
      `notifications/tests.py` in full; confirm their existing counts are
      unchanged and nothing regressed from the Section 2 edits. **192
      passed** (`0:02:05`), nothing regressed.
- [x] 5.2 Run `identity_verification/tests.py`'s Mailpit-backed OTP test and
      `invitations/tests.py`'s Mailpit-backed approval/denial/reschedule
      tests individually; confirm Mailpit is reachable and all still pass —
      re-confirming, not re-deriving, the prior audit's real-SMTP-delivery
      evidence. **4/4 passed** (`pytest -k "mailpit or via_mailpit"`) —
      Mailpit reachable throughout.
- [x] 5.3 Confirm the untracked
      `alembic_tenant/versions/dfb1340caf66_audit_report_jobs.py` migration
      applies cleanly: apply the full tenant migration chain against a
      fresh throwaway schema in `vmss_test`, verify `audit_report_jobs` has
      the expected columns/indexes, then drop the throwaway schema. Applied
      cleanly end-to-end (`e0366161cbb8` → `dfb1340caf66`, every migration
      including the two merge points); verified all 12 expected columns,
      the primary key, both expected secondary indexes
      (`requested_by_user_id`, `status`), and the `users` FK; throwaway
      schema dropped after.

## 6. Closing Gate

- [x] 6.1 Full `ddev exec uv run pytest`: confirm a clean run and record the
      final passed/failed count. First attempt showed 4 spurious
      `UniqueViolationError`s on the shared test tenant's fixture-seeded
      `visitor_categories` row — caused by this session's own earlier
      concurrent `pytest` invocations (Sections 2/3/5) racing against this
      same full-suite run against the same real Postgres DB, exactly the
      "concurrent process interference" hazard the prior audit's tasks.md
      §3.2 already documented. Re-ran alone, nothing else touching the DB:
      **646 passed, 0 failed** (`0:07:22`) — up by exactly 1 from the 645
      baseline, matching the one new `audit_trail/tests.py` test added.
- [x] 6.2 Re-run `ruff check .`, `ruff format --check .`, and the `mypy`
      scope from Task 1.3; confirm still clean. `ruff check`: found and
      fixed one real E501 (line too long) this change's own edit
      introduced; clean after. `ruff format --check`: found and fixed one
      real formatting issue this change's own edit introduced (an
      over-long assert); clean after, same single pre-existing unrelated
      finding remains (`add-invitation-lifecycle-actions/design.md`).
      `mypy` (`core/`, `auth/`, `audit_trail/`): clean, 34 source files.
- [x] 6.3 Write the closing summary: final test count, the delegate-push
      conclusion from Section 4, and any follow-up items surfaced (e.g.
      archiving prior changes, any bug found and fixed, any gap deferred).
      See closing summary below.
- [x] 6.4 No `git add`/`git commit` — leave the working tree for the user's
      review and explicit commit instruction. Confirmed — no git commands
      run against tracked changes during this session.

## Closing Summary

- **Final test count: 646 passed, 0 failed** (up from the 645 baseline by
  exactly 1 — the new `audit_trail/tests.py` write/read integration test).
  `ruff check`/`ruff format --check` clean (one pre-existing, unrelated
  finding in a different change's `design.md` sample, untouched). `mypy`
  clean on `core/`, `auth/`, `audit_trail/`.
- **Delegate-push question (design.md Decision 3): confirmed as intended,
  no gap.** `openspec/specs/approvals/spec.md`'s delegation requirement and
  `docs/features/notifications.md`'s recipient-resolution table both
  describe delegation without a notification effect; the delegate always
  already held the step's role at the branch and so was already in the
  broadcast push sent when the step activated. No change needed.
- **Two real gaps closed:**
  - `tests/test_workflow_full_lifecycle.py` now exercises delegation,
    `relevantToMe`, push notifications, and the audit trail together in one
    real end-to-end scenario (host approves → delegates the next step →
    delegate sees it via `relevantToMe` → delegate approves, finalizing the
    invitation → the delegation action is confirmed retrievable via
    `GET /audit-trail`), closing the "these features have never been
    exercised together" gap from proposal.md finding #1.
  - `audit_trail/tests.py` gained
    `test_login_action_is_retrievable_via_audit_trail`, the first test in
    that file to perform a real mutating action through another feature's
    router and confirm it surfaces through audit-trail's own read API,
    closing the write/read loop gap from proposal.md finding #2.
- **One real bug found and fixed, both in this change's own new test
  code** (not production code — the full-suite run and the per-feature
  re-confirmations in Section 5 found no production bugs): an E501 and an
  over-long assert introduced by the Section 2 edit, caught by `ruff` and
  fixed in Task 6.2.
- **One incidental discovery, not a bug**: finalizing the delegated
  invitation dispatches a third push ("Invitation approved", to the host)
  beyond the two the design anticipated — legitimate, documented behavior
  (`invitations/service.py::approve_invitation`'s own host-notification
  push), just not one this design's author had read closely enough to
  predict in advance. Corrected the test's assertion rather than the code.
- **Follow-ups, not actioned in this change:**
  - Archiving the now-superseded-in-scope prior verify changes
    (`verify-full-api-and-notification-delivery`, etc.) is unaffected by
    this change and remains a separate, later action.
  - This session's own concurrent-pytest-invocation hazard (Task 6.1) is
    worth a note for future sessions doing this kind of work: don't run a
    second `pytest` invocation while a full-suite run is in flight against
    the same real Postgres DB — the prior audit already hit this once too.
