## ADDED Requirements

### Requirement: Reception's step offers a combined Approve & Delegate action when a further step follows
The system SHALL, on a card whose current approval step is stepOrder 0 (Reception) and whose workflow has more than one total step, present an "Approve & Delegate" action instead of a plain "Delegate" action. Activating it SHALL show a dropdown of employees eligible for the *next* step's (stepOrder 1) required role. Confirming with a selected employee SHALL approve the Reception step and then assign that employee as the approver of the resulting next step, in a single user-facing action; on success it SHALL refresh the board and trigger a success notification naming the newly-assigned approver.

#### Scenario: Reception approves and assigns the next approver together
- **WHEN** a Reception user activates "Approve & Delegate" on a card with a further step, selects an eligible employee, and confirms
- **THEN** the system approves the Reception step, assigns the selected employee as the next step's approver, refreshes the board, and triggers a success notification

#### Scenario: Approve succeeds but assigning the next approver fails
- **WHEN** the approve call in a confirmed "Approve & Delegate" action succeeds but the subsequent assignment call fails
- **THEN** the system triggers an error notification stating the request was approved but the next approver could not be assigned, and refreshes the board so the current (now-advanced) state is visible

#### Scenario: No eligible employees for the next step
- **WHEN** a Reception user activates "Approve & Delegate" and no employees are eligible for the next step's role
- **THEN** the system shows an empty-state message in the dropdown and the confirm action stays disabled

### Requirement: A single-step Reception-only workflow keeps plain approval
The system SHALL NOT present any delegate-style action on a card whose current approval step is stepOrder 0 (Reception) when the workflow has only one total step; approving remains the only action available for that step.

#### Scenario: Reception-only workflow shows no delegate action
- **WHEN** a card's current approval step is stepOrder 0 and the workflow's total step count is 1
- **THEN** neither "Delegate" nor "Approve & Delegate" is shown on that card
