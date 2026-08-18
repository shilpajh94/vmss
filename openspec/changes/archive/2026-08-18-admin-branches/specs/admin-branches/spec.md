## Purpose

The admin-branches capability is the Super Admin's Branches Register screen at `/admin/branches`: it renders the Admin section shell with "Branches" active and lets an admin view, add, edit, and delete the organisation's geographical branches.

## ADDED Requirements

### Requirement: Admin section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Branches page, and SHALL redirect to `/staff/login` instead of rendering the page when no token is present.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token navigates to `/admin/branches`
- **THEN** the system redirects to `/staff/login` and does not render the page

#### Scenario: Token present
- **WHEN** a browser with a staff auth token navigates to `/admin/branches`
- **THEN** the system renders the Branches page

### Requirement: Admin sidebar and top bar render with "Branches" active
The system SHALL render, for an authenticated session, the Admin sidebar with "Branches" shown as the active item, and the Admin top bar showing "Organization Admin" with the Branches-specific description and the signed-in staff member's name and role.

#### Scenario: Admin views the Branches page
- **WHEN** an authenticated admin's Branches page finishes loading
- **THEN** the sidebar shows "Branches" marked active and the top bar shows the signed-in staff member's name and role

### Requirement: Branch list loads on page entry
The system SHALL, when the Branches page loads, fetch the current list of branches and render one table row per branch showing its name, location/city, branch code, contact person, and status.

#### Scenario: Branches load successfully
- **WHEN** the Branches page loads and the fetch succeeds
- **THEN** the table shows one row per branch with its name, location/city, branch code, contact person, and status

### Requirement: Zero branches shows the shared empty state
The system SHALL show the shared empty-state component in place of the table's rows when the branch list loads successfully with zero branches.

#### Scenario: No branches exist
- **WHEN** the branch list loads successfully with zero branches
- **THEN** the system shows the shared empty-state component instead of any table rows

### Requirement: Branch list load failure is reported without crashing
The system SHALL, when the branch list fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the branch list fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: Adding a branch requires name, location/city, branch code, and contact person
The system SHALL, when "Add Branch" is activated, open a form requesting the branch name, location/city, branch code, contact person, and active/inactive status, and SHALL require name, location/city, branch code, and contact person to be non-empty before submission succeeds.

#### Scenario: Add Branch opened
- **WHEN** an admin activates "Add Branch"
- **THEN** the system opens a form for entering a new branch's details

#### Scenario: Required field left empty
- **WHEN** an admin submits the add-branch form with the branch name, location/city, branch code, or contact person left empty
- **THEN** the system shows a validation error and does not submit the branch

### Requirement: Submitting a valid new branch adds it to the list
The system SHALL, when the add-branch form is submitted with all required fields present, create the branch, close the form, add the new branch to the visible list, and trigger a success notification.

#### Scenario: Branch created successfully
- **WHEN** an admin submits the add-branch form with all required fields present and the creation succeeds
- **THEN** the system closes the form, shows the new branch in the table, and triggers a success notification

### Requirement: Branch creation failure keeps the form open with entered values
The system SHALL, when creating a branch fails, trigger an error notification and SHALL leave the add-branch form open with the admin's entered values.

#### Scenario: Branch creation fails
- **WHEN** an admin submits the add-branch form and the creation fails
- **THEN** the system triggers an error notification and the form remains open with the entered values

### Requirement: Editing a branch opens the form pre-filled with its current details
The system SHALL, when a row's "Edit" action is activated, open the same form used for adding a branch, pre-filled with that branch's current name, location/city, branch code, contact person, and status.

#### Scenario: Edit opened
- **WHEN** an admin activates a branch row's "Edit" action
- **THEN** the system opens the form pre-filled with that branch's current details

### Requirement: Submitting a valid branch edit updates the list
The system SHALL, when the edit form is submitted with all required fields present, update the branch, close the form, reflect the updated details in the table, and trigger a success notification.

#### Scenario: Branch updated successfully
- **WHEN** an admin submits the edit form with all required fields present and the update succeeds
- **THEN** the system closes the form, shows the updated details in the table, and triggers a success notification

### Requirement: Branch update failure keeps the form open with entered values
The system SHALL, when updating a branch fails, trigger an error notification and SHALL leave the edit form open with the admin's entered values.

#### Scenario: Branch update fails
- **WHEN** an admin submits the edit form and the update fails
- **THEN** the system triggers an error notification and the form remains open with the entered values

### Requirement: Deleting a branch requires confirmation
The system SHALL, when a row's "Delete" action is activated, show a confirmation dialog before deleting, and SHALL NOT delete the branch unless the admin confirms.

#### Scenario: Delete requested
- **WHEN** an admin activates a branch row's "Delete" action
- **THEN** the system shows a confirmation dialog and does not yet delete the branch

#### Scenario: Delete cancelled
- **WHEN** an admin dismisses the delete confirmation dialog without confirming
- **THEN** the branch remains in the table unchanged

### Requirement: Confirmed deletion removes the branch and notifies on failure
The system SHALL, when the admin confirms deletion, delete the branch, remove it from the visible list, and trigger a success notification on success; on failure it SHALL trigger an error notification and leave the branch in the list.

#### Scenario: Delete confirmed and succeeds
- **WHEN** an admin confirms deletion of a branch and the deletion succeeds
- **THEN** the system removes that branch from the table and triggers a success notification

#### Scenario: Delete confirmed and fails
- **WHEN** an admin confirms deletion of a branch and the deletion fails
- **THEN** the system triggers an error notification and the branch remains in the table

### Requirement: Filters affordance is presented but not yet functional
The system SHALL display the "Filters" control per the design, but SHALL NOT apply any filtering when it is activated.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the visible branches do not change
