## MODIFIED Requirements

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
