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
flight. `stepOrder` 0 is always the **ownership step**, role-identified for
the tenant's default host role — see "The ownership step" below
(`role-based-invitation-workflow` — replaces the old "host-identified when
a client-supplied `hostId` resolved" behavior).

Exactly one of `approverRoleId`/`approverUserId` is set per row (a `CHECK`
constraint enforces this) — a role-identified step (from a rule, or the
ownership step before it's delegated) sets `approverRoleId`; a
host-identified step sets `approverUserId` instead. New invitations only
ever produce a host-identified step via delegation now (see "The ownership
step" below) — a genuinely host-identified step at snapshot time is legacy
data from before this change, still handled the same way it always was
(both kinds share the exact same authorization/delegation logic below).

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

## The ownership step (`stepOrder` 0)

`stepOrder` 0 is **always** created, unconditionally, for every submitted
(non-auto-approved) invitation, role-identified for the tenant's default
host role (`Company.defaultHostRoleId`, falling back to the standard
`reception` role) — composing with (never replacing) the category's own
configured role-based chain:

- Category has no active rules → one step: `stepOrder` 0 (the ownership
  role), and nothing else. Blanket `POST /invitations/{id}/approve` is
  unavailable (409) for **every** newly submitted invitation now — there is
  no longer a "no snapshotted steps" case to fall back to it.
- Category has N active rules → N+1 steps: `stepOrder` 0 (the ownership
  role), then the rules' own configured `stepOrder` values (1..N) unchanged.

The ownership step never has `escalatesAt`/`autoApprovesAt` — no rule backs
it, so both stay null (consistent with "an unconfigured duration leaves its
timestamp null"). It's role-identified, not host-identified, at snapshot
time — the invitation has no resolved host yet at this point. The actual
host is established afterward by **delegating** any step — this one or a
later one in the workflow chain (see "Delegation" below) — doing so also
sets the invitation's `hostId`/`hostNameOrEmail`
(`docs/features/invitations.md`) in the same transaction, and notifies the
newly-named host (push, and a `"You've been named host"` email —
`invitations/tasks.py::send_host_creation_notification`, repurposed from
firing at creation to firing on this delegation instead). Delegating a
later step supersedes whichever host was previously resolved — the
invitation's host always reflects the most recent delegation, at any
`stepOrder`, not just this one.

**Approvable directly, same as any other step**: `stepOrder` 0 has no
special approval gate — the owning-role holder (e.g. `reception`) may
`approve` it directly, exactly as they would `delegate` it, the same
role-match authorization every other step uses. Approving it directly just
means no host ever gets resolved from that step (`hostId` stays null unless
some step is delegated); a caller who wants to name a specific host still
uses `delegate`, not `approve`. Once delegated, the named delegate approves
the step like any other current pending step.

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
| POST | `/api/v1/invitations/{id}/approval-steps/{stepId}/delegate` | `invitations:approve` at the invitation's branch, **and** delegate-match, role-match, the invitation's resolved host (any step position), or `invitations:approve-override` — see "Delegation" below; body: `{"delegateUserId": "..."}` |

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
- for a **host-identified** step (only ever produced by delegating the
  ownership step, or on legacy pre-migration data — see "The ownership
  step" above): be that exact user — `caller.id == step.approverUserId`. No
  role check applies at all for this step kind; the step is authorized for
  that one person regardless of which role(s) they otherwise hold; or
- hold the `invitations:approve-override` permission (seeded to `admin`
  only in the default catalog), which bypasses the delegate-match,
  role-match, or host-match check entirely, for any step kind.

None of the above met → 403, whether or not the role/permission dependency
chain already passed on `invitations:approve` alone. Note this means a host
with no `invitations:approve` grant at their own branch cannot act on their
own host-identified step — provisioning hosts with that permission is an
RBAC/onboarding decision, not something this endpoint decides on its own.

## Delegation

The invitation's **current pending step, at any `stepOrder`** — not just the
one immediately after another — can be delegated to a specific person
instead of being left open to anyone holding that step's role. A caller may
delegate if they are:

- the invitation's already-**resolved host** (its `hostId`) — a blanket
  privilege across every step position, once a host has been resolved. This
  is how a host can hand a later step to someone else even if they don't
  hold that step's own role. Before a host has been resolved (the common
  case right after submission, since `stepOrder` 0 now starts
  role-identified — see "The ownership step" above), this clause doesn't
  apply yet; or
- otherwise already authorized to act on the current step directly
  (role-match, or the step's existing delegate re-delegating onward); or
- an `invitations:approve-override` holder, for any step regardless of role
  or host match; or
- the one who **personally approved the immediately preceding step**
  (`stepOrder - 1`) — regardless of whether they hold the current step's own
  role. This lets Reception, having approved the ownership step directly
  (without delegating it), hand the workflow's next configured step
  straight to whoever should act on it, rather than waiting for a holder of
  that role to notice it themselves
  (`reception-retains-visibility-and-delegation-after-own-step`). It only
  ever reaches back one step — approving `stepOrder` 1 doesn't grant any
  privilege over `stepOrder` 3 once `stepOrder` 2 has also been approved by
  someone else — and never applies to `stepOrder` 0 itself (no preceding
  step exists).

**Named-delegate eligibility** depends on which step is being delegated:

- **`stepOrder` 0 (the ownership step)**: the delegate need only hold
  `invitations:approve` at the invitation's branch — **not** the step's own
  `approverRoleId` role. This is the one deliberate exception
  (`role-based-invitation-workflow`): the real host is normally not a
  front-office employee, so requiring them to hold the default host role
  would defeat the point of delegating ownership to them in the first
  place.
- **Every other role-identified step** (the category's own configured
  chain, `stepOrder` 1+): the delegate must hold that step's
  `approverRoleId` role at the invitation's branch (or company-wide) — the
  original, unchanged rule.

**Every** delegation — at any `stepOrder`, first or repeat — also
resolves/updates the invitation's `hostId`/`hostNameOrEmail` to that
delegate and fires the same host-assigned notification (extended from the
original `stepOrder`-0-only rule; see "The ownership step" above). The
host always reflects the most recently delegated step, so delegating a
later step in the chain supersedes whoever was resolved as host before.

A step can be re-delegated any number of times — each delegation overwrites
the prior one rather than accumulating multiple delegates. Delegating a step
that isn't currently the invitation's pending step (already acted on, or
not yet reached), or naming an ineligible delegate, is rejected (409/422
respectively). Delegating does **not** itself advance the workflow — the
step stays `pending` until the delegate (or an `invitations:approve-
override` holder) separately approves or rejects it. A delegate approving
the last step finalizes the invitation exactly like any other last-step
approval.

The delegate then sees the invitation in their own `GET /invitations
?relevantToMe=true` list — see `docs/features/invitations.md`.

## Not yet built

- **Escalation/auto-approve enforcement.** No scheduled job reads
  `escalatesAt`/`autoApprovesAt` and acts on them yet.
- **Resubmission after rejection.** A step rejection denies the invitation
  outright — there's no path back to `submitted`.
- **Mandatory-step skip logic.** `isMandatory` is stored but nothing
  currently skips an optional step automatically.
