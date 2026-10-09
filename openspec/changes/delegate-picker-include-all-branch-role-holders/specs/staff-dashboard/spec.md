## ADDED Requirements

### Requirement: Delegate and next-step pickers include employees holding the role for all branches
The system SHALL, when listing employees for "Approve & Delegate" (the next step's role) or "Delegate" (the current step's role), include every active employee who holds that role either at the invitation's own branch or with an "All Branch" assignment (no specific branch). It SHALL NOT include employees who hold the role only at a different branch. When the invitation has no branch, any holder of the role SHALL be listed.

#### Scenario: Role holder assigned to the invitation's branch is listed
- **WHEN** a Reception user opens "Approve & Delegate" and an employee holds the next step's role at the invitation's branch
- **THEN** that employee appears in the dropdown

#### Scenario: Role holder assigned to All Branch is listed
- **WHEN** an employee holds the next step's role with an "All Branch" assignment
- **THEN** that employee appears in the dropdown for an invitation at any branch

#### Scenario: Role holder at a different branch is not listed
- **WHEN** an employee holds the role only at a branch other than the invitation's
- **THEN** that employee does not appear in the dropdown

#### Scenario: Multiple holders all appear
- **WHEN** several employees hold the next role (any mix of matching-branch and All Branch)
- **THEN** all of them appear in the dropdown, not just one

#### Scenario: Both pickers agree
- **WHEN** the same invitation's step is viewed via "Approve & Delegate" and via "Delegate"
- **THEN** both list the same eligible employees for that step's role

#### Scenario: Server rejects a chosen delegate
- **WHEN** the backend rejects the selected delegate on submit
- **THEN** the backend's message is shown as an error notification
