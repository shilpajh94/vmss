## ADDED Requirements

### Requirement: Reception-only approval assigns the approver as host
The system SHALL, when a reception-only (single total step) invitation is approved via the plain "Approve" action, set the invitation's host to the reception staff member who approved it.

#### Scenario: Single-step invitation approved by Reception
- **WHEN** a reception-only invitation (workflow with exactly one total step) is approved
- **THEN** the invitation's host becomes the approving reception staff member instead of remaining unassigned

#### Scenario: Multi-step workflow is unaffected
- **WHEN** Reception approves its own step in a workflow with more than one total step
- **THEN** the host is unaffected by this requirement — it continues to be set only via the existing "Approve & Delegate" action, exactly as today
