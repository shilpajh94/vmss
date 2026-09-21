## MODIFIED Requirements

### Requirement: An in-progress approval step shows its pending approver by name
The system SHALL, when an expanded card's invitation has a current approval step, show "Step X of Y" together with the name of who it is pending on: the role's name when the step is assigned to a role, or that person's full name when it is assigned to a specific host user. When the current step is stepOrder 0 (Reception) and the workflow has more than one total step, the system SHALL instead show the *next* step's (stepOrder 1) required role as the pending approver, both on the collapsed card badge and the expanded detail line.

#### Scenario: Step pending on a role
- **WHEN** an expanded card's current approval step is assigned to a role, and that step is not Reception's (stepOrder 0) step in a multi-step workflow
- **THEN** the system shows that role's name as the pending approver

#### Scenario: Step pending on a specific host
- **WHEN** an expanded card's current approval step is assigned to a specific user (the invitation's host)
- **THEN** the system shows that user's full name as the pending approver

#### Scenario: Reception's step previews the next level instead of naming itself
- **WHEN** a card's current approval step is stepOrder 0 (Reception) and the workflow has more than one total step
- **THEN** the system shows the next step's required role as the pending approver, on both the collapsed badge and the expanded detail line, instead of naming Reception's own step

#### Scenario: Single-step Reception-only workflow is unaffected
- **WHEN** a card's current approval step is stepOrder 0 (Reception) and the workflow has only one total step
- **THEN** the system shows Reception's own step as the pending approver, unchanged
