# approvals Specification

## Purpose

Evaluates a visitor category's configured `ApprovalWorkflowRule` chain
against an actual submitted invitation — snapshotting it into ordered,
per-invitation approval steps and governing how those steps are approved,
rejected, and authorized — so a workflow configured in the admin UI actually
takes effect at approval time instead of only existing as unused config.

## Requirements

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

### Requirement: Steps Are Approved in Strict Order by the Current Pending Step
For an invitation with snapshotted approval steps, only the single step with
the lowest `stepOrder` still `pending` is actionable at any time (the
"current step"). `POST /invitations/{id}/approval-steps/{stepId}/approve`
SHALL approve that step, recording the acting user and timestamp. WHEN the
approved step is not the last one, the next step by `stepOrder` becomes the
new current step. WHEN it is the last step, the invitation transitions to
`approved`, its `approvedAt` is set, and the existing QR/notification
dispatch fires — the same dispatch a non-workflow invitation's approval
already triggers. Calling this endpoint with a `stepId` that is not the
invitation's current pending step (already acted on, or not yet reached)
SHALL be rejected with 409 and SHALL NOT change any step's status. An
unknown invitation id or step id (or a step id belonging to a different
invitation) SHALL be rejected with 404.

#### Scenario: Approving a non-final step unlocks the next one
- **WHEN** an approver approves the current pending step of a 3-step
  invitation at `stepOrder` 1
- **THEN** that step's status becomes `approved`, its acting user and
  timestamp are recorded, the invitation's overall status remains
  `submitted`, and the step at `stepOrder` 2 becomes the current pending
  step

#### Scenario: Approving the final step approves the invitation and fires the QR notification
- **WHEN** an approver approves the current pending step that is the last
  step in the sequence
- **THEN** that step's status becomes `approved`, the invitation's status
  becomes `approved`, `approvedAt` is set, and the approval notification
  (tracking ID + QR code) is dispatched to the primary contact

#### Scenario: Acting on a step out of order is rejected
- **WHEN** a caller calls the approve endpoint for a step that has already
  been acted on, or for a step later in the sequence than the current
  pending step
- **THEN** the request is rejected with 409 and no step's status changes

#### Scenario: Unknown invitation or step id is rejected with 404
- **WHEN** a caller names an invitation id or step id that does not exist,
  or a step id that belongs to a different invitation than the one named in
  the path
- **THEN** the request is rejected with 404

### Requirement: Rejecting a Step Is Terminal and Denies the Invitation
`POST /invitations/{id}/approval-steps/{stepId}/reject` SHALL reject the
named current pending step — recording the acting user, timestamp, and a
mandatory reason — and SHALL immediately deny the invitation as a whole (see
the `invitations` capability's "Approval-Step Rejection Denies the
Invitation" requirement), regardless of how many steps remain after the
rejected one. No resubmission path exists: a denied invitation stays denied,
and none of its other steps (approved, pending, or otherwise) become
actionable again. The same out-of-order and unknown-id rejections that apply
to approving a step apply to rejecting one.

#### Scenario: Rejecting a middle step denies the invitation without evaluating later steps
- **WHEN** an approver rejects the current pending step at `stepOrder` 2 of
  a 3-step invitation
- **THEN** that step's status becomes `rejected`, the invitation's status
  becomes `denied`, and the step at `stepOrder` 3 remains `pending` and is
  never evaluated or actioned

#### Scenario: Rejecting a step requires a reason
- **WHEN** a caller calls the reject endpoint without supplying a reason
- **THEN** the request is rejected with a validation error and no step or
  invitation status changes

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

### Requirement: Escalation and Auto-Approve Timestamps Are Computed but Not Enforced
Each `InvitationApprovalStep` SHALL carry `escalatesAt` and `autoApprovesAt`
timestamps, computed by adding the snapshotted rule's `escalationMinutes`/
`autoApproveMinutes` (each independently nullable) to the moment that step
becomes the current pending step — the invitation's submission time for the
first step, or the moment the prior step is approved for every subsequent
step. A rule that does not configure one of those minute values SHALL leave
the corresponding timestamp null for that step. Nothing in this capability
SHALL automatically act on either timestamp once it passes — no automatic
status transition and no escalation notification are triggered by this
change; the fields exist solely for a caller (e.g. the UI) to render a
countdown or overdue indicator.

#### Scenario: First step's timestamps are set at submission
- **WHEN** an invitation is submitted and its first snapshotted step's rule
  configures both `escalationMinutes` and `autoApproveMinutes`
- **THEN** that step's `escalatesAt` and `autoApprovesAt` are set relative to
  the submission timestamp

#### Scenario: A later step's timestamps are set when it becomes current
- **WHEN** a step's rule configures `escalationMinutes`/`autoApproveMinutes`
  and the prior step is approved, making this step the new current pending
  step
- **THEN** this step's `escalatesAt`/`autoApprovesAt` are computed relative
  to the moment it became current, not relative to the invitation's original
  submission time

#### Scenario: An unconfigured duration leaves its timestamp null
- **WHEN** a step's snapshotted rule does not configure
  `escalationMinutes` or does not configure `autoApproveMinutes`
- **THEN** the corresponding timestamp (`escalatesAt` or `autoApprovesAt`,
  respectively) is null for that step

#### Scenario: A passed timestamp triggers no automatic action
- **WHEN** a step's `escalatesAt` or `autoApprovesAt` timestamp is in the
  past and no caller has acted on the step
- **THEN** the step's status remains `pending`, no escalation notification
  is dispatched, and no status auto-transition occurs

### Requirement: Activating an Approval Step Notifies Its Approver(s) via Push
Whenever a step becomes the invitation's current pending step because the
prior step was just approved (`_activate_next_step`), the system SHALL
dispatch a push notification to the newly-current step's approver(s): the
resolved host if the step is host-identified, or every user holding the
step's role at the invitation's branch if role-identified — except when
that role is the tenant's standard `admin` role (matched by name,
case-insensitively), which SHALL NOT receive a push notification. This is
in addition to, and uses the same resolution rules as, the push dispatched
when an invitation's first step is created at submission
(`specs/invitations/spec.md` "Invitation Submission Notifies the Approval
Workflow's First Approver(s) via Push").

#### Scenario: Approving a role-identified step activates a host-identified step
- **WHEN** a two-step invitation's first (role-identified) step is approved,
  making the second (host-identified) step current
- **THEN** the host user receives a push notification that the invitation
  now awaits their approval

#### Scenario: Approving a step activates a role-identified step, sending no push
- **WHEN** a step is approved and the newly-current next step is
  role-identified for the tenant's standard `admin` role
- **THEN** no push notification is dispatched to anyone for that step
  activation

#### Scenario: Approving a step activates a non-Admin role-identified step
- **WHEN** a step is approved and the newly-current next step is
  role-identified for a role other than `admin` (e.g. Reception, Security,
  or a tenant-defined custom role)
- **THEN** every user holding that role at the invitation's branch receives
  a push notification that the invitation now awaits their approval

#### Scenario: Approving the last step does not double-notify via this requirement
- **WHEN** the step just approved was the invitation's last pending step (no
  next step to activate)
- **THEN** no "step activated" push fires from this requirement — the
  invitation's own approval push (`specs/invitations/spec.md` "Invitation
  Approval, Denial, Reschedule, Check-In, and Check-Out Notify the Host via
  Push") is what notifies the host of the outcome instead
