## MODIFIED Requirements

### Requirement: Current Step's Authorized Approver Delegates It to a Specific Person
For an invitation with a current pending `InvitationApprovalStep`, a caller
MAY delegate that step, via `POST
/invitations/{invitationId}/approval-steps/{stepId}/delegate`, to a
specific other person, at any `stepOrder` — including `stepOrder` 0 (the
ownership step) and any step beyond the one immediately following it —
provided the caller satisfies one of:
(a) the caller is the invitation's currently resolved host (its `hostId` —
see the `invitations` capability's "Invitation Output Surfaces the Resolved
Host as hostId"), if one has been resolved — regardless of whether they
would otherwise be authorized to act on the current step directly. This is
a blanket privilege, extended to every step position rather than only the
one immediately following the ownership step's. Before a host has been
resolved (the common case for a freshly submitted invitation, since
`stepOrder` 0 now starts role-identified rather than host-identified), this
clause simply does not apply yet — clause (b) below is what lets any
holder of the owning role delegate `stepOrder` 0 to the real host in the
first place;
(b) the caller otherwise satisfies one of the conditions that would
authorize them to act on the current step directly (see "Acting on a Step
Requires the Caller's Matching Role, or an Explicit Override"): matches its
currently assigned delegate (re-delegating), or holds the role its
`approverRoleId` names (when no delegate is yet assigned); or
(c) the caller holds `invitations:approve-override`.
The named delegate's own eligibility depends on which step is being
delegated: for `stepOrder` 0 (the ownership step, role-identified for the
tenant's default host role), the delegate SHALL hold `invitations:approve`
at the invitation's branch — the delegate need NOT hold the default host
role itself, since the real host is normally not a front-office employee;
this is the one exception to the general rule. For every other
role-identified step (the category's own configured chain, `stepOrder` 1
and beyond), the delegate SHALL hold that step's `approverRoleId` role at
the invitation's branch or company-wide, unchanged from before. A step that
already has a delegate assigned MAY be re-delegated — by its current
delegate, by the invitation's resolved host once one exists (clause a), or
by an override-permission holder (clause c) — to a different specific
person, overwriting the prior delegate rather than accumulating multiple
delegates for one step. Delegating a step that is not currently the
invitation's current pending step, that has already been acted on
(approved/rejected), or that belongs to an invitation with no snapshotted
approval steps at all, SHALL be rejected with 409 and SHALL NOT record any
delegation. A caller satisfying none of (a)-(c) for that step SHALL be
rejected with 403. A successful delegation SHALL record the delegate, the
delegating user, and the timestamp; it does not itself change the step's
`pending` status or the invitation's overall status — the delegate must
still separately approve or reject it (or delegate it onward again). WHEN
the delegated step is `stepOrder` 0, delegation additionally resolves the
invitation's host (see "Delegating the Ownership Step Also Resolves the
Invitation's Host").

#### Scenario: Host delegates their own step to another person
- **WHEN** the invitation's already-resolved host — currently authorized to
  act on its `stepOrder` 0 step via clause (a) — calls the delegate endpoint
  on that same step, naming a person who holds `invitations:approve` at the
  invitation's branch
- **THEN** the delegation succeeds, the step remains `pending`, and the
  invitation's resolved host updates to the new delegate

#### Scenario: Host delegates a later role-identified step without holding its role
- **WHEN** the invitation's resolved host, who does not hold the role its
  current pending `stepOrder` 2 step names, calls the delegate endpoint on
  that step, naming a person who does hold that role at the invitation's
  branch
- **THEN** the delegation succeeds — the resolved host's delegation
  privilege does not require them to be independently authorized to act on
  the step being delegated

#### Scenario: A role-holder delegates a later step, not just the one after the host's
- **WHEN** a user who is not the invitation's resolved host, but is currently
  authorized (by role match) to act on a `stepOrder` 2 step of a
  multi-level workflow, calls the delegate endpoint on it, naming another
  user who holds that step's role at the invitation's branch
- **THEN** the delegation succeeds regardless of the step's position in the
  sequence, and this step's delegate eligibility is unchanged from before
  (the named delegate must hold that step's role — the `stepOrder` 0
  exception below does not apply here)

#### Scenario: Host re-delegates an already-delegated step
- **WHEN** the invitation's resolved host calls the delegate endpoint on a
  step that already has a different delegate assigned, naming a new person
  who satisfies the step's own eligibility
- **THEN** the delegation succeeds and is updated to the new person — the
  resolved host's blanket privilege persists even after a step has already
  been delegated to someone else, not just at the moment it first becomes
  current

#### Scenario: A holder of the owning role delegates the ownership step to the real host
- **WHEN** a user holding the tenant's default host role at an invitation's
  branch — with no host yet resolved for that invitation — calls the
  delegate endpoint on its `stepOrder` 0 step, naming a person who holds
  `invitations:approve` at the branch but does not hold the default host
  role
- **THEN** the delegation succeeds even though the named delegate does not
  hold the step's `approverRoleId` role — this is the exception this change
  introduces for `stepOrder` 0 specifically

#### Scenario: A delegate re-delegates the step onward, chaining the delegation
- **WHEN** a step already has a delegate assigned, and that delegate calls
  the delegate endpoint again, naming a third person who also satisfies the
  step's own eligibility
- **THEN** the delegation is updated to the third person, superseding the
  prior delegate, and the step remains `pending`

#### Scenario: Override-permission holder delegates any step regardless of role or host match
- **WHEN** a caller holds `invitations:approve` and
  `invitations:approve-override` at the invitation's branch, and calls the
  delegate endpoint on the current pending step
- **THEN** the delegation succeeds regardless of whether the caller's own
  role, user id, or existing delegate status would otherwise authorize them
  on that step

#### Scenario: Caller not currently authorized on the step is rejected
- **WHEN** a caller who is not the invitation's resolved host, does not
  match the current step's role, is not its currently assigned delegate,
  and does not hold `invitations:approve-override` calls the delegate
  endpoint
- **THEN** the request is rejected with 403 and no delegation is recorded

#### Scenario: Delegating a step that is not currently pending is rejected
- **WHEN** a caller attempts to delegate a step that is not the invitation's
  current pending step (already acted on, or not yet reached)
- **THEN** the request is rejected with 409 and no delegation is recorded

#### Scenario: Named delegate not eligible for the step is rejected
- **WHEN** a caller names a delegate who does not hold a `stepOrder` 1-or-
  later step's `approverRoleId` role at the invitation's branch or
  company-wide
- **THEN** the request is rejected and no delegation is recorded

#### Scenario: Named delegate lacking invitations:approve for the ownership step is rejected
- **WHEN** a caller delegates `stepOrder` 0 to a person who does not hold
  `invitations:approve` at the invitation's branch
- **THEN** the request is rejected and no delegation is recorded, even
  though holding the default host role itself is not required for this step

#### Scenario: Delegation alone does not advance the workflow
- **WHEN** a delegation is successfully recorded on the current pending
  step
- **THEN** the step's status remains `pending`, the invitation's overall
  status is unchanged, and the workflow only advances once the delegate (or
  an override-permission holder) actually approves or rejects the step

#### Scenario: Delegate action finalizes the workflow the same as any other last step
- **WHEN** the delegated step is the invitation's last step and the
  delegate approves it
- **THEN** the invitation transitions to `approved` exactly as it would if
  a role-holding, non-delegated approver had acted on that same step

## REMOVED Requirements

### Requirement: Submission Snapshots the Category's Active Workflow Into Ordered Steps
**Reason**: `stepOrder` 0 is no longer conditional on a client-supplied host
resolving — it is now unconditionally created for every submitted invitation,
role-identified for the tenant's default host role. The old requirement's
scenarios described a step count and a host/no-host branching (e.g. "three
active rules snapshots three ordered steps", "a resolved host with no
configured rules creates a single host-approval step") that can no longer
occur, since a host can never resolve at submission time anymore (see the
`invitations` capability's "Visit Details Optionally Accept Catalog IDs
Alongside Free Text").
**Migration**: See "Submission Snapshots the Category's Workflow Plus an
Unconditional Ownership Step" below, which replaces this requirement in
full.

## ADDED Requirements

### Requirement: Submission Snapshots the Category's Workflow Plus an Unconditional Ownership Step
WHEN an invitation is submitted (created with a resulting status of
`submitted`, i.e. not auto-approved) for a `visitorCategoryId` that has one
or more active `ApprovalWorkflowRule` rows, the system SHALL create one
`InvitationApprovalStep` per active rule, copying that rule's `stepOrder`,
`approverRoleId`, and `isMandatory` at that moment, each starting in
`pending` status. This is a point-in-time snapshot, not a live reference to
the rule: a rule created, edited, or deactivated after the snapshot SHALL
NOT change the steps already created for invitations submitted before that
edit.

Unconditionally — regardless of whether the category has any active rules,
and regardless of anything supplied at creation — the system SHALL
additionally create one `InvitationApprovalStep` at `stepOrder` 0,
role-identified for the tenant's default host role (the standard `reception`
role unless a tenant has reconfigured it), `isMandatory` true, starting
`pending`, ahead of any role-identified steps snapshotted from the
category's active `ApprovalWorkflowRule` chain. The role-identified steps
(if any) keep the `stepOrder` values already configured on their rules (by
convention starting at 1), so no renumbering is needed. The invitation's
actual host is established later, by delegating this step to a specific
person (see "Delegating the Ownership Step Also Resolves the Invitation's
Host") — not at snapshot time.

#### Scenario: A category with three active rules snapshots four ordered steps
- **WHEN** an invitation is submitted for a `visitorCategoryId` with three
  active `ApprovalWorkflowRule` rows at `stepOrder` 1, 2, and 3
- **THEN** four `InvitationApprovalStep` rows are created: `stepOrder` 0
  (role-identified for the tenant's default host role, `pending`, the
  current step), followed by `stepOrder` 1, 2, and 3 (role-identified, as
  configured), all `pending`

#### Scenario: A category with no active rules still snapshots the ownership step
- **WHEN** an invitation is submitted for a `visitorCategoryId` with zero
  active `ApprovalWorkflowRule` rows
- **THEN** exactly one `InvitationApprovalStep` is created, at `stepOrder` 0,
  role-identified for the tenant's default host role, `pending` — the
  invitation is no longer left with zero snapshotted steps in this case

#### Scenario: Editing a rule after snapshot does not affect an in-flight invitation
- **WHEN** an invitation's approval steps have already been snapshotted, and
  an admin subsequently edits or deactivates the category's
  `ApprovalWorkflowRule` that produced one of those steps
- **THEN** the already-created `InvitationApprovalStep` row is unchanged —
  its `approverRoleId`, `isMandatory`, and position in the sequence stay as
  they were snapshotted

#### Scenario: Auto-approved invitations are never snapshotted
- **WHEN** an invitation's initial status resolves to `approved` at creation
  (tenant auto-approve enabled)
- **THEN** no `InvitationApprovalStep` rows are created, regardless of
  whether the category has active rules

### Requirement: Delegating the Ownership Step Also Resolves the Invitation's Host
WHEN the invitation's `stepOrder` 0 step (role-identified for the tenant's
default host role) is successfully delegated to a specific person, the
system SHALL, in the same transaction, set the invitation's `hostId` and
`hostNameOrEmail` (see the `invitations` capability's "Invitation Output
Surfaces the Resolved Host as hostId") to that delegate — establishing them
as the invitation's resolved host from that point on. Re-delegating an
already-delegated `stepOrder` 0 step SHALL update the resolved host to the
new delegate the same way. Delegating any step other than `stepOrder` 0
SHALL NOT change the invitation's resolved host. The newly assigned host
SHALL be notified (push, and email using the branded template from the
`email-notifications` capability) that they have been named host of the
invitation, including the tracking ID, visitor's name, and visit
date/time — a notification that does not fire today, since delegation
currently has no dispatch at all.

#### Scenario: Delegating stepOrder 0 resolves and notifies the host
- **WHEN** a holder of the tenant's default host role delegates an
  invitation's `stepOrder` 0 step to a specific person for the first time
- **THEN** the invitation's `hostId`/`hostNameOrEmail` are set to that
  person, and they receive a push notification and an email stating they
  have been named host, with the tracking ID, visitor's name, and visit
  date/time

#### Scenario: Re-delegating stepOrder 0 updates the resolved host and notifies the new one
- **WHEN** an invitation's already-delegated `stepOrder` 0 step is
  re-delegated to a different person
- **THEN** the invitation's `hostId`/`hostNameOrEmail` update to the new
  person, who receives the same host-assignment notification; the
  previous delegate receives no further notifications tied to being host

#### Scenario: Delegating a later step does not change the resolved host
- **WHEN** a `stepOrder` 1 (or later) step is delegated to a specific person
- **THEN** the invitation's `hostId`/`hostNameOrEmail` are unaffected, and no
  host-assignment notification is dispatched from this requirement (the
  delegate of that later step is still visible to themselves via
  `relevantToMe` clause (b), independent of host resolution)
