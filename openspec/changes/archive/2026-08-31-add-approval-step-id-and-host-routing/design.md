## Context

See `proposal.md` - Why for motivation. Current state, established by research
into the running code:

- `InvitationApprovalStep` (`approvals/models.py`) already has `approver_role_id`
  as a **non-nullable** FK to `roles`, plus `step_order`, `status`,
  `is_mandatory`, `acted_by_user_id`, `escalates_at`/`auto_approves_at`. No ORM
  relationships (column-only), by existing design.
- `Invitation.host_id` (`invitations/models.py`) already exists as a **nullable**
  FK to `users`, and `invitations/service.py` already resolves it from a
  submitted `hostId` (or matches `hostNameOrEmail`) at submission time,
  overwriting `host_name_or_email` with the resolved user's `full_name`. This
  column is persisted today but never surfaced on output and never consulted by
  approval-step snapshotting.
- `CurrentApprovalStepOut` (embedded in `InvitationOut`/`InvitationDetailOut`/
  `InvitationTrackingOut`) deliberately omits `id` today (see its docstring,
  design.md Decision 7 of the invitations change that introduced it) — the data
  is already loaded in the service (`get_current_approval_step`), just not
  serialized.
- Step-action authorization (`approvals/service.py::_authorize_step_action`) is
  purely role-keyed: it checks `invitations:approve` at the branch, then either a
  `UserBranchRole` match against `step.approver_role_id` or the
  `invitations:approve-override` permission.
- The user already chose, when this proposal was raised, that host-approval and
  role-based workflow steps **compose** rather than one replacing the other:
  a resolved host always gets an implicit `stepOrder` 0 step, and any configured
  `ApprovalWorkflowRule` chain runs afterward unchanged. This decision is fixed
  for this change - see specs/approvals/spec.md.

## Goals / Non-Goals

**Goals:**
- Let the frontend obtain a step's `id` from the same invitation payload it
  already fetches, so it can call the approve/reject endpoints without a new
  round trip.
- Let the frontend see which user (if any) an invitation's host resolved to.
- Route the first approval step to the invitation's host, composing with
  (not replacing) any category-configured role-based chain.
- Keep the change additive on the wire (new fields only) except for the
  step-sequence behavior change the composition decision necessarily causes.

**Non-Goals:**
- No per-category toggle for "host step on/off" — the host step is
  unconditional whenever the host resolves, for every category. A future
  change can add an opt-out if a real use case needs it.
- No change to how `hostId`/`hostNameOrEmail` is resolved at submission — that
  logic (`invitations/service.py:99-104`) is reused as-is.
- No escalation/auto-approve timing for the host step in this change (see
  Decisions below) — it stays consistent with the approvals capability's
  existing "computed but not enforced" posture.
- No RBAC/provisioning change to grant hosts `invitations:approve` — that
  permission is still required to act on any step, host-identified or not (see
  Risks).

## Decisions

**Schema change: `approver_role_id` becomes nullable; new nullable
`approver_user_id`, exactly one set per row.**
Alternative considered: a separate `approver_kind` discriminator column
(`"role" | "user"`) alongside a single polymorphic `approver_id`. Rejected —
two distinct, separately-FK'd columns are simpler to query, index, and
constrain (`ForeignKey("roles.id")` / `ForeignKey("users.id")` each keep
referential integrity that a polymorphic id column can't express in Postgres
without a trigger. A `CHECK` constraint enforces exactly one is non-null.

**Host step is always `stepOrder` 0; role-configured steps keep their
existing `stepOrder` (starting at 1 by convention).**
Alternative considered: renumbering role steps to start at 2 when a host step
is inserted. Rejected — the existing convention already has rules configured
starting at `stepOrder` 1 (see the approvals spec's existing scenarios), so
reserving 0 for the host avoids any renumbering logic and keeps
`ApprovalWorkflowRule.step_order` a stable, rule-owned value unaffected by
whether a given invitation happens to have a resolved host.

**Authorization: host-match is a new, independent branch alongside the
existing role-match, both still gated by `invitations:approve`.**
`_authorize_step_action` gains: if `step.approver_user_id is not None`, check
`caller.id == step.approver_user_id`, else fall through to the existing
role-match logic; `invitations:approve-override` continues to bypass both.
This keeps the override permission's meaning ("bypass whatever the normal
match rule is") consistent regardless of step kind.

**`id` is exposed on the shared `CurrentApprovalStepOut`, used by all three
output schemas (`InvitationOut`, `InvitationDetailOut`, and the
unauthenticated `InvitationTrackingOut`) — not forked into a staff-only
variant.**
Alternative considered: keep `InvitationTrackingOut` on the current minimal
shape (per its own docstring's original rationale) and add `id` only to a new
schema used by `InvitationOut`/`InvitationDetailOut`. Rejected for this
change — knowing a step's `id` grants no privilege by itself: both mutating
endpoints still independently require authentication, `invitations:approve`,
and a role/host/override match. Forking the schema would add a second type to
keep in sync for no security benefit. This is easily reversed later if the
team wants the public tracking response to stay minimal.

**`CurrentApprovalStepOut.approverRoleId` becomes nullable; new nullable
`approverUserId` — mirroring the model's now-nullable/new columns.**
Follows directly from the model change; exactly one of the two is non-null
per the same invariant.

**Host step's `escalates_at`/`auto_approves_at` are left null.**
There is no `ApprovalWorkflowRule` backing a host step to source
`escalationMinutes`/`autoApproveMinutes` from, and the approvals capability's
existing requirement already treats these fields as informational-only,
computed-but-not-enforced. Leaving them null is consistent with "an
unconfigured duration leaves its timestamp null" and doesn't foreclose adding
a per-tenant configurable host-escalation window later.

## Risks / Trade-offs

- **[Risk] A host who is not otherwise granted `invitations:approve` at the
  invitation's branch cannot act on their own host-approval step, even though
  they are named as its approver.** → Not mitigated by this change; the
  permission model is unchanged on purpose (this change adds a new *match*
  condition, not a new permission bypass). Flagging this explicitly: rolling
  this out is only useful once hosts are provisioned with `invitations:approve`
  at their branch, which is an RBAC/onboarding decision for whoever owns
  tenant role assignments, not something this change can decide.
- **[Risk] Behavior change for existing zero-rule categories.** Any invitation
  whose host resolves and whose category has no configured workflow rules
  moves from "no steps, blanket single-approve available" to "one step,
  approvable only via the step endpoint." → Mitigated by calling this out as
  **BREAKING** in the proposal and covering both the old and new precondition
  in the `invitations` capability's modified requirement and its test
  coverage (`testing-standards.md` §2).
- **[Risk] Migration must apply to every tenant schema, not just one.** →
  Follow the established `alembic_tenant` process
  (`database-architecture.md` §5): author once, apply via the existing
  per-tenant upgrade path; no autogenerate-per-tenant loop.

## Migration Plan

1. `alembic_tenant` revision: alter `invitation_approval_steps` —
   `approver_role_id` becomes nullable, add nullable `approver_user_id`
   (`ForeignKey("users.id")`), add a `CHECK` constraint that exactly one of
   `approver_role_id`/`approver_user_id` is non-null. Existing rows are
   unaffected (they already have `approver_role_id` set, `approver_user_id`
   null, satisfying the constraint) — no backfill needed.
2. Apply the migration to every existing tenant schema per the standard
   per-tenant upgrade path.
3. Ship the model/schema/service changes and the new spec requirements
   together with the migration — there is no dual-write/rollout window needed
   since the new column defaults to null and old code paths (role-only steps)
   keep working unchanged.
4. Rollback: a down-migration drops the `CHECK` constraint and the
   `approver_user_id` column and restores `approver_role_id` to non-nullable —
   safe only if no row has been created with `approver_user_id` set and
   `approver_role_id` null (i.e., before this change's step-snapshot logic
   ships). Document this ordering constraint in the migration file itself.
