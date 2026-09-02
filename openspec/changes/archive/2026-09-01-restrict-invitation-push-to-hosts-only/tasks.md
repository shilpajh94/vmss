## 1. Narrow Recipient Resolution

- [x] 1.1 `notifications/service.py::notify_step_approver` — remove the
      `notify_role_at_branch(...)` dispatch from the role-identified branch;
      a role-identified step (`approver_role_id` set) now returns without
      dispatching anything. Leave `notify_role_at_branch` and
      `auth/repository.py::list_user_ids_holding_role_at_branch` themselves
      in place (unused by this call site after this change, but still the
      `notifications` capability's own dispatch-by-role primitive).

## 2. Update Tests

- [x] 2.1 `approvals/tests.py::test_approve_step_non_final_notifies_next_step_approver`
      — invert to assert `notify_step_approver`'s role-identified branch no
      longer calls `notify_role_at_branch` (or, more simply, that
      `notify_user`/`notify_role_at_branch` are never called when the newly
      current step is role-identified). Keep
      `test_approve_step_last_step_does_not_double_notify` as-is — still
      correct, unaffected by this change.
- [x] 2.2 Add a host-identified-step-activation test alongside 2.1's
      inverted case if one doesn't already assert the still-working
      host-identified path (`test_approve_step_host_identified_*` tests in
      `approvals/tests.py` cover authorization already; confirm one also
      exercises the push, or add one).
- [x] 2.3 `invitations/tests.py` — add a submission test for a role-identified
      first step (no resolved host, a category with an active role-based
      workflow rule) asserting no push is dispatched, alongside the existing
      `test_create_invitation_submission_notifies_host_step_approver`
      (host-identified, unaffected) and
      `test_create_invitation_hostless_no_rules_skips_push` (zero steps,
      already covers the "nothing to push" case for a different reason).

## 3. Documentation

- [x] 3.1 `docs/features/notifications.md` — update the "Recipient
      resolution used by `invitations`/`approvals`" table: submission and
      step-activation rows now read "host only — a role-identified step
      sends no push", not "host if host-identified, else role holders".

## 4. Verification

- [x] 4.1 `ruff check`/`ruff format --check` clean on touched files.
- [x] 4.2 `mypy src/vmss_api` clean.
- [x] 4.3 Full `pytest` suite green.
