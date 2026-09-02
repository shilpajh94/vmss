## Why

Verification finding: `restrict-invitation-push-to-hosts-only` (archived)
over-corrected. It was meant to stop the Admin role specifically from
receiving push, but it implemented "no role-identified step ever pushes to
anyone" instead — `notifications.service.notify_step_approver`'s role
branch is now dead code, so **every** role-based approver (Reception,
Security, or any other custom role a tenant configures as an
`ApprovalWorkflowRule.approverRoleId`) silently stops receiving push too,
not just Admin. The actual requirement is narrower: hosts get push, other
selected staff approvers get push, only the Admin role is excluded.

## What Changes

- `notify_step_approver`'s role-identified branch dispatches to
  `notify_role_at_branch` again (as it did before
  `restrict-invitation-push-to-hosts-only`), **except** when the resolved
  role is the tenant's standard `admin` role (matched by name,
  case-insensitively — `admin` is a seeded, non-renameable, non-deletable
  role name per `auth/rbac_catalog.py`, so name-matching it is reliable).
  A role-identified step whose role is anything other than `admin` — e.g.
  Reception, Security, or a tenant-defined custom role — pushes to every
  holder of that role at the invitation's branch, exactly like before
  `restrict-invitation-push-to-hosts-only`.
- Host-identified steps and the five terminal-action pushes
  (approve/deny/reschedule/check-in/check-out) are unaffected — they were
  never touched by the over-broad exclusion in the first place.

## Capabilities

### Modified Capabilities
- `invitations`: "Invitation Submission Notifies the Approval Workflow's
  First Approver(s) via Push" widens back from "host-identified only" to
  "host-identified, or role-identified when the role isn't Admin."
- `approvals`: "Activating an Approval Step Notifies Its Approver(s) via
  Push" widens the same way.

## Impact

- **Code**: `src/vmss_api/notifications/service.py::notify_step_approver`
  — resolve the `Role` row for `approver_role_id` (new: a
  `RoleRepository(tenant_db).get(...)` lookup) and dispatch to
  `notify_role_at_branch` unless `role.name.lower() == "admin"`. A deleted
  or unresolvable role is treated as "not admin" (dispatches normally) —
  the FK guarantees a role-identified step's `approver_role_id` names a
  real row; a lookup miss here would indicate the referenced role was
  deleted out from under an in-flight invitation, an edge case out of
  scope for this fix.
- **Tests**: `approvals/tests.py`'s
  `test_approve_step_non_final_role_identified_step_sends_no_push`
  (added by the prior change) needs to become two tests — one for a
  non-Admin role (push fires) and one for the Admin role specifically (no
  push). Same split needed for
  `invitations/tests.py::test_create_invitation_role_identified_step_sends_no_push`.
- **Docs**: `docs/features/notifications.md`'s "Recipient resolution"
  table and its role-dispatch note need correcting back to "role holders
  get pushed, except the Admin role."
- **Out of scope**: no change to which roles can be configured as
  `ApprovalWorkflowRule` approvers, and no change to the Admin role's other
  permissions/behavior — this only affects whether Admin-role holders
  receive a *push notification* for a step they approve.
