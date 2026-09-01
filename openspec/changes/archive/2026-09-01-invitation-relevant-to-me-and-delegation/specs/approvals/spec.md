## MODIFIED Requirements

### Requirement: Acting on a Step Requires the Caller's Matching Role, or an Explicit Override
A caller acting on an approval step (approve or reject) SHALL hold
`invitations:approve` at the invitation's branch, exactly as the existing
blanket approve endpoint requires, AND SHALL satisfy one of:
(a) the step has a delegate assigned (see "Host Delegates the Step
Following Their Own to a Specific Person") and the caller's own user id
matches that delegate exactly — a delegated step is authorized for the
delegate only, and its `approverRoleId`-based role match no longer applies
once a delegate is assigned;
(b) the step has no delegate assigned, its `approverRoleId` is set, and the
caller holds, via their branch-scoped role assignment, the `Role` it names,
at the invitation's branch;
(c) the current step's `approverUserId` is set and the caller's own user id
matches it exactly (host-identified steps are not role-matched — the step
is authorized for that specific person, regardless of their assigned
role); or
(d) the caller holds the `invitations:approve-override` permission, which
bypasses the role-match, delegate-match, and host-match checks.
A caller satisfying none of (a), (b), (c), or (d) SHALL be rejected with
403, and the step's and invitation's status SHALL be unchanged.

#### Scenario: Caller holding the step's approver role succeeds
- **WHEN** a caller holds `invitations:approve` and, via `UserBranchRole` at
  the invitation's branch, the exact `Role` the current step's
  `approverRoleId` names, and the step has no delegate assigned
- **THEN** the caller may approve or reject that step

#### Scenario: Caller matching the step's approver user succeeds
- **WHEN** a caller holds `invitations:approve` at the invitation's branch
  and the current step's `approverUserId` equals the caller's own user id
- **THEN** the caller may approve or reject that step, regardless of which
  role they are otherwise assigned at that branch

#### Scenario: Caller matching the step's delegate succeeds regardless of their assigned role
- **WHEN** a caller holds `invitations:approve` at the invitation's branch,
  the current step has a delegate assigned, and the caller's own user id
  matches that delegate
- **THEN** the caller may approve or reject that step, regardless of
  whether they also hold the step's `approverRoleId` role there

#### Scenario: Caller with a non-matching role and no override is rejected
- **WHEN** a caller holds `invitations:approve` at the invitation's branch
  but their assigned role there does not match the current step's
  `approverRoleId`, the step has no delegate assigned, and they do not hold
  `invitations:approve-override`
- **THEN** the request is rejected with 403 and no step or invitation status
  changes

#### Scenario: Caller who is not the step's approver user and lacks override is rejected
- **WHEN** the current step's `approverUserId` is set, the caller's own
  user id does not match it, and the caller does not hold
  `invitations:approve-override`
- **THEN** the request is rejected with 403 and no step or invitation status
  changes

#### Scenario: Caller holding the step's role but not matching its delegate is rejected
- **WHEN** the current step has a delegate assigned, the caller's own user
  id does not match that delegate (even though the caller holds the step's
  `approverRoleId` role at the invitation's branch), and the caller does
  not hold `invitations:approve-override`
- **THEN** the request is rejected with 403 and no step or invitation status
  changes

#### Scenario: Override permission bypasses the role-match check
- **WHEN** a caller holds `invitations:approve` and `invitations:approve-
  override` at the invitation's branch, regardless of whether the current
  step is role-identified, host-identified, or delegated, and regardless of
  the caller's own assigned role or user id
- **THEN** the caller may approve or reject the current step

#### Scenario: Caller lacking invitations:approve entirely is rejected regardless of role
- **WHEN** a caller does not hold `invitations:approve` at the invitation's
  branch, even if their assigned role, user id, or delegate status would
  otherwise match the current step's approver
- **THEN** the request is rejected with 403

## ADDED Requirements

### Requirement: Host Delegates the Step Following Their Own to a Specific Person
Once an invitation's `stepOrder` 0 host-identified step has been approved
and the role-identified step at `stepOrder` 1 has become the current
pending step, the system SHALL let the invitation's host (the same user
identified by that `stepOrder` 0 step's `approverUserId`) delegate that
`stepOrder` 1 step to a specific person via
`POST /invitations/{invitationId}/approval-steps/{stepId}/delegate`,
supplying the delegate's user id. The delegate SHALL hold the step's
configured `approverRoleId` role, via their own branch-scoped role
assignment at the invitation's branch (or company-wide), at the moment of
delegation — the same role-membership rule used to authorize a
role-identified step action. Only the step immediately following the
host's own step is delegable this way; a step at any other `stepOrder`
(including `stepOrder` 0 itself, or `stepOrder` 2+ in a 3-or-more level
workflow) SHALL be rejected. Delegating a step that is not currently the
invitation's current pending step, or that has already been delegated,
acted on, or belongs to an invitation with no `stepOrder` 0 host step,
SHALL be rejected. A successful delegation SHALL record the delegate, the
delegating host, and the timestamp, and does not itself change the step's
`pending` status or the invitation's overall status — the delegate must
still separately approve or reject it.

#### Scenario: Host delegates the step following their own
- **WHEN** the host of an invitation whose `stepOrder` 0 step they already
  approved calls the delegate endpoint on the now-current `stepOrder` 1
  step, naming a user who holds that step's role at the invitation's branch
- **THEN** the delegation succeeds, the step remains `pending`, and the
  named user becomes the only caller (short of an override) who can approve
  or reject it

#### Scenario: Caller who is not the host is rejected
- **WHEN** a caller who is not the user identified by the invitation's
  `stepOrder` 0 step attempts to delegate the `stepOrder` 1 step, even if
  they otherwise hold `invitations:approve` at the invitation's branch
- **THEN** the request is rejected with 403 and no delegation is recorded

#### Scenario: Delegating before the host's own step is approved is rejected
- **WHEN** the host attempts to delegate the `stepOrder` 1 step while their
  own `stepOrder` 0 step is still `pending`
- **THEN** the request is rejected with 409 and no delegation is recorded

#### Scenario: Delegating a step other than the one immediately following the host's is rejected
- **WHEN** the host of a 3-or-more level workflow attempts to delegate the
  `stepOrder` 2 step, or attempts to delegate `stepOrder` 0 itself
- **THEN** the request is rejected and no delegation is recorded

#### Scenario: Delegating to a person who does not hold the step's role is rejected
- **WHEN** the host names a delegate who does not hold, via any
  branch-scoped role assignment at the invitation's branch or
  company-wide, the `stepOrder` 1 step's configured `approverRoleId` role
- **THEN** the request is rejected and no delegation is recorded

#### Scenario: Re-delegating an already-delegated step is rejected
- **WHEN** the host attempts to delegate the `stepOrder` 1 step a second
  time, after it already has a delegate assigned
- **THEN** the request is rejected and the existing delegation is unchanged

#### Scenario: Delegating an already-acted-on step is rejected
- **WHEN** the host attempts to delegate the `stepOrder` 1 step after it
  has already been approved or rejected
- **THEN** the request is rejected with 409 and no delegation is recorded

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
