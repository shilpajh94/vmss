# Approvals

Runtime evaluation of a `VisitorCategory`'s configured `ApprovalWorkflowRule`
chain (`docs/features/visitors.md`) against an actual submitted invitation
(`docs/features/invitations.md`) — the piece both of those docs previously
flagged as "not yet built." Everything here is tenant-scoped by schema
(`Base`, not `GlobalBase`).

See `openspec/changes/invitation-multi-step-approval/` for the
proposal/spec/design this feature was built from.

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

One ordered step snapshotted onto an invitation at submission time, copied
from the matching category's active `ApprovalWorkflowRule` rows — a
point-in-time copy, not a live reference, so editing or deactivating a rule
afterward never changes an invitation already in flight.

| Field | Notes |
|---|---|
| `stepOrder` | Copied from the rule; ordering is strict — only the lowest `stepOrder` still `pending` is ever actionable. |
| `approverRoleId` | Copied from the rule (`auth.models.Role`, no ORM relationship — resolved by id only, same posture `ApprovalWorkflowRule.approver_role_id` already has). |
| `isMandatory` | Copied from the rule. Not currently enforced by any skip logic — informational only in this change. |
| `status` | `pending` \| `approved` \| `rejected` \| `skipped` \| `auto_approved` — plain string, not a DB enum, matching `Invitation.status`'s own convention. Only `pending`/`approved`/`rejected` are ever produced by code today; `skipped`/`auto_approved` are reserved for the not-yet-built enforcement job. |
| `actedByUserId` / `actedAt` | Set when a caller approves or rejects the step. |
| `escalationMinutes` / `autoApproveMinutes` | Raw minute values copied from the rule at snapshot time — kept separately from the computed timestamps below because a later step needs its own duration again when it becomes current, and re-reading the live rule at that point would defeat the snapshot. |
| `escalatesAt` / `autoApprovesAt` | Computed by adding the step's own `escalationMinutes`/`autoApproveMinutes` to the moment it became the current pending step (submission time for the first step, the moment the prior step was approved for every step after it). Null when the corresponding minute value isn't configured, or the step hasn't become current yet. **Nothing currently acts on either timestamp once it passes** — see invitations.md's "Not yet built". |

`(invitationId, stepOrder)` is unique among non-deleted rows (a partial
index, same soft-delete-reuse posture as `ApprovalWorkflowRule`'s own
constraint).

## Endpoints

Both live under the `/invitations` path prefix (they're actions on an
invitation's own lifecycle), registered from this package's own router —
see `docs/features/invitations.md`'s endpoint table for the full
request/response reference. Summary:

| Method | Path | Auth |
|---|---|---|
| POST | `/api/v1/invitations/{id}/approval-steps/{stepId}/approve` | `invitations:approve` at the invitation's branch, **and** role-match or `invitations:approve-override` |
| POST | `/api/v1/invitations/{id}/approval-steps/{stepId}/reject` | Same as above; body: `{"reason": "..."}` |

## Authorization: role-match or override

Holding `invitations:approve` at the invitation's branch is necessary but
not sufficient. The caller must additionally either:

- hold, via a `UserBranchRole` grant, the exact `Role` the current step's
  `approverRoleId` names — scoped to the invitation's branch, or granted
  company-wide (`branch_id IS NULL`), matching
  `auth.models.User.has_permission`'s own branch-or-company-wide semantics; or
- hold the `invitations:approve-override` permission (seeded to `admin`
  only in the default catalog), which bypasses the role-match check
  entirely.

Neither condition met → 403, whether or not the role/permission dependency
chain already passed on `invitations:approve` alone.

## Not yet built

- **Escalation/auto-approve enforcement.** No scheduled job reads
  `escalatesAt`/`autoApprovesAt` and acts on them yet.
- **Resubmission after rejection.** A step rejection denies the invitation
  outright — there's no path back to `submitted`.
- **Mandatory-step skip logic.** `isMandatory` is stored but nothing
  currently skips an optional step automatically.
