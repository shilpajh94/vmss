## 1. Baseline

- [x] 1.1 Run `ddev exec uv run pytest -q` on a clean checkout of this
      branch and record the current pass count/any pre-existing failures,
      so anything this change's work introduces can be distinguished from
      what was already broken. **Result: 826 passed, 0 failed — clean
      baseline.**
- [x] 1.2 Run `ddev exec uv run ruff check`, `ruff format --check`, and
      `mypy` (scoped to `core`, `auth`, `invitations`, `approvals`,
      `notifications`, `sso` per `project-rules.md`'s strict-typing list)
      and record the baseline result. **Result: `ruff check` clean;
      `mypy` clean on all 66 source files across the scoped modules;
      `ruff format --check` flags one pre-existing, out-of-scope
      formatting issue in `openspec/changes/add-invitation-lifecycle-
      actions/design.md` (a markdown doc's embedded code sample, not a
      source file, unrelated to invitations/approvals/notifications/
      sso) — noted as pre-existing baseline noise, not addressed here.**

## 2. Invitation-Creation Path — Staff Pre-Registration Channel

- [x] 2.1 Confirm `POST /invitations` called by an authenticated staff
      caller (the pre-registration wizard's caller, `source=
      staff_pre_registration`) snapshots a role-identified `stepOrder=0`
      step for the tenant's default host role, exactly as the visitor
      self-service caller already does — add the test if missing.
      **No test was missing: `POST /invitations` requires an authenticated,
      branch-scoped employee for every caller — the visitor self-service
      wizard and the staff pre-registration wizard both submit through this
      one endpoint with the same auth requirement, so they are the same API
      call. Already covered by
      `invitations/tests.py::test_create_invitation_notifies_owning_role_even_with_no_configured_rules`
      and `test_create_invitation_submission_notifies_owning_role`, both
      passing in the baseline run.**
- [x] 2.2 Confirm a `hostId`/`hostNameOrEmail` submitted by this caller is
      silently ignored (not rejected), and the invitation still creates
      successfully — add the test if missing. **Already covered:
      `invitations/tests.py::test_create_invitation_ignores_supplied_host_fields`.**
- [x] 2.3 Confirm the branded (Jinja2) tracking/creation email renders and
      dispatches correctly for this caller — add the test if missing.
      **Already covered: dispatch by
      `test_create_invitation_submission_notifies_owning_role` (asserts
      `send_tracking_notification.delay` fires with the right
      `invitation_id`); template content/fallback by
      `test_every_notification_template_renders_without_error` and
      `test_template_rendering_failure_falls_back_to_plain_text`.**

## 3. Invitation-Creation Path — Walk-In Channel

- [x] 3.1 Confirm `POST /registrations/walk-in` snapshots the same
      role-identified `stepOrder=0` step for the tenant's default host role
      — add the test if missing. **Gap found and closed: added
      `registrations/tests.py::test_walk_in_registration_snapshots_role_owned_ownership_step`.**
- [x] 3.2 Confirm `hostId`/`hostNameOrEmail` submitted via walk-in is
      silently ignored, not rejected — add the test if missing. **Gap found
      and closed: added
      `test_walk_in_registration_ignores_supplied_host_fields` (the
      existing `_individual_payload()` fixture already carries a
      `hostNameOrEmail`, so this closes a real, previously-unasserted gap).**
- [x] 3.3 Confirm the optional profile-photo capture and the branded
      creation/tracking email both work identically to the other two
      channels for this unauthenticated caller — add the test if missing.
      **Photo capture was already covered
      (`test_walk_in_registration_with_primary_contact_photo_succeeds`).
      Tracking-email dispatch was only incidentally exercised (call-count
      assertion inside `test_walk_in_registration_idempotency_key_replay`)
      — gap closed with a dedicated
      `test_walk_in_registration_dispatches_tracking_notification`; template
      content itself is channel-agnostic and already covered under task 2.3.
      All three new tests pass (`registrations/tests.py`: 26 passed, up
      from 23).**

## 4. Staff/Admin Invitation Board — Delegation and Edit

- [x] 4.1 Confirm delegating `stepOrder=0` to a user who does not hold the
      default host role succeeds, sets `Invitation.host_id`, and dispatches
      a notification to the new host — re-run existing coverage from the
      archived change and add any missing edge case (e.g. re-delegation
      notifies only the new host, not the previous one). **Happy path
      already covered
      (`approvals/tests.py::test_delegate_ownership_step_to_non_role_holder_succeeds`,
      `test_delegate_ownership_step_resolves_invitation_host_and_notifies`,
      `test_redelegate_ownership_step_updates_resolved_host`). Gap found and
      closed: added
      `test_redelegate_ownership_step_notifies_only_new_host`, asserting
      exactly one push + one email, both addressed to the new delegate, on
      re-delegation (51 passed, up from 50).**
- [x] 4.2 Confirm `PATCH /invitations/{id}/edit` still enforces: visitor-
      personal-field/`visitorCategoryId`/host-field rejection, ineligible-
      status 409, missing-`invitations:edit` 403, unknown-id 404, and that
      it dispatches an edit notification to the primary contact and
      resolved host. **No gap: fully covered already by
      `invitations/tests.py::test_edit_invitation_success` (primary-contact
      email dispatch), `test_edit_invitation_rejects_visitor_personal_fields`,
      `test_edit_invitation_rejects_visitor_category_id`,
      `test_edit_invitation_rejects_host_fields`,
      `test_edit_invitation_ineligible_status_rejected`,
      `test_edit_invitation_requires_permission`,
      `test_edit_invitation_unknown_id_not_found`, and
      `test_edit_invitation_notifies_resolved_host` (host push dispatch).**
- [x] 4.3 Confirm `relevantToMe`'s host clause (a), delegate clause (b), and
      role-holder clause (c) all still resolve correctly against a freshly
      role-owned invitation, per the archived change's `invitations` spec.
      **No gap: all three clauses, their interaction with re-delegation,
      status filtering, empty-result, `X-Branch-ID` being ignored, and
      tenant isolation are already exercised by the 12
      `test_list_invitations_relevant_to_me_*` tests in
      `invitations/tests.py`, all running against this module's
      role-owned-by-default fixture setup.**

## 5. Staff/Admin Invitation Board — Approve, Deny, Reschedule, Extend, Badge, Check-In/Out

- [x] 5.1 Confirm `POST /invitations/{id}/approval-steps/{stepId}/approve`
      and the blanket `POST /invitations/{id}/approve` both still behave
      per spec (409 when steps are snapshotted, single-step approval
      dispatches correctly) against a role-owned invitation. **No gap:
      covered by `test_approve_invitation_rejected_for_workflow_backed_invitation`,
      `test_approve_invitation_rejected_for_host_only_invitation`,
      `test_approve_step_non_final_unlocks_next_step_and_computes_its_clock`,
      `test_approve_step_last_step_approves_invitation_and_dispatches_notification`,
      plus role/host-match, override-permission, and out-of-order cases in
      `approvals/tests.py`.**
- [x] 5.2 Confirm step rejection still denies the invitation and dispatches
      the denial notification with the new push-payload addressing fields
      (`assignedRoleId`/`assignedUserId`/`reason`) intact. **No gap:
      `approvals/tests.py::test_reject_step_denies_invitation_and_leaves_later_steps_pending`
      covers denial; the payload shape itself is directly asserted by
      `notifications/tests.py::test_notify_user_payload_carries_assigned_user_id_and_reason`
      and `test_notify_role_at_branch_payload_carries_assigned_role_id_and_reason`.**
- [x] 5.3 Confirm `reschedule` and `extend` still dispatch their respective
      notifications and enforce their existing eligibility rules, unaffected
      by the ownership-step change. **No gap: `test_reschedule_invitation_success`,
      `test_reschedule_invitation_after_check_in_rejected`,
      `test_reschedule_invitation_notifies_host`, `test_extend_invitation_success`,
      `test_extend_invitation_earlier_expiry_rejected`,
      `test_extend_invitation_ineligible_status_rejected` all pass.**
- [x] 5.4 Confirm badge issue/reprint and QR + staff check-in/check-out
      still succeed for a role-owned-then-delegated invitation, including
      that the check-in/check-out detail responses still surface the
      resolved host correctly. **No gap: badge issue/reprint fully covered
      (`test_issue_badge_success`, `test_reprint_badge_success_and_reflects_updated_expiry`,
      plus permission/eligibility/idempotency variants); check-in/check-out
      response host-field serialization covered by
      `test_public_check_in_response_includes_full_invitation_detail`
      (asserts `hostNameOrEmail` matches the persisted row); combined with
      task 4.1's confirmation that delegation correctly sets
      `host_id`/`host_name_or_email`, this composes to full coverage
      without a redundant end-to-end duplicate. Full
      `invitations/tests.py` run: 231 passed.**

## 6. SSO Regression

- [x] 6.1 Run the full `sso/tests.py` suite (including the new
      `test_list_role_mappings_sort_by_idp_group_claim_value` test) and
      confirm no existing SSO test regressed. **Result: 42 passed, 0
      failed.**
- [x] 6.2 Exercise the full OIDC flow end to end in a test (provider config
      → `start_login` → `handle_callback` → `redeem_exchange_code` → user
      provisioning/role-mapping resolution) if not already covered by an
      existing single test, to confirm login is unaffected by the
      invitation/approvals/notifications changes. **Already covered:
      `test_full_login_flow_creates_account_with_mapped_role` drives the
      full login → callback → exchange → provisioning → role-mapping →
      audit chain in one test and passes. No gap; no new test needed.**

## 7. Full-Suite Gate

- [x] 7.1 Re-run `ddev exec uv run pytest -q` after tasks 2-6 and confirm
      the pass count only grew (new tests added) with zero new failures
      relative to the 1.1 baseline. **Result: 830 passed (up from the 826
      baseline — the 4 tests added in tasks 3 and 4), 0 failed.**
- [x] 7.2 Re-run `ruff check`, `ruff format --check`, and `mypy` (same
      scope as 1.2) and confirm clean. **Result: `ruff check` clean;
      `ruff format --check` scoped to `src/vmss_api` (145 files) clean —
      the one pre-existing formatting issue from task 1.2 is confined to
      an `openspec/changes/` markdown doc, outside source; `mypy` clean on
      all 74 source files across the scoped modules (now including
      `registrations`, touched by task 3's new tests).**

## 8. Cross-Repo Handoff — VMMS_WEB Manual Verification Script

- [x] 8.1 Write a channel-by-channel manual verification script (as a
      section in this change's final summary, for a human or a future
      `VMMS_WEB`-scoped session to run against the deployed web app) that
      closes `VMMS_WEB/openspec/changes/role-based-invitation-workflow/
      tasks.md` task 7.2 for all three channels: (a) visitor self-service
      wizard — already manually confirmed working by the user, record that
      as done; (b) staff pre-registration wizard — create with no host
      field shown, confirm "Unassigned — Front Office" ownership, delegate
      to a specific host, confirm card + notification-center reflect it,
      edit date/time via the Edit modal; (c) walk-in check-in flow —
      confirm the same ownership/notification behavior end to end.
      **Done: see `web-verification-checklist.md` in this change directory.**
- [x] 8.2 Note, for the user, that `VMMS_WEB`'s other currently-open changes
      (`fix-invitation-contact-validation`,
      `fix-visitor-category-badgecolor-nullable`,
      `fix-visitor-category-invalid-id-fallback`,
      `fix-visitor-wizard-contact-method-default`,
      `fix-staff-dashboard-refresh-filters`,
      `integrate-audit-dashboard-apis`, `visit-card-schedule-actions`,
      `push-notifications`) touch adjacent invitation-board/notification
      surfaces and are worth a quick overlap check before archiving
      `role-based-invitation-workflow` on the web side, but are explicitly
      out of scope for this change to modify. **Done: noted in
      `web-verification-checklist.md`'s final section, and in this
      session's summary to the user.**
