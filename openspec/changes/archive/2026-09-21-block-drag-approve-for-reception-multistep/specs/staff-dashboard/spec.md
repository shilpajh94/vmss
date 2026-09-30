## MODIFIED Requirements

### Requirement: Dropping a requested card on Approved approves it, using the step endpoint when a workflow is active
The system SHALL, when a card is dropped on the Approved column, approve that invitation: if it has a current approval step, approve that specific step; otherwise approve the invitation directly. On success it SHALL refresh the board and trigger a success notification; on failure it SHALL trigger an error notification showing the backend's message. A card whose current approval step is stepOrder 0 (Reception) in a workflow with more than one total step SHALL NOT be draggable to the Approved column at all — "Approve & Delegate" is the only way to advance it.

#### Scenario: Approving a non-workflow invitation
- **WHEN** a card for an invitation with no configured approval workflow is dropped on Approved
- **THEN** the system approves the invitation directly, refreshes the board, and triggers a success notification

#### Scenario: Approving a workflow-backed invitation's current step
- **WHEN** a card for an invitation with a current approval step, other than a Reception step with a further step following, is dropped on Approved
- **THEN** the system approves that specific step, refreshes the board, and triggers a success notification

#### Scenario: Approval rejected by the backend
- **WHEN** an approve attempt (direct or step-based) fails
- **THEN** the system triggers an error notification containing the backend's error message and the board is not otherwise changed

#### Scenario: A Reception-step, multi-step card cannot be drag-approved
- **WHEN** a card's current approval step is stepOrder 0 (Reception) and the workflow has more than one total step
- **THEN** the card cannot be dragged to the Approved column, and only "Approve & Delegate" is available to advance it
