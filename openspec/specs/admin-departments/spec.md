# admin-departments Specification

## Purpose

The admin-departments capability is the Super Admin's Departments Register screen at `/admin/departments`, plus its Add/Edit Department page: it lets an admin view, add, edit, and delete the organisation's departments, each associated with a branch.

## Requirements

### Requirement: Admin section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Departments list or the Add/Edit Department page, and SHALL redirect to `/staff/login` instead of rendering when no token is present.

#### Scenario: No token present on the list
- **WHEN** a browser without a staff auth token navigates to `/admin/departments`
- **THEN** the system redirects to `/staff/login` and does not render the page

#### Scenario: No token present on the form
- **WHEN** a browser without a staff auth token navigates to `/admin/departments/new`
- **THEN** the system redirects to `/staff/login` and does not render the page

### Requirement: Admin sidebar and top bar render with "Departments" active
The system SHALL render, for an authenticated session, the Admin sidebar with "Departments" shown as the active item, and the Admin top bar showing "Organization Admin" with the Departments-specific description and the signed-in staff member's name and role.

#### Scenario: Admin views the Departments page
- **WHEN** an authenticated admin's Departments page finishes loading
- **THEN** the sidebar shows "Departments" marked active and the top bar shows the signed-in staff member's name and role

### Requirement: Department list loads on page entry
The system SHALL, when the Departments page loads, fetch the current list of departments and render one table row per department showing its name, branch, head of department, employee count, and status.

#### Scenario: Departments load successfully
- **WHEN** the Departments page loads and the fetch succeeds
- **THEN** the table shows one row per department with its name, branch, head of department, employee count, and status

### Requirement: Zero departments shows the shared empty state
The system SHALL show the shared empty-state component in place of the table's rows when the department list loads successfully with zero departments.

#### Scenario: No departments exist
- **WHEN** the department list loads successfully with zero departments
- **THEN** the system shows the shared empty-state component instead of any table rows

### Requirement: Department list load failure is reported without crashing
The system SHALL, when the department list fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the department list fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: Add Department navigates to a dedicated page
The system SHALL, when "Add Department" is activated from the Departments list, navigate to a dedicated Add Department page.

#### Scenario: Add Department activated
- **WHEN** an admin activates "Add Department" on the Departments list
- **THEN** the system navigates to the Add Department page

#### Scenario: Cancel on the Add Department page
- **WHEN** an admin activates "Cancel" on the Add Department page
- **THEN** the system navigates back to the Departments list without creating a department

### Requirement: Adding a department requires a name and a branch
The system SHALL, on the Add Department page, request the department name, an associated branch (chosen from the organisation's existing branches), a head of department, a description, and an active/inactive status, and SHALL require the department name and branch to be non-empty before submission succeeds. Head of department, description, and status are optional (status defaults to active).

#### Scenario: Required field left empty
- **WHEN** an admin submits the Add Department page with the department name or branch left empty
- **THEN** the system shows a validation error and does not submit the department

### Requirement: Branch options come from the organisation's existing branches
The system SHALL populate the Branch field's options from the same branch data the Branches Register page lists, so an admin can only associate a department with a branch that actually exists.

#### Scenario: Branch options loaded
- **WHEN** the Add Department page loads
- **THEN** the Branch field offers every branch currently in the organisation's branch list

### Requirement: Submitting a valid new department adds it to the list
The system SHALL, when the Add Department page is submitted with all required fields present, create the department, navigate back to the Departments list, show the new department in the visible list, and trigger a success notification.

#### Scenario: Department created successfully
- **WHEN** an admin submits the Add Department page with all required fields present and the creation succeeds
- **THEN** the system navigates back to the Departments list, shows the new department in the table, and triggers a success notification

### Requirement: Department creation failure keeps the admin on the page with entered values
The system SHALL, when creating a department fails, trigger an error notification and SHALL keep the admin on the Add Department page with their entered values retained.

#### Scenario: Department creation fails
- **WHEN** an admin submits the Add Department page and the creation fails
- **THEN** the system triggers an error notification and the admin remains on the page with the entered values retained

### Requirement: Editing a department opens the same page pre-filled with its current details
The system SHALL, when a row's "Edit" action is activated, navigate to the Edit Department page pre-filled with that department's current name, branch, head of department, description, and status.

#### Scenario: Edit opened
- **WHEN** an admin activates a department row's "Edit" action
- **THEN** the system navigates to the Edit Department page pre-filled with that department's current details

### Requirement: Submitting a valid department edit updates the list
The system SHALL, when the Edit Department page is submitted with all required fields present, update the department, navigate back to the Departments list, reflect the updated details in the table, and trigger a success notification.

#### Scenario: Department updated successfully
- **WHEN** an admin submits the Edit Department page with all required fields present and the update succeeds
- **THEN** the system navigates back to the Departments list, shows the updated details in the table, and triggers a success notification

### Requirement: Department update failure keeps the admin on the page with entered values
The system SHALL, when updating a department fails, trigger an error notification and SHALL keep the admin on the Edit Department page with their entered values retained.

#### Scenario: Department update fails
- **WHEN** an admin submits the Edit Department page and the update fails
- **THEN** the system triggers an error notification and the admin remains on the page with the entered values retained

### Requirement: Deleting a department requires confirmation
The system SHALL, when a row's "Delete" action is activated, show a confirmation dialog before deleting, and SHALL NOT delete the department unless the admin confirms.

#### Scenario: Delete requested
- **WHEN** an admin activates a department row's "Delete" action
- **THEN** the system shows a confirmation dialog and does not yet delete the department

#### Scenario: Delete cancelled
- **WHEN** an admin dismisses the delete confirmation dialog without confirming
- **THEN** the department remains in the table unchanged

### Requirement: Confirmed deletion removes the department and notifies on failure
The system SHALL, when the admin confirms deletion, delete the department, remove it from the visible list, and trigger a success notification on success; on failure it SHALL trigger an error notification and leave the department in the list.

#### Scenario: Delete confirmed and succeeds
- **WHEN** an admin confirms deletion of a department and the deletion succeeds
- **THEN** the system removes that department from the table and triggers a success notification

#### Scenario: Delete confirmed and fails
- **WHEN** an admin confirms deletion of a department and the deletion fails
- **THEN** the system triggers an error notification and the department remains in the table

### Requirement: Filters affordance is presented but not yet functional
The system SHALL display the "Filters" control per the design, but SHALL NOT apply any filtering when it is activated.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the visible departments do not change
