# admin-approval-workflows Specification

## Purpose

The admin-approval-workflows capability is the Super Admin's Workflows screen at `/admin/workflows`, plus its Add/Edit Workflow page: it lets an admin configure, per visitor category, an ordered chain of role-based approval levels that invitations for that category must pass through.

## Requirements

### Requirement: Admin section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Workflows list or the Add/Edit Workflow page, and SHALL redirect to `/admin/login` instead of rendering when no token is present.

#### Scenario: No token present on the list
- **WHEN** a browser without a staff auth token navigates to `/admin/workflows`
- **THEN** the system redirects to `/admin/login` and does not render the page

#### Scenario: No token present on the form
- **WHEN** a browser without a staff auth token navigates to `/admin/workflows/new`
- **THEN** the system redirects to `/admin/login` and does not render the page

### Requirement: Admin sidebar and top bar render with "Workflows" active
The system SHALL render, for an authenticated session, the Admin sidebar with "Workflows" shown as the active item, and the Admin top bar showing the Workflows-specific description and the signed-in staff member's name and role.

#### Scenario: Admin views the Workflows page
- **WHEN** an authenticated admin's Workflows page finishes loading
- **THEN** the sidebar shows "Workflows" marked active and the top bar shows the signed-in staff member's name and role

### Requirement: Workflow list loads on page entry, grouped by visitor category
The system SHALL, when the Workflows page loads, fetch the current approval-workflow rules and the organisation's visitor categories, and render one group per visitor category that has at least one rule, each group listing its approval levels in `stepOrder` order with the approver role's name.

#### Scenario: Workflows load successfully
- **WHEN** the Workflows page loads and both fetches succeed
- **THEN** the page shows one group per visitor category that has configured rules, each listing its levels in order with the approver role's name

### Requirement: Zero configured workflows shows the shared empty state
The system SHALL show the shared empty-state component in place of any group when the rule list loads successfully with zero rules.

#### Scenario: No workflows exist
- **WHEN** the approval-workflow rule list loads successfully with zero rules
- **THEN** the system shows the shared empty-state component instead of any group

### Requirement: Workflow list load failure is reported without crashing
The system SHALL, when either the rule list or the visitor category list fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the Workflows page's rule fetch or visitor-category fetch fails
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: Add Workflow navigates to a dedicated page
The system SHALL, when "Add Workflow" is activated from the Workflows list, navigate to a dedicated Add Workflow page.

#### Scenario: Add Workflow activated
- **WHEN** an admin activates "Add Workflow" on the Workflows list
- **THEN** the system navigates to the Add Workflow page

#### Scenario: Cancel on the Add Workflow page
- **WHEN** an admin activates "Cancel" on the Add Workflow page
- **THEN** the system navigates back to the Workflows list without creating any rules

### Requirement: Add Workflow requires selecting a visitor category with no existing workflow
The system SHALL, on the Add Workflow page, request a Visitor Category, offering only visitor categories that do not already have a configured workflow, and SHALL require a category to be selected before submission succeeds.

#### Scenario: Category options loaded
- **WHEN** the Add Workflow page loads
- **THEN** the Visitor Category field offers only visitor categories that have no rules configured yet

#### Scenario: No category selected
- **WHEN** an admin submits the Add Workflow page with no Visitor Category selected
- **THEN** the system shows a validation error and does not submit any rule

### Requirement: A workflow requires at least one approval level with an approver
The system SHALL, on the Add/Edit Workflow page, start with at least one approval level, require every level to have an approver role selected before submission succeeds, and SHALL NOT allow removing the last remaining level.

#### Scenario: New workflow starts with one empty level
- **WHEN** the Add Workflow page loads
- **THEN** it shows exactly one approval level with no approver selected

#### Scenario: Level submitted without an approver
- **WHEN** an admin submits the page with any level's approver left unselected
- **THEN** the system shows a validation error and does not submit any rule

#### Scenario: Delete attempted on the only remaining level
- **WHEN** an admin activates the delete action on a page with exactly one level
- **THEN** the system does not remove the level

### Requirement: Approver options are the organisation's roles
The system SHALL populate every level's Approver Select field with the organisation's roles, so an admin can only assign an approval level to a role that actually exists.

#### Scenario: Approver options loaded
- **WHEN** the Add/Edit Workflow page loads
- **THEN** every level's Approver Select offers every role in the organisation's role list

### Requirement: Adding and removing levels keeps step order sequential
The system SHALL, when "+ Add Level" is activated, append a new empty level numbered one past the current last level, and SHALL, when a level is deleted, renumber the remaining levels so they stay sequential starting at 1.

#### Scenario: Level added
- **WHEN** an admin activates "+ Add Level" on a page with levels numbered 1 and 2
- **THEN** a new empty level numbered 3 appears

#### Scenario: Level removed from the middle
- **WHEN** an admin deletes level 2 on a page with levels numbered 1, 2, and 3
- **THEN** the remaining levels are renumbered 1 and 2, preserving their original relative order

### Requirement: Levels are created without escalation, auto-approve, or optional-step settings
The system SHALL create every approval level as mandatory, with no escalation timer and no auto-approve timer, since the Add/Edit Workflow page does not expose controls for those settings in this change.

#### Scenario: Workflow saved
- **WHEN** an admin saves a workflow with one or more levels
- **THEN** each created rule is mandatory and has no escalation or auto-approve timer set

### Requirement: Submitting a valid new workflow creates its rules and adds it to the list
The system SHALL, when the Add Workflow page is submitted with a category and at least one valid level, create one approval-workflow rule per level (step order matching each level's position), navigate back to the Workflows list, show the new workflow's group in the visible list, and trigger a success notification.

#### Scenario: Workflow created successfully
- **WHEN** an admin submits the Add Workflow page with a category and valid levels and the creation succeeds
- **THEN** the system navigates back to the Workflows list, shows the new category's group with its levels in order, and triggers a success notification

### Requirement: Workflow creation failure keeps the admin on the page with entered values
The system SHALL, when creating a workflow's rules fails, trigger an error notification and SHALL keep the admin on the Add Workflow page with their entered values retained.

#### Scenario: Workflow creation fails
- **WHEN** an admin submits the Add Workflow page and the creation fails
- **THEN** the system triggers an error notification and the admin remains on the page with the entered values retained

### Requirement: Editing a workflow opens the same page pre-filled with its current levels
The system SHALL, when a group's "Edit" action is activated, navigate to the Edit Workflow page pre-filled with that visitor category's existing rules as ordered levels, each showing its current approver role.

#### Scenario: Edit opened
- **WHEN** an admin activates a workflow group's "Edit" action
- **THEN** the system navigates to the Edit Workflow page pre-filled with that category's existing levels in `stepOrder` order

### Requirement: Submitting a valid workflow edit reconciles its rules
The system SHALL, when the Edit Workflow page is submitted with at least one valid level, reconcile the visitor category's rules against the submitted levels — creating rules for new levels, updating rules whose approver or position changed, and deleting rules for removed levels — then navigate back to the Workflows list, reflect the updated levels in that category's group, and trigger a success notification.

#### Scenario: Workflow updated successfully
- **WHEN** an admin submits the Edit Workflow page with valid levels and the reconciliation succeeds
- **THEN** the system navigates back to the Workflows list, shows the updated levels in that category's group, and triggers a success notification

### Requirement: Workflow update failure keeps the admin on the page with entered values
The system SHALL, when reconciling a workflow's rules fails, trigger an error notification and SHALL keep the admin on the Edit Workflow page with their entered values retained.

#### Scenario: Workflow update fails
- **WHEN** an admin submits the Edit Workflow page and the reconciliation fails
- **THEN** the system triggers an error notification and the admin remains on the page with the entered values retained

### Requirement: Deleting a workflow requires confirmation
The system SHALL, when a group's "Delete" action is activated, show a confirmation dialog before deleting, and SHALL NOT delete any of that category's rules unless the admin confirms.

#### Scenario: Delete requested
- **WHEN** an admin activates a workflow group's "Delete" action
- **THEN** the system shows a confirmation dialog and does not yet delete any rule

#### Scenario: Delete cancelled
- **WHEN** an admin dismisses the delete confirmation dialog without confirming
- **THEN** the workflow's group remains in the list unchanged

### Requirement: Confirmed workflow deletion removes all of its rules and notifies on failure
The system SHALL, when the admin confirms deletion, delete every rule belonging to that visitor category, remove the category's group from the visible list, and trigger a success notification on success; on failure it SHALL trigger an error notification and leave the group in the list.

#### Scenario: Delete confirmed and succeeds
- **WHEN** an admin confirms deletion of a workflow and every rule deletion succeeds
- **THEN** the system removes that category's group from the list and triggers a success notification

#### Scenario: Delete confirmed and fails
- **WHEN** an admin confirms deletion of a workflow and any rule deletion fails
- **THEN** the system triggers an error notification and the group remains in the list
