# admin-branches Specification

## Purpose

The admin-branches capability is the Super Admin's Branches Register screen at `/admin/branches`: it renders the Admin section shell with "Branches" active and lets an admin view, add, edit, and delete the organisation's geographical branches.

## Requirements

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

### Requirement: Add Branch navigates to a dedicated create page
The system SHALL, when "Add Branch" is activated from the Branches list, navigate to a dedicated create-branch page instead of opening a modal.

#### Scenario: Add Branch activated
- **WHEN** an admin activates "Add Branch" on the Branches list
- **THEN** the system navigates to the create-branch page

#### Scenario: Cancel on the create page
- **WHEN** an admin activates "Cancel" on the create-branch page
- **THEN** the system navigates back to the Branches list without creating a branch

### Requirement: Creating or editing a branch requires the full identity, geography, and operations field set
The system SHALL, on both the create-branch page and the edit-branch form, request branch name, branch code, location/city, country, physical address, contact person, contact email, contact phone, operating hours (from/to), operational status, and internal notes, and SHALL require branch name, branch code, location/city, country, physical address, contact person, contact email, and contact phone to be non-empty before submission succeeds. Operating hours, operational status, and internal notes are optional.

#### Scenario: Required field left empty on create
- **WHEN** an admin submits the create-branch page with branch name, branch code, location/city, country, physical address, contact person, contact email, or contact phone left empty
- **THEN** the system shows a validation error and does not submit the branch

#### Scenario: Required field left empty on edit
- **WHEN** an admin submits the edit-branch form with branch name, branch code, location/city, country, physical address, contact person, contact email, or contact phone left empty
- **THEN** the system shows a validation error and does not submit the branch

### Requirement: Submitting a valid new branch adds it to the list
The system SHALL, when the create-branch page is submitted with all required fields present, create the branch, navigate back to the Branches list, show the new branch in the visible list, and trigger a success notification.

#### Scenario: Branch created successfully
- **WHEN** an admin submits the create-branch page with all required fields present and the creation succeeds
- **THEN** the system navigates back to the Branches list, shows the new branch in the table, and triggers a success notification

### Requirement: Branch creation failure keeps the form open with entered values
The system SHALL, when creating a branch fails, trigger an error notification and SHALL keep the admin on the create-branch page with their entered values retained.

#### Scenario: Branch creation fails
- **WHEN** an admin submits the create-branch page and the creation fails
- **THEN** the system triggers an error notification and the admin remains on the create-branch page with the entered values retained

### Requirement: Editing a branch opens the form pre-filled with its current details
The system SHALL, when a row's "Edit" action is activated, open a modal form pre-filled with that branch's current branch name, branch code, location/city, country, physical address, contact person, contact email, contact phone, operating hours, operational status, and internal notes.

#### Scenario: Edit opened
- **WHEN** an admin activates a branch row's "Edit" action
- **THEN** the system opens the edit modal pre-filled with that branch's current details across every field

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

### Requirement: Branch list can be filtered by status
The system SHALL, when "Filters" is activated, show a filter panel offering a Status field (Active/Inactive, defaulting to "All"), and SHALL narrow the visible branches to those matching the selected status as soon as it changes, without a separate confirm step. The system SHALL let an admin clear the active filter back to "All".

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the system shows the Status filter field

#### Scenario: Filter selected narrows the list
- **WHEN** an admin selects a specific Status value
- **THEN** the table immediately shows only branches matching that status

#### Scenario: Filters cleared
- **WHEN** an admin activates "Clear filters"
- **THEN** the filter resets to "All" and the table shows the full branch list again

### Requirement: No filter matches shows a distinct empty state
The system SHALL, when a filter is active and no branch matches it, show a message indicating no branches match the current filters, distinct from the message shown when the organisation has zero branches at all.

#### Scenario: No matches for active filter
- **WHEN** a filter is active and no branch matches it
- **THEN** the system shows a "no branches match these filters" message instead of the zero-branches empty state
