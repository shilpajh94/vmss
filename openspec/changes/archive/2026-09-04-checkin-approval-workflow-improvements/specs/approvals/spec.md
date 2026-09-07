## ADDED Requirements

### Requirement: Current Step's Authorized Approver Delegates It to a Specific Person
For an invitation with a current pending `InvitationApprovalStep`, a caller
MAY delegate that step, via `POST
/invitations/{invitationId}/approval-steps/{stepId}/delegate`, to a
specific other person, at any `stepOrder` — including `stepOrder` 0 (the
host step itself) and any step beyond the one immediately following it —
provided the caller satisfies one of:
(a) the caller is the invitation's host — the user identified by its
`stepOrder` 0 host-identified step's `approverUserId` — regardless of
whether they would otherwise be authorized to act on the current step
directly. This is a blanket privilege, generalized from the prior
capability's own "the host may hand off the very next role-identified step
to someone else even without holding that role" behavior, now extended to
every step position rather than only the one immediately following the
host's;
(b) the caller otherwise satisfies one of the conditions that would
authorize them to act on the current step directly (see "Acting on a Step
Requires the Caller's Matching Role, or an Explicit Override"): matches its
currently assigned delegate (re-delegating), holds the role its
`approverRoleId` names (when no delegate is yet assigned), or — for a
host-identified step — is the person its `approverUserId` names (already
covered by clause (a) when that person is the invitation's own host, but
this also covers a *different* host-identified step were one ever to
exist); or
(c) the caller holds `invitations:approve-override`.
The named delegate SHALL satisfy the step's own eligibility: for a
role-identified step, the delegate SHALL hold the step's `approverRoleId`
role at the invitation's branch or company-wide; for a host-identified step
(`stepOrder` 0), the delegate SHALL hold `invitations:approve` at the
invitation's branch. A step that already has a delegate assigned MAY be
re-delegated — by its current delegate, by the invitation's host (clause
a), or by an override-permission holder (clause c) — to a different
specific person, overwriting the prior delegate rather than accumulating
multiple delegates for one step; this chaining is what makes delegation
genuinely multi-level rather than a single hop. Delegating a step that is
not currently the invitation's current pending step, that has already been
acted on (approved/rejected), or that belongs to an invitation with no
snapshotted approval steps at all, SHALL be rejected with 409 and SHALL NOT
record any delegation. A caller satisfying none of (a)-(c) for that step
SHALL be rejected with 403. A successful delegation SHALL record the
delegate, the delegating user, and the timestamp; it does not itself change
the step's `pending` status or the invitation's overall status — the
delegate must still separately approve or reject it (or delegate it onward
again).

#### Scenario: Host delegates their own step to another person
- **WHEN** the host of an invitation — currently the only one authorized to
  act on its `stepOrder` 0 step — calls the delegate endpoint on that same
  step, naming a person who holds `invitations:approve` at the invitation's
  branch
- **THEN** the delegation succeeds, the step remains `pending`, and the
  named delegate — not the original host — becomes the one who can approve
  or reject `stepOrder` 0

#### Scenario: Host delegates a later role-identified step without holding its role
- **WHEN** the invitation's host, who does not hold the role its current
  pending `stepOrder` 2 step names, calls the delegate endpoint on that
  step, naming a person who does hold that role at the invitation's branch
- **THEN** the delegation succeeds — the host's delegation privilege does
  not require the host to be independently authorized to act on the step
  being delegated

#### Scenario: A role-holder delegates a later step, not just the one after the host's
- **WHEN** a user who is not the invitation's host, but is currently
  authorized (by role match) to act on a `stepOrder` 2 step of a
  multi-level workflow, calls the delegate endpoint on it, naming another
  user who holds that step's role at the invitation's branch
- **THEN** the delegation succeeds regardless of the step's position in the
  sequence

#### Scenario: A delegate re-delegates the step onward, chaining the delegation
- **WHEN** a step already has a delegate assigned, and that delegate calls
  the delegate endpoint again, naming a third person who also satisfies the
  step's own eligibility
- **THEN** the delegation is updated to the third person, superseding the
  prior delegate, and the step remains `pending`

#### Scenario: Host re-delegates an already-delegated step
- **WHEN** the invitation's host calls the delegate endpoint on a step that
  already has a different delegate assigned, naming a new person who
  satisfies the step's own eligibility
- **THEN** the delegation succeeds and is updated to the new person — the
  host's blanket privilege persists even after a step has already been
  delegated to someone else, not just at the moment it first becomes
  current

#### Scenario: Override-permission holder delegates any step regardless of role or host match
- **WHEN** a caller holds `invitations:approve` and
  `invitations:approve-override` at the invitation's branch, and calls the
  delegate endpoint on the current pending step
- **THEN** the delegation succeeds regardless of whether the caller's own
  role, user id, or existing delegate status would otherwise authorize them
  on that step

#### Scenario: Caller not currently authorized on the step is rejected
- **WHEN** a caller who is not the invitation's host, does not match the
  current step's role, is not its currently assigned delegate, and does
  not hold `invitations:approve-override` calls the delegate endpoint
- **THEN** the request is rejected with 403 and no delegation is recorded

#### Scenario: Delegating a step that is not currently pending is rejected
- **WHEN** a caller attempts to delegate a step that is not the invitation's
  current pending step (already acted on, or not yet reached)
- **THEN** the request is rejected with 409 and no delegation is recorded

#### Scenario: Named delegate not eligible for the step is rejected
- **WHEN** a caller names a delegate who does not hold the step's
  `approverRoleId` role (for a role-identified step) or does not hold
  `invitations:approve` at the invitation's branch (for the host-identified
  step)
- **THEN** the request is rejected and no delegation is recorded

## REMOVED Requirements

### Requirement: Host Delegates the Step Following Their Own to a Specific Person
**Reason**: Delegation is generalized from "only the host, only the single
role-identified step immediately after their own, one time" to "whoever is
currently authorized to act on the current pending step, at any step
position, re-delegable" — see "Current Step's Authorized Approver Delegates
It to a Specific Person" — so a genuine multi-level delegation chain is
possible instead of one fixed hop, per explicit product direction.
**Migration**: `POST
/invitations/{invitationId}/approval-steps/{stepId}/delegate` keeps its
URL, method, and request/response shape. Only eligibility changes: a
caller previously rejected under the old host-only/next-step-only/
one-shot restriction may now succeed. No caller that previously succeeded
under the old rule is rejected under the new one — the new rule is a strict
superset of who may delegate and which steps are delegable.
