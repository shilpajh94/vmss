## Context

The push stack (`notifications/service.py`) is complete and has two ways to
address a push: `notify_user` and `notify_role_at_branch`. The second
supports `exclude_user_ids` and `reason`. `invitations/service.py` uses it in
two ways:

- `_notify_host(tenant, invitation, builder)` pushes the resolved host. It
  is called from approve, deny, revert, both check-in paths, both check-out
  paths, reschedule, edit and extend.
- `_notify_responsible_staff(..., event, actor_user_id)` is called only
  from deny, revert and reschedule. It does two jobs: it enqueues the
  per-recipient staff email, and it pushes the POC user or POC role with
  the actor and host excluded (staff-lifecycle-emails-and-dashboard-landing
  D1/D4). The exclusion rule lives in `_responsible_staff`.

The POC-push half is what this change extends to five more events. The
staff-email half stays limited to deny, revert and reschedule; that
change's Non-Goals deliberately left out email on check-in, check-out and
extend.

Actor availability at each call site:

| Path | Actor available today |
|---|---|
| `approve_invitation` | ✗ (router has `user`; `approvals.approve_step` has `user`) |
| `_perform_check_in` | ✓ `actor_user_id` (may be `None` for tracking-id/kiosk) |
| `check_in_by_qr_token`, `check_out_by_qr_token` | none, public QR path |
| `check_out_invitation` | ✓ `user_id` |
| `edit_invitation` | ✓ `user` |
| `extend_invitation` | ✗ (router has `user`) |

## Goals / Non-Goals

**Goals:**
- One POC-push code path shared by all eight POC-pushed events, with the
  actor/host exclusion defined once.
- No change to who receives the host push or any email.

**Non-Goals:**
- Excluding the host from their own host push when the host is the actor.
  Today `_notify_host` pushes the host even for an action they performed.
  That's an existing behavior of a different requirement and stays as is.
- Any new `action` value or payload key. Clients see the same payload shape
  they already handle.

## Decisions

### D1. Split `_notify_responsible_staff` into email + `_push_point_of_contact`

Extract the POC-push half into:

```python
async def _push_point_of_contact(
    tenant_db, tenant, invitation, *,
    push_builder: Callable[[Invitation], tuple[str, str, dict[str, str]]],
    actor_user_id: uuid.UUID | None,
) -> None
```

It resolves the POC with the same exclusion rules `_responsible_staff`
applies today: a POC user equal to the actor or the host is skipped, and a
role fan-out excludes `{actor, host}` with `reason="lifecycle_update"`.
`_notify_responsible_staff` keeps its email loop and calls this helper for
its push. That keeps deny, revert and reschedule behavior byte-identical.

The five newly covered call sites each call `_notify_host(...)` and then
`_push_point_of_contact(...)` with the same builder.

*Alternative considered*: fold the POC push into `_notify_host` itself (a
`_notify_staff`). That was rejected because `_notify_host` has no DB
session or actor, and its "host only" contract is what the existing host
requirement and its tests assert. Widening it would quietly change deny,
revert and reschedule, which call both functions and would then double-push
the POC.

*Alternative considered*: add the five events to `_notify_responsible_staff`'s
`event` map. That was rejected because the function also sends staff
**email**, and email for these events is an explicit non-goal. A flag to
suppress email would make the function do two unrelated things.

`_responsible_staff`'s `push_poc_user_id` logic moves into the helper, and
the `_ResponsibleStaff` dataclass becomes a plain
`_staff_email_recipients` function, since email recipients are all that's
left of it. The push-exclusion rule now has one owner.

### D2. `actor_user_id: uuid.UUID | None` with `None` meaning "no human actor"

`approve_invitation` and `extend_invitation` gain a keyword-only
`actor_user_id: uuid.UUID | None = None`. The `None` default keeps the
signatures backward compatible for tests and any internal caller. The two
routes pass `user.id`, and `approvals.approve_step` passes `user.id`. For
QR check-in and check-out the helper is called with `actor_user_id=None`,
so only the host is excluded.

`deny_invitation` and `reschedule_invitation` already take a required
actor, and they're untouched.

### D3. An edit that names a new POC skips the `edited` POC push for that POC

`edit_invitation` already sends `poc_assigned` when `poc_user_id` or
`poc_role_id` changes. The `edited` POC push therefore runs only when the
POC did **not** change in this edit. When it changed, the previous POC is no
longer responsible and the new one has just had `poc_assigned`, so no
`edited` POC push is sent. This works as one `if` on the existing
`"poc_user_id" in changes or "poc_role_id" in changes` check, so the helper
needs no knowledge of the previous POC and no extra "skip this user"
parameter.

### D4. Push only after a real state change, after commit

Every new POC push sits immediately after the existing `_notify_host` call.
That means it runs after `tenant_db.commit()` and only on the success path.
So it inherits the host push's guarantees: no push on a 409, 410, 422 or 425
rejection, no push for an idempotent no-op check-in (the early `return
..., False` path in `_perform_check_in`), and no push for an uncommitted
transaction. A role fan-out resolves its holders synchronously on the
request's `tenant_db`, like the deny/revert/reschedule fan-out already does.

## Risks / Trade-offs

- **Notification volume for role POCs.** A busy reception desk whose POC is
  a role with many holders now pushes all of them on every check-in and
  check-out. → This is the same fan-out rule already accepted for
  deny/revert/reschedule. Staff choose to name a role as POC, so volume is
  under their control.
- **Admin as a POC role.** Any role can be named POC, Admin included. The
  `poc_assigned` push goes through `notify_step_approver`, which skips
  Admin and `host`. The existing deny/revert/reschedule fan-out calls
  `notify_role_at_branch` directly and does **not** skip them. The helper
  keeps the lifecycle fan-out's existing behavior, with no Admin
  exclusion, so deny/revert/reschedule don't change. Someone who names a
  role as the point of contact asked for that role to hear about the
  visit. The `exclude-admin-role-only-from-push` decision covers approval
  triage, not a POC an admin named on purpose.
- **One extra synchronous query per action with a role POC.**
  `list_user_ids_holding_role_at_branch` runs once on the request path.
  It's a single indexed `IN`-free query with no loop, the same cost
  deny/revert/reschedule already pay.
- **QR check-in pushes from an unauthenticated endpoint.** The recipients
  are resolved server-side from the invitation, never from the request, so
  a QR scan can't steer a push anywhere new.

## Migration Plan

Code-only. Deploy normally. No migration, setting or client release is
needed. To roll back, revert the commit. Nothing persists that depends on
the new behavior.

## Open Questions

- Should a **watchlist-flagged** invitation, or a check-in blocked by the
  watchlist, push a security role? And should a **kiosk device** awaiting
  approval push a device-admin role? Neither has a defined recipient role
  today. Each needs a product decision on who receives it, then its own
  change.
