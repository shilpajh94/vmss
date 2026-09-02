## MODIFIED Requirements

### Requirement: Activating an Approval Step Notifies Its Approver(s) via Push
Whenever a step becomes the invitation's current pending step because the
prior step was just approved (`_activate_next_step`), and that newly-current
step is host-identified, the system SHALL dispatch a push notification to
the resolved host. A newly-current step that is role-identified SHALL NOT
dispatch a push to anyone — only a host-identified step's host is ever
pushed on activation, using the same host-only resolution the push
dispatched at submission uses (`specs/invitations/spec.md` "Invitation
Submission Notifies the Approval Workflow's First Approver(s) via Push").

#### Scenario: Approving a role-identified step activates a host-identified step
- **WHEN** a two-step invitation's first (role-identified) step is approved,
  making the second (host-identified) step current
- **THEN** the host user receives a push notification that the invitation
  now awaits their approval

#### Scenario: Approving a step activates a role-identified step, sending no push
- **WHEN** a step is approved and the newly-current next step is
  role-identified
- **THEN** no push notification is dispatched to anyone for that step
  activation

#### Scenario: Approving the last step does not double-notify via this requirement
- **WHEN** the step just approved was the invitation's last pending step (no
  next step to activate)
- **THEN** no "step activated" push fires from this requirement — the
  invitation's own approval push (`specs/invitations/spec.md` "Invitation
  Approval, Denial, Reschedule, Check-In, and Check-Out Notify the Host via
  Push") is what notifies the host of the outcome instead
