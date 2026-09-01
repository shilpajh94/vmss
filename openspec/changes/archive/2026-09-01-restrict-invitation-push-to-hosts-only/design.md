## Context

See `proposal.md` for motivation. `add-invitation-push-notifications`
(archived) built `notifications.service.notify_step_approver` as the shared
entry point `invitations/service.py::create_invitation` and
`approvals/service.py::_activate_next_step` both call with an
`InvitationApprovalStep`'s `approver_user_id`/`approver_role_id` XOR:

```python
async def notify_step_approver(tenant_db, *, tenant_schema, approver_user_id,
                                approver_role_id, branch_id, title, body, data=None) -> None:
    if approver_user_id is not None:
        await notify_user(tenant_schema=tenant_schema, user_id=approver_user_id, ...)
        return
    assert approver_role_id is not None
    await notify_role_at_branch(tenant_db, tenant_schema=tenant_schema,
                                 role_id=approver_role_id, branch_id=branch_id, ...)
```

Both call sites already just hand this function whatever the current/newly-
activated step resolves to — neither one branches on host-vs-role itself.

## Goals / Non-Goals

**Goals:**
- Stop pushing to role-identified-step approvers (e.g. Admin) at submission
  and at step activation — host-identified steps keep pushing exactly as
  before.

**Non-Goals:**
- Removing `notify_role_at_branch`/`list_user_ids_holding_role_at_branch` or
  their own `notifications` capability requirement — they stay as
  general-purpose, spec-backed infrastructure for a future caller, per the
  proposal's explicit scoping.
- Touching the five terminal-action pushes (approve/deny/reschedule/
  check-in/check-out) — those already resolve only the invitation's host,
  never a role, so nothing about them changes.

## Decisions

### Decision: Narrow `notify_step_approver` itself, not its two call sites
The role branch inside `notify_step_approver` becomes a no-op instead of
calling `notify_role_at_branch`. Both `create_invitation` and
`_activate_next_step` keep calling `notify_step_approver` exactly as they do
today, unchanged — they never need to know whether a step is host- or
role-identified themselves. This keeps the "which steps get pushed" policy
in exactly one place, as it already was, rather than duplicating a
`if approver_role_id is not None: skip` check at each of the two call sites.

**Alternative considered**: have each call site check `approver_role_id is
None` before calling `notify_step_approver` at all. Rejected — it moves the
recipient policy out of the function whose entire job is resolving it,
back into two call sites, which is the exact duplication
`notify_step_approver` was introduced to avoid in the first place.

### Decision: No warning log for a skipped role-identified step
Unlike the existing "no host and no active workflow rules" case (which logs
`WARNING` — a genuine gap, nobody to notify), a role-identified step now
sends no push *by design*. Logging a `WARNING` here would misrepresent
expected, intended behavior as an anomaly. No log line is added for this
path.

## Risks / Trade-offs

- **[Trade-off]** A role-only approval chain (no host anywhere in it) now
  produces zero push notifications for its entire lifecycle until an
  eventual approve/deny reaches the terminal push (which itself only fires
  if a host resolved — so a genuinely hostless, role-only invitation now
  never pushes at all). Accepted: this matches the stated requirement
  exactly — role-based (Admin) recipients no longer get push, full stop.

## Migration Plan

- Pure behavior change in one function body; no data model, endpoint
  contract, or migration involved. Deploys and rolls back as a plain code
  change.
