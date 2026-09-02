# Approvals

Runtime evaluation of a `VisitorCategory`'s configured `ApprovalWorkflowRule`
chain (`docs/features/visitors.md`) against an actual submitted invitation
(`docs/features/invitations.md`) — the piece both of those docs previously
flagged as "not yet built." Everything here is tenant-scoped by schema
(`Base`, not `GlobalBase`).

See `openspec/changes/invitation-multi-step-approval/` for the
proposal/spec/design this feature was built from, and
`openspec/changes/add-approval-step-id-and-host-routing/` for the
host-as-step-0 composition and `id`/`approverUserId` additions below.

## What this package owns, and what it doesn't

- **Owns**: the `InvitationApprovalStep` snapshot, the step
  approve/reject endpoints, and the role-match/override authorization check
  on top of them.
- **Does not own**: `ApprovalWorkflowRule` CRUD (still `visitors/`, config
  only) or the snapshot-creation call itself, which happens inline inside
  `invitations/service.py::create_invitation` in the same transaction as the
  `Invitation` insert — see the design doc's Decision 1 for why (snapshot
  atomicity, avoiding an import cycle). This package's own `service.py`
  reuses `invitations.service.approve_invitation`/`deny_invitation` verbatim
  for finalizing/denying an invitation (Decision 2) rather than
  reimplementing either mutation.

## InvitationApprovalStep

One ordered step snapshotted onto an invitation at submission time. Most
steps are copied from the matching category's active `ApprovalWorkflowRule`
rows — a point-in-time copy, not a live reference, so editing or
deactivating a rule afterward never changes an invitation already in
flight. When the invitation's `hostId` resolves to an active user at
submission, an additional **host-identified** step is always prepended at
`stepOrder` 0, ahead of any role-identified steps — unconditional, whether
or not the category has any configured rules (see "Host as step 0" below).

Exactly one of `approverRoleId`/`approverUserId` is set per row (a `CHECK`
constraint enforces this) — a role-identified step (from a rule) sets
`approverRoleId`; the host-identified step sets `approverUserId` instead.

| Field | Notes |
|---|---|
| `id` | Returned to callers as `currentApprovalStep.id` — this is the `stepId` the approve/reject endpoints expect in their path. |
| `stepOrder` | Copied from the rule (role-identified), or `0` (host-identified). Ordering is strict — only the lowest `stepOrder` still `pending` is ever actionable. |
| `approverRoleId` | Copied from the rule (`auth.models.Role`, no ORM relationship — resolved by id only, same posture `ApprovalWorkflowRule.approver_role_id` already has). Null on a host-identified step. |
| `approverUserId` | The invitation's resolved host (`auth.models.User`), set only on the host-identified step. Null on every role-identified step. |
| `isMandatory` | Copied from the rule (always `true` for the host step). Not currently enforced by any skip logic — informational only in this change. |
| `status` | `pending` \| `approved` \| `rejected` \| `skipped` \| `auto_approved` — plain string, not a DB enum, matching `Invitation.status`'s own convention. Only `pending`/`approved`/`rejected` are ever produced by code today; `skipped`/`auto_approved` are reserved for the not-yet-built enforcement job. |
| `actedByUserId` / `actedAt` | Set when a caller approves or rejects the step. |
| `delegatedToUserId` / `delegatedByUserId` / `delegatedAt` | Set once, by the host, on the role-identified step immediately following their own (`stepOrder` 1 only) — see "Host delegation" below. Null on every other step. |
| `escalationMinutes` / `autoApproveMinutes` | Raw minute values copied from the rule at snapshot time — kept separately from the computed timestamps below because a later step needs its own duration again when it becomes current, and re-reading the live rule at that point would defeat the snapshot. |
| `escalatesAt` / `autoApprovesAt` | Computed by adding the step's own `escalationMinutes`/`autoApproveMinutes` to the moment it became the current pending step (submission time for the first step, the moment the prior step was approved for every step after it). Null when the corresponding minute value isn't configured, or the step hasn't become current yet. **Nothing currently acts on either timestamp once it passes** — see invitations.md's "Not yet built". |

`(invitationId, stepOrder)` is unique among non-deleted rows (a partial
index, same soft-delete-reuse posture as `ApprovalWorkflowRule`'s own
constraint).

## Host as step 0

The invitation's own host (`Invitation.hostId`, resolved at submission from
`hostId`/`hostNameOrEmail` — see `docs/features/invitations.md`) is always
the first approver whenever it resolves to an active user, composing with
(never replacing) the category's configured role-based chain:

- Host resolves, category has no active rules → one step, host-identified,
  `stepOrder` 0. Blanket `POST /invitations/{id}/approve` is unavailable
  (409) — same as any other snapshotted-step invitation.
- Host resolves, category has N active rules → N+1 steps: `stepOrder` 0
  (host), then the rules' own configured `stepOrder` values (1..N)
  unchanged.
- Host does not resolve, category has no active rules → no steps (unchanged
  from before this feature — blanket approve still works).

The host step never has `escalatesAt`/`autoApprovesAt` — no rule backs it,
so both stay null (consistent with "an unconfigured duration leaves its
timestamp null").

## Push notifications on step activation

Approving a non-final step activates the next one (`_activate_next_step`),
which — after the approving request's own commit — dispatches a staff
push notification to that newly-current step's approver(s): the host if
host-identified, else every holder of the step's role at the invitation's
branch. Approving the *last* step activates nothing here; the invitation's
own resolution (via `invitations.service.approve_invitation`) sends its own
push to the host instead — see `docs/features/notifications.md`.

## Endpoints

Both live under the `/invitations` path prefix (they're actions on an
invitation's own lifecycle), registered from this package's own router —
see `docs/features/invitations.md`'s endpoint table for the full
request/response reference. Summary:

| Method | Path | Auth |
|---|---|---|
| POST | `/api/v1/invitations/{id}/approval-steps/{stepId}/approve` | `invitations:approve` at the invitation's branch, **and** delegate-match, role-match, host-match, or `invitations:approve-override` |
| POST | `/api/v1/invitations/{id}/approval-steps/{stepId}/reject` | Same as above; body: `{"reason": "..."}` |
| POST | `/api/v1/invitations/{id}/approval-steps/{stepId}/delegate` | `invitations:approve` at the invitation's branch, **and** caller must be the invitation's host acting on the step immediately following their own — see "Host delegation" below; body: `{"delegateUserId": "..."}` |

## Authorization: delegate-match, role-match, host-match, or override

Holding `invitations:approve` at the invitation's branch is necessary but
not sufficient. The caller must additionally either:

- for a step with a **delegate assigned** (`delegatedToUserId` set): be
  that exact user — `caller.id == step.delegatedToUserId`. Once a step has
  a delegate, general role membership stops being a second valid path in —
  see "Host delegation" below; or
- for a **role-identified** step with no delegate assigned: hold, via a
  `UserBranchRole` grant, the exact `Role` the current step's
  `approverRoleId` names — scoped to the invitation's branch, or granted
  company-wide (`branch_id IS NULL`), matching
  `auth.models.User.has_permission`'s own branch-or-company-wide semantics;
  or
- for a **host-identified** step (`stepOrder` 0, when present): be that
  exact user — `caller.id == step.approverUserId`. No role check applies at
  all for this step kind; the step is authorized for that one person
  regardless of which role(s) they otherwise hold; or
- hold the `invitations:approve-override` permission (seeded to `admin`
  only in the default catalog), which bypasses the delegate-match,
  role-match, or host-match check entirely, for any step kind.

None of the above met → 403, whether or not the role/permission dependency
chain already passed on `invitations:approve` alone. Note this means a host
with no `invitations:approve` grant at their own branch cannot act on their
own host-identified step — provisioning hosts with that permission is an
RBAC/onboarding decision, not something this endpoint decides on its own.

## Host delegation

Once an invitation's `stepOrder` 0 host-identified step is `approved`,
making the role-identified step at `stepOrder` 1 the current pending one,
the invitation's host (the user identified by that `stepOrder` 0 step's
`approverUserId`) can delegate `stepOrder` 1 to a specific person of their
choosing, instead of leaving it open to anyone holding that step's role.

- Only the step immediately following the host's own is delegable —
  `stepOrder` 0 itself, and `stepOrder` 2+ in a 3-or-more level workflow,
  are rejected.
- The named delegate must hold the step's `approverRoleId` role at the
  invitation's branch (or company-wide) at the moment of delegation, via the
  same role-membership check a role-identified step action is authorized
  with — an ineligible delegate is rejected (422).
- A step can be delegated once; delegating an already-delegated step, or one
  that's no longer the current pending step (already acted on, or the host's
  own step isn't approved yet), is rejected (409).
- Delegating does **not** itself advance the workflow — the step stays
  `pending` until the delegate (or an `invitations:approve-override` holder)
  separately approves or rejects it. A delegate approving the last step
  finalizes the invitation exactly like any other last-step approval.

The delegate then sees the invitation in their own `GET /invitations
?relevantToMe=true` list — see `docs/features/invitations.md`.

## Not yet built

- **Escalation/auto-approve enforcement.** No scheduled job reads
  `escalatesAt`/`autoApprovesAt` and acts on them yet.
- **Resubmission after rejection.** A step rejection denies the invitation
  outright — there's no path back to `submitted`.
- **Mandatory-step skip logic.** `isMandatory` is stored but nothing
  currently skips an optional step automatically.
