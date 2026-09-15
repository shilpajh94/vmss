## MODIFIED Requirements

### Requirement: A workflow requires at least one approval level with an approver
The system SHALL, on the Add/Edit Workflow page, start with at least one approval level, require every level other than Level 1 to have an approver role selected before submission succeeds, and SHALL NOT allow removing the last remaining level or Level 1 specifically, regardless of how many levels exist.

#### Scenario: New workflow starts with one empty level
- **WHEN** the Add Workflow page loads
- **THEN** it shows exactly one approval level, with Level 1 already set to the Reception role

#### Scenario: Level submitted without an approver
- **WHEN** an admin submits the page with any level other than Level 1 left unselected
- **THEN** the system shows a validation error and does not submit any rule

#### Scenario: Delete attempted on the only remaining level
- **WHEN** an admin activates the delete action on a page with exactly one level
- **THEN** the system does not remove the level

#### Scenario: Delete attempted on Level 1 with other levels present
- **WHEN** an admin activates the delete action on Level 1 while additional levels exist
- **THEN** the system does not remove Level 1

### Requirement: Approver options are the organisation's roles
The system SHALL populate every level after Level 1's Approver Select field with the organisation's roles, so an admin can only assign that approval level to a role that actually exists. Level 1's approver is fixed to the Reception role and is not selectable from this list.

#### Scenario: Approver options loaded
- **WHEN** the Add/Edit Workflow page loads
- **THEN** every level after Level 1 offers every role in the organisation's role list, and Level 1 shows the Reception role, locked

### Requirement: Editing a workflow opens the same page pre-filled with its current levels
The system SHALL, when a group's "Edit" action is activated, navigate to the Edit Workflow page pre-filled with that visitor category's existing rules as ordered levels, each showing its current approver role — except Level 1, which is shown and saved as the Reception role regardless of what its existing rule's approver was.

#### Scenario: Edit opened
- **WHEN** an admin activates a workflow group's "Edit" action
- **THEN** the system navigates to the Edit Workflow page pre-filled with that category's existing levels in `stepOrder` order, with Level 1 shown as the Reception role

#### Scenario: Editing a workflow whose saved Level 1 is not Reception
- **WHEN** an admin opens the Edit Workflow page for a workflow whose saved Level 1 approver is a role other than Reception
- **THEN** the page shows Level 1 as the Reception role, and saving the page updates that workflow's Level 1 rule to the Reception role

## ADDED Requirements

### Requirement: Level 1 is fixed to the Reception role
The system SHALL, on the Add/Edit Workflow page, resolve the organisation's role named "Reception" and fix Level 1's approver to it — displayed as locked, not editable — for both a new workflow and an existing one being edited. If no role named "Reception" exists in the organisation's role catalog, the system SHALL show a blocking error on the page instead of allowing the form to be used.

#### Scenario: Reception role resolved
- **WHEN** the Add/Edit Workflow page loads and a role named "Reception" exists in the organisation's roles
- **THEN** Level 1 shows that role, locked and not editable

#### Scenario: No Reception role configured
- **WHEN** the Add/Edit Workflow page loads and no role named "Reception" exists in the organisation's roles
- **THEN** the system shows a blocking error explaining that a Reception role must exist before a workflow can be configured
