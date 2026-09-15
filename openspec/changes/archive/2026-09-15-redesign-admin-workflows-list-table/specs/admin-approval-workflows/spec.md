## MODIFIED Requirements

### Requirement: Add Workflow navigates to a dedicated page
The system SHALL, when "Create Workflow" is activated from the Workflows list, navigate to a dedicated Add Workflow page.

#### Scenario: Add Workflow activated
- **WHEN** an admin activates "Create Workflow" on the Workflows list
- **THEN** the system navigates to the Add Workflow page

#### Scenario: Cancel on the Add Workflow page
- **WHEN** an admin activates "Cancel" on the Add Workflow page
- **THEN** the system navigates back to the Workflows list without creating any rules

## ADDED Requirements

### Requirement: Workflow list renders as a table with Status, Approval Flow, and Levels columns
The system SHALL render each visitor category's workflow as one row in a table with columns Workflow (the category name), Status, Approval Flow, Levels, and Actions, in place of a stacked card layout. The Approval Flow cell SHALL join the group's levels, in `stepOrder` order, by their approver role name separated by " → ". The Levels cell SHALL show the count of levels in the group as "N levels".

#### Scenario: Workflow row rendered
- **WHEN** the Workflows page renders a group with levels ordered "Reception", "Manager", "Host"
- **THEN** the row's Approval Flow cell shows "Reception → Manager → Host" and its Levels cell shows "3 levels"

### Requirement: Workflow status badge is derived from its rules' active state
The system SHALL show a Status badge on each workflow row: "Active" when every rule in that visitor category's group has `isActive: true`, and "Paused" when any rule in the group has `isActive: false`.

#### Scenario: All rules active
- **WHEN** a workflow's group has every rule with `isActive: true`
- **THEN** its row shows an "Active" status badge

#### Scenario: Any rule inactive
- **WHEN** a workflow's group has at least one rule with `isActive: false`
- **THEN** its row shows a "Paused" status badge

### Requirement: Workflow list header shows a live count of loaded workflows
The system SHALL show, above the table, a count of the currently loaded workflows as "N workflows".

#### Scenario: Count reflects loaded workflows
- **WHEN** the Workflows page has 4 groups loaded
- **THEN** the header subtitle reads "4 workflows"

### Requirement: Workflow list paginates client-side over the already-loaded groups
The system SHALL paginate the loaded, grouped workflow list on the client, showing a fixed page size per screen, a "Showing X–Y of N workflows" caption, and Previous/Next controls that move between pages without any additional network request. Previous SHALL be disabled on the first page and Next SHALL be disabled on the last page.

#### Scenario: Navigating to the next page
- **WHEN** an admin activates "Next" while viewing a page that is not the last page
- **THEN** the system shows the next page of workflow rows and updates the "Showing X–Y of N" caption without an additional fetch

#### Scenario: Previous disabled on first page
- **WHEN** the Workflows list is showing its first page
- **THEN** the "Previous" control is disabled

#### Scenario: Next disabled on last page
- **WHEN** the Workflows list is showing its last page
- **THEN** the "Next" control is disabled
