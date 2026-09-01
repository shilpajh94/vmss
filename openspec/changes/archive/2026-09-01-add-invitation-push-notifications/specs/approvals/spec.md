## ADDED Requirements

### Requirement: Activating an Approval Step Notifies Its Approver(s) via Push
Whenever a step becomes the invitation's current pending step because the
prior step was just approved (`_activate_next_step`), the system SHALL
dispatch a push notification to the newly-current step's approver(s) — the
resolved host if the step is host-identified, or every user holding the
step's role at the invitation's branch if role-identified. This is in
addition to, and uses the same resolution rules as, the push dispatched when
an invitation's first step is created at submission
(`specs/invitations/spec.md` "Invitation Submission Notifies the Approval
Workflow's First Approver(s) via Push").

#### Scenario: Approving a role-identified step activates a host-identified step
- **WHEN** a two-step invitation's first (role-identified) step is approved,
  making the second (host-identified) step current
- **THEN** the host user receives a push notification that the invitation
  now awaits their approval

#### Scenario: Approving the last step does not double-notify via this requirement
- **WHEN** the step just approved was the invitation's last pending step (no
  next step to activate)
- **THEN** no "step activated" push fires from this requirement — the
  invitation's own approval push (`specs/invitations/spec.md` "Invitation
  Approval, Denial, Reschedule, Check-In, and Check-Out Notify the Host via
  Push") is what notifies the host of the outcome instead
