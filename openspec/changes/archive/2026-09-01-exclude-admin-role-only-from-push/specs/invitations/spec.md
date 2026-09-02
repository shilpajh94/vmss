## MODIFIED Requirements

### Requirement: Invitation Submission Notifies the Approval Workflow's First Approver(s) via Push
When `create_invitation` leaves an invitation `submitted` (not auto-approved)
with at least one approval step, the system SHALL dispatch a push
notification to the newly-created first (`step_order` 0) step's
approver(s): the resolved host if the step is host-identified, or every
user holding the step's role at the invitation's branch if role-identified
— except when that role is the tenant's standard `admin` role (matched by
name, case-insensitively), which SHALL NOT receive a push notification.

#### Scenario: Submission with a host-identified first step
- **WHEN** an invitation is submitted and its host resolves, giving it an
  implicit host-identified step 0
- **THEN** the host user receives a push notification that a new invitation
  awaits their approval

#### Scenario: Submission with a role-identified first step
- **WHEN** an invitation is submitted with no resolved host, and its
  category's workflow gives it a role-identified step 0 for a role other
  than the tenant's standard `admin` role (e.g. Reception, Security, or a
  tenant-defined custom role)
- **THEN** every user holding that role at the invitation's branch receives
  a push notification that a new invitation awaits their approval

#### Scenario: Submission with an Admin-role first step sends no push
- **WHEN** an invitation is submitted with no resolved host, and its
  category's workflow gives it a role-identified step 0 for the tenant's
  standard `admin` role
- **THEN** no push notification is dispatched to anyone for that step
