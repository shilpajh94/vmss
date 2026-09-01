## MODIFIED Requirements

### Requirement: Invitation Submission Notifies the Approval Workflow's First Approver(s) via Push
When `create_invitation` leaves an invitation `submitted` (not auto-approved)
with at least one approval step, and that first (`step_order` 0) step is
host-identified, the system SHALL dispatch a push notification to the
resolved host. A role-identified first step SHALL NOT dispatch a push to
anyone — only a host-identified step's host is ever pushed at submission.

#### Scenario: Submission with a host-identified first step
- **WHEN** an invitation is submitted and its host resolves, giving it an
  implicit host-identified step 0
- **THEN** the host user receives a push notification that a new invitation
  awaits their approval

#### Scenario: Submission with a role-identified first step
- **WHEN** an invitation is submitted with no resolved host, and its
  category's workflow gives it a role-identified step 0 (e.g. an Admin-role
  step)
- **THEN** no push notification is dispatched to anyone for that step
