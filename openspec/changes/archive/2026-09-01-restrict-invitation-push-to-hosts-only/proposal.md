## Why

`add-invitation-push-notifications` pushed a role-identified approval step's
notification to every user holding that role at the branch (e.g. every
Admin), alongside the host-identified push. Now that role holders (Admin)
are handled, that role-based push is no longer wanted: push should reach
only the invitation's host, never a role-based approver.

## What Changes

- `notifications.service.notify_step_approver` (called at invitation
  submission and at approval-step activation) no longer dispatches to a
  role-identified step's role holders — only a host-identified step's host
  gets pushed. A role-identified step (current-pending at submission, or
  newly-activated after a prior step's approval) now sends **no** push to
  anyone.
- The general-purpose `notifications` capability itself is unchanged: its
  `notify_role_at_branch`/`list_user_ids_holding_role_at_branch` primitives
  stay in place as reusable dispatch infrastructure (per that capability's
  own "Push Dispatch Is Addressed by User or by Role at a Branch"
  requirement) — this change only removes the one caller that used the
  role branch, not the primitive itself. **Not exercised by any call site
  after this change.**
- The five terminal-action pushes (approve/deny/reschedule/check-in/
  check-out) are unaffected — they already only ever notified the
  invitation's host, never a role.

## Capabilities

### Modified Capabilities
- `invitations`: "Invitation Submission Notifies the Approval Workflow's
  First Approver(s) via Push" narrows to host-identified steps only; a
  role-identified current step at submission no longer triggers a push.
- `approvals`: "Activating an Approval Step Notifies Its Approver(s) via
  Push" narrows the same way — a role-identified step becoming current no
  longer triggers a push.

## Impact

- **Code**: `src/vmss_api/notifications/service.py::notify_step_approver`
  (drop the role branch's dispatch call). No change to
  `invitations/service.py`/`approvals/service.py` call sites themselves —
  they already just call `notify_step_approver` with whatever the step
  resolves to.
- **Tests**: `approvals/tests.py::test_approve_step_non_final_notifies_next_step_approver`
  currently asserts a push for a role-identified next step and needs to
  invert to asserting no push; `invitations/tests.py::test_create_invitation_submission_notifies_host_step_approver`'s
  host-identified case is unaffected, but the (not-yet-covered) role-only
  submission case now needs a "no push" assertion.
- **Docs**: `docs/features/notifications.md`'s "Recipient resolution" table
  needs updating to reflect that a role-identified step sends no push.
- **Out of scope**: removing the now-unused `notify_role_at_branch`/
  `list_user_ids_holding_role_at_branch` primitives entirely. They stay as
  the `notifications` capability's own tested, spec-backed infrastructure
  for a future caller — deleting them is a separate decision this change
  doesn't make.
