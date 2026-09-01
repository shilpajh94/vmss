## ADDED Requirements

### Requirement: Invitation Approval, Denial, Reschedule, Check-In, and Check-Out Notify the Host via Push
When an invitation with a resolved host (`host_id` present) is approved
(directly, or as the final step of a multi-step workflow), denied (directly,
or via a rejected step), rescheduled, checked in, or checked out, the system
SHALL dispatch a push notification to that host user, in addition to the
visitor's existing email/SMS notification where one already exists for that
action. An invitation with no resolved host SHALL skip the push dispatch for
these actions without failing the triggering request.

#### Scenario: Approval notifies the host
- **WHEN** an invitation with a resolved host is approved (via
  `POST /invitations/{id}/approve` or as the final approval step)
- **THEN** the host user receives a push notification, and the visitor still
  receives their existing approval email/SMS unchanged

#### Scenario: Denial notifies the host
- **WHEN** an invitation with a resolved host is denied (directly, or via a
  rejected approval step)
- **THEN** the host user receives a push notification stating the invitation
  was denied

#### Scenario: Reschedule notifies the host
- **WHEN** an invitation with a resolved host has its preferred visit
  date/time changed via the reschedule endpoint
- **THEN** the host user receives a push notification stating the new
  date/time, alongside the visitor's existing reschedule email/SMS

#### Scenario: Check-in and check-out notify the host
- **WHEN** an invitation with a resolved host is checked in, and later when
  it is checked out
- **THEN** the host user receives a push notification for each event

#### Scenario: No resolved host means no push, and the request still succeeds
- **WHEN** any of the actions above completes for an invitation whose
  `host_id` never resolved
- **THEN** the action's own HTTP response is unaffected and no push
  notification is dispatched for that action

### Requirement: Invitation Submission Notifies the Approval Workflow's First Approver(s) via Push
When `create_invitation` leaves an invitation `submitted` (not auto-approved)
with at least one approval step, the system SHALL dispatch a push
notification to the newly-created first (`step_order` 0) step's
approver(s) — the resolved host if the step is host-identified, or every
user holding the step's role at the invitation's branch if role-identified.

#### Scenario: Submission with a host-identified first step
- **WHEN** an invitation is submitted and its host resolves, giving it an
  implicit host-identified step 0
- **THEN** the host user receives a push notification that a new invitation
  awaits their approval

#### Scenario: Submission with a role-identified first step
- **WHEN** an invitation is submitted with no resolved host, and its
  category's workflow gives it a role-identified step 0 (e.g. an Admin-role
  step)
- **THEN** every user holding that role at the invitation's branch receives a
  push notification that a new invitation awaits their approval

### Requirement: Auto-Approved Invitations Do Not Trigger a Submission Push
An invitation created while the tenant's Company profile auto-approves
pre-registered visitors never has approval steps, so its creation SHALL NOT
dispatch a "submitted, awaiting your approval" push to anyone — only the
visitor's existing auto-approval email/SMS fires.

#### Scenario: Auto-approve tenant, no staff push on creation
- **WHEN** an invitation is created for a tenant whose Company profile has
  `auto_approve_pre_registered_visitors` enabled
- **THEN** no approval-step push notification is dispatched, and the visitor
  still receives their existing approval-confirmation email/SMS
