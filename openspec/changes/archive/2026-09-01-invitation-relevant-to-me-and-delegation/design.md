## Context

`InvitationApprovalStep` (`src/vmss_api/approvals/models.py`) already carries
an XOR pair — exactly one of `approver_role_id` / `approver_user_id` is set
per step — introduced for the host-routing case (`stepOrder=0` only). Step
action authorization lives in `approvals/service.py::_authorize_step_action`
(role match via `_user_holds_role_at_branch`, or exact `approver_user_id`
match for host steps, or the `invitations:approve-override` bypass).
`GET /invitations` (`invitations/router.py`, `service.py`, `repository.py`)
is filtered exclusively through `require_branch_scope("invitations:view")`
— there is no path today for a caller to see an invitation without that
branch-scoped permission. See proposal.md for why both gaps matter to the
frontend team's "relevant to me" inbox.

## Goals / Non-Goals

**Goals:**
- Let a host (and, once delegated, a delegate) find their invitations via
  `GET /invitations?relevantToMe=true` without needing `invitations:view`.
- Let a host hand the step right after their own to a specific person,
  reusing the existing role-membership check to validate that person is
  eligible.
- Keep the existing strict step-order / finalization / rejection-is-terminal
  behavior completely unchanged — delegation only changes *who* may act on
  one step.

**Non-Goals:**
- Delegating any step other than the one immediately following the host's
  own (`stepOrder=1`) — confirmed out of scope with the user; step
  `stepOrder=2+` always follows plain role-based authorization.
- Delegating the host's own `stepOrder=0` step, or letting anyone other than
  the host initiate a delegation.
- A generic "assign any user to any step at creation time" mechanism —
  `approver_user_id` at creation remains host-only, exactly as today.
- Un-delegating / re-delegating a step, or delegate handoff chains
  (delegate-of-a-delegate). One delegation per step, set once, is all this
  change supports; re-delegation attempts are rejected (see spec).
- Extending `relevantToMe` to plain role-based "pending my approval because
  I hold this role" invitations — that's a materially broader feature the
  frontend team did not ask for here.

## Decisions

### Decision: Add `delegated_to_user_id` / `delegated_by_user_id` / `delegated_at` columns rather than repurposing `approver_user_id`
Repurposing `approver_user_id` (setting it on the `stepOrder=1` row instead
of `approver_role_id`) would violate the existing XOR check constraint's
intent and would make it impossible to tell, later, "who was the role
originally assigned to vs. who was delegated" — useful for audit and for
the `_authorize_step_action` fallback (a delegated step's `approver_role_id`
is still meaningful context, just no longer the sole gate). Three new
nullable columns on `InvitationApprovalStep`
(`delegated_to_user_id FK users.id`, `delegated_by_user_id FK users.id`,
`delegated_at`) keep the original role/host snapshot intact and add
delegation as an orthogonal, auditable fact layered on top.

Alternative considered: a separate `InvitationApprovalStepDelegation` audit
table. Rejected as premature — a step is delegated at most once in this
change's scope (no re-delegation), so three columns on the step itself carry
the same information with one less join, and the columns still satisfy
`security-architecture.md` §5's "who, when" audit expectation for this
specific mutation. The append-only `AuditLog` table is still written to for
the mutating action itself (delegation is a mutation, same as approve/
reject), consistent with the project's blanket audit-trail rule.

### Decision: Delegation eligibility check reuses `_user_holds_role_at_branch`, not a new role-check path
The same function that authorizes a role-identified step action already
answers "does this user hold this role at this branch (or company-wide)."
Delegation validation calls it with the *candidate delegate* instead of the
caller, at delegation time. No new role-resolution logic is introduced.

### Decision: `_authorize_step_action` checks the delegate before falling back to the role match
When `delegated_to_user_id` is set on the current step, only that user (or
an override-permission holder) may act — the step's `approver_role_id` role
match is bypassed entirely, not just supplemented. This matches the spec's
"the step is authorized for that specific person" language already used for
host-identified steps, applied consistently to delegated steps: once a
specific person is named, general role membership stops being a second
valid path in, avoiding an ambiguous "who actually approved this" audit
trail if two different role-holders raced to act.

### Decision: `relevantToMe` is implemented as a distinct query path, not a `require_branch_scope` variant
`require_branch_scope` answers "which branches is this caller authorized to
view at" and 403s on an empty set. `relevantToMe` answers a different
question entirely ("which invitations name this caller specifically") that
has nothing to do with branch permission grants, so it bypasses that
dependency's check rather than trying to make one dependency serve both
questions. The repository query becomes an `OR` across two joins: invitation
IDs whose `stepOrder=0` step's `approver_user_id` matches the caller, unioned
with invitation IDs where any step's `delegated_to_user_id` matches the
caller — both are simple indexed lookups against `invitation_approval_steps`
foreign-keyed columns, no N+1 risk (`query-performance.md` §1-2).
`relevantToMe=true` and the branch-scoped path are mutually exclusive for a
given request: when `relevantToMe` is set, `X-Branch-ID` and the
`invitations:view` check are skipped entirely for that request, per the
spec's "ADDED Requirements" scenario.

### Decision: One new endpoint (`POST .../approval-steps/{stepId}/delegate`), not a field on the approve/reject payload
Delegation is a distinct action with its own eligibility rules (host-only,
step-order-1-only, target-must-hold-role) and its own terminal state
question (has this step already been delegated?) — folding it into the
approve/reject request body would conflate "acting on a step" with "handing
it off," and would make the 409 semantics ("already delegated" vs. "already
acted on") harder to keep distinct in one response shape. A sibling
endpoint next to `approve`/`reject` matches the existing router shape in
`approvals/router.py`.

## Risks / Trade-offs

- **[Risk]** A host could be tempted to expect delegation available on
  *any* pending step (e.g. `stepOrder=2` in a 3-level workflow), since the
  UI mockup may not obviously communicate the "only the very next step"
  restriction → **Mitigation**: the delegate endpoint returns a clear
  rejection (not a silent no-op) naming the reason when called on an
  ineligible step, so the frontend can surface it immediately rather than
  the request appearing to hang.
- **[Risk]** `relevantToMe` bypassing `invitations:view` is a deliberate,
  narrow authorization carve-out; a future contributor unfamiliar with this
  decision could "fix" it by adding the permission check back, silently
  breaking hosts with no view grant → **Mitigation**: the spec scenario "Host
  sees their own invitation without invitations:view" makes this explicit
  and testable, and the design decision above records the reasoning inline
  next to the code it justifies (service/repository docstring pointing at
  this design doc's decision).
- **[Trade-off]** Three new nullable columns instead of a separate
  delegation table means the `invitation_approval_steps` table carries
  columns that are null for every step except the rare delegated one —
  acceptable given the low cardinality of delegation events and the
  simplicity win of avoiding a join for the common case (reading a step's
  current authorization state).

## Migration Plan

- New Alembic migration under `alembic_tenant/versions/` adding the three
  nullable columns (no backfill needed — every existing row has no
  delegation). Applied per-tenant the same way every tenant migration is
  (`platform/service.py::create_tenant` / an "upgrade all tenants" op task),
  per `database-architecture.md` §5.
- Purely additive: no existing column, endpoint, or response field changes
  shape or semantics, so no coordinated frontend/backend rollout ordering is
  required beyond "the frontend can start calling the new endpoint/param
  once this ships."
- Rollback: drop the migration; the delegate endpoint and `relevantToMe`
  param simply stop being reachable (no data-loss concern since the columns
  are purely additive metadata, not the source of truth for step status).
