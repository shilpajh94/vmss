## MODIFIED Requirements

### Requirement: Submission Snapshots the Category's Active Workflow Into Ordered Steps
WHEN an invitation is submitted (created with a resulting status of
`submitted`, i.e. not auto-approved) for a `visitorCategoryId` that has one
or more active `ApprovalWorkflowRule` rows, the system SHALL create one
`InvitationApprovalStep` per active rule, copying that rule's `stepOrder`,
`approverRoleId`, and `isMandatory` at that moment, each starting in
`pending` status. This is a point-in-time snapshot, not a live reference to
the rule: a rule created, edited, or deactivated after the snapshot SHALL
NOT change the steps already created for invitations submitted before that
edit.

WHEN the invitation's host resolves to an active user at submission time
(`hostId` given, or `hostNameOrEmail` matched to an active user), the
system SHALL additionally create one implicit host-identified
`InvitationApprovalStep` at `stepOrder` 0 — carrying `approverUserId` set to
that host, `approverRoleId` null, `isMandatory` true, starting `pending` —
ahead of any role-identified steps snapshotted from the category's active
`ApprovalWorkflowRule` chain. This host step is unconditional: it is
created whenever the host resolves, regardless of whether the category has
any active rules, and the role-identified steps (if any) keep the
`stepOrder` values already configured on their rules (by convention
starting at 1), so no renumbering is needed. WHEN the category has zero
active rules and the host does not resolve to a user, the system SHALL
create no steps for that invitation, leaving it to the existing single-
approve behavior.

#### Scenario: A category with three active rules snapshots three ordered steps
- **WHEN** an invitation is submitted for a `visitorCategoryId` with three
  active `ApprovalWorkflowRule` rows at `stepOrder` 1, 2, and 3, and the
  invitation's host does not resolve to a user
- **THEN** three `InvitationApprovalStep` rows are created for that
  invitation, each `pending`, ordered 1, 2, and 3, carrying the
  corresponding rule's `approverRoleId` and `isMandatory`

#### Scenario: A category with no active rules creates no steps
- **WHEN** an invitation is submitted for a `visitorCategoryId` with zero
  active `ApprovalWorkflowRule` rows, and the invitation's host does not
  resolve to a user
- **THEN** no `InvitationApprovalStep` rows are created for that invitation,
  and it remains approvable only through the blanket single-approve
  endpoint

#### Scenario: A resolved host with no configured rules creates a single host-approval step
- **WHEN** an invitation is submitted whose host resolves to an active
  user, for a `visitorCategoryId` with zero active `ApprovalWorkflowRule`
  rows
- **THEN** exactly one `InvitationApprovalStep` is created at `stepOrder`
  0, `pending`, carrying `approverUserId` set to the resolved host and
  `approverRoleId` null

#### Scenario: A resolved host with configured rules creates a host step ahead of the role chain
- **WHEN** an invitation is submitted whose host resolves to an active
  user, for a `visitorCategoryId` with three active `ApprovalWorkflowRule`
  rows at `stepOrder` 1, 2, and 3
- **THEN** four `InvitationApprovalStep` rows are created: `stepOrder` 0
  (host-identified, `approverUserId` set, `pending`, the current step),
  followed by `stepOrder` 1, 2, and 3 (role-identified, as configured),
  all still `pending`

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
  whether the category has active rules or the host resolves to a user

### Requirement: Acting on a Step Requires the Caller's Matching Role, or an Explicit Override
A caller acting on an approval step (approve or reject) SHALL hold
`invitations:approve` at the invitation's branch, exactly as the existing
blanket approve endpoint requires, AND SHALL satisfy one of:
(a) the current step's `approverRoleId` is set and the caller holds, via
their branch-scoped role assignment, the `Role` it names, at the
invitation's branch;
(b) the current step's `approverUserId` is set and the caller's own user id
matches it exactly (host-identified steps are not role-matched — the step
is authorized for that specific person, regardless of their assigned
role); or
(c) the caller holds the `invitations:approve-override` permission, which
bypasses both the role-match and the host-match check.
A caller satisfying none of (a), (b), or (c) SHALL be rejected with 403, and
the step's and invitation's status SHALL be unchanged.

#### Scenario: Caller holding the step's approver role succeeds
- **WHEN** a caller holds `invitations:approve` and, via `UserBranchRole` at
  the invitation's branch, the exact `Role` the current step's
  `approverRoleId` names
- **THEN** the caller may approve or reject that step

#### Scenario: Caller matching the step's approver user succeeds
- **WHEN** a caller holds `invitations:approve` at the invitation's branch
  and the current step's `approverUserId` equals the caller's own user id
- **THEN** the caller may approve or reject that step, regardless of which
  role they are otherwise assigned at that branch

#### Scenario: Caller with a non-matching role and no override is rejected
- **WHEN** a caller holds `invitations:approve` at the invitation's branch
  but their assigned role there does not match the current step's
  `approverRoleId`, and they do not hold `invitations:approve-override`
- **THEN** the request is rejected with 403 and no step or invitation status
  changes

#### Scenario: Caller who is not the step's approver user and lacks override is rejected
- **WHEN** the current step's `approverUserId` is set, the caller's own
  user id does not match it, and the caller does not hold
  `invitations:approve-override`
- **THEN** the request is rejected with 403 and no step or invitation status
  changes

#### Scenario: Override permission bypasses the role-match check
- **WHEN** a caller holds `invitations:approve` and `invitations:approve-
  override` at the invitation's branch, regardless of whether the current
  step is role-identified or host-identified and regardless of the
  caller's own assigned role or user id
- **THEN** the caller may approve or reject the current step

#### Scenario: Caller lacking invitations:approve entirely is rejected regardless of role
- **WHEN** a caller does not hold `invitations:approve` at the invitation's
  branch, even if their assigned role or user id would otherwise match the
  current step's `approverRoleId`/`approverUserId`
- **THEN** the request is rejected with 403

## ADDED Requirements

### Requirement: The Current Step's Identifier Is Returned So Callers Can Act On It
The current-step summary embedded in an invitation response
(`currentApprovalStep`, on `InvitationOut`, `InvitationDetailOut`, and
`InvitationTrackingOut`) SHALL include the step's `id`, alongside
`stepOrder` and `totalSteps`, plus whichever of `approverRoleId` or
`approverUserId` identifies that step's approver (the other left null) —
so a caller can invoke `POST /invitations/{id}/approval-steps/{stepId}/
approve` (or `.../reject`) directly, without a separate lookup.

#### Scenario: Role-identified current step exposes its id and approverRoleId
- **WHEN** an invitation with a role-identified current pending step is
  fetched
- **THEN** `currentApprovalStep` includes that step's `id`, its
  `approverRoleId`, `stepOrder`, and `totalSteps`, with `approverUserId`
  null

#### Scenario: Host-identified current step exposes its id and approverUserId
- **WHEN** an invitation with a host-identified current pending step
  (`stepOrder` 0) is fetched
- **THEN** `currentApprovalStep` includes that step's `id`, its
  `approverUserId`, `stepOrder` 0, and `totalSteps`, with `approverRoleId`
  null
