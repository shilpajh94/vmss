# admin-host-employees Specification

## Purpose

The admin-host-employees capability is the Super Admin's Host Employees Directory at `/admin/host-employees`: it renders the Admin section shell with "Host Employees" active and lets an admin view, add, edit, and delete the internal staff authorized to sponsor and host corporate visitors.

## Requirements

### Requirement: Admin section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Host Employees page, and SHALL redirect to `/staff/login` instead of rendering the page when no token is present.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token navigates to `/admin/host-employees`
- **THEN** the system redirects to `/staff/login` and does not render the page

#### Scenario: Token present
- **WHEN** a browser with a staff auth token navigates to `/admin/host-employees`
- **THEN** the system renders the Host Employees page

### Requirement: Admin sidebar and top bar render with "Host Employees" active
The system SHALL render, for an authenticated session, the Admin sidebar with "Host Employees" shown as the active item, and the Admin top bar showing "Organization Admin" with the Host-Employees-specific description and the signed-in staff member's name and role.

#### Scenario: Admin views the Host Employees page
- **WHEN** an authenticated admin's Host Employees page finishes loading
- **THEN** the sidebar shows "Host Employees" marked active and the top bar shows the signed-in staff member's name and role

### Requirement: Host employee list loads on page entry
The system SHALL, when the Host Employees page loads, fetch the current list of host employees and render one table row per host employee showing its name, department, branch, email address, role/access, and status.

#### Scenario: Host employees load successfully
- **WHEN** the Host Employees page loads and the fetch succeeds
- **THEN** the table shows one row per host employee with its name, department, branch, email address, role/access, and status

### Requirement: Zero host employees shows the shared empty state
The system SHALL show the shared empty-state component in place of the table's rows when the host employee list loads successfully with zero host employees.

#### Scenario: No host employees exist
- **WHEN** the host employee list loads successfully with zero host employees
- **THEN** the system shows the shared empty-state component instead of any table rows

### Requirement: Host employee list load failure is reported without crashing
The system SHALL, when the host employee list fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the host employee list fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: Add Host Employee navigates to a dedicated create page
The system SHALL, when "Add Host Employee" is activated from the Host Employees list, navigate to a dedicated create page instead of opening a modal.

#### Scenario: Add Host Employee activated
- **WHEN** an admin activates "Add Host Employee" on the Host Employees list
- **THEN** the system navigates to the create page

#### Scenario: Cancel on the create page
- **WHEN** an admin activates "Cancel" on the create page
- **THEN** the system navigates back to the Host Employees list without creating a host employee

### Requirement: Creating or editing a host employee requires name, department, email, and role/access
The system SHALL, on both the create page and the edit page, request the host employee's name, department, email address, role/access level, and status, and SHALL require name, department, email address, and role/access to be non-empty before submission succeeds. Status defaults to active and is not required-validated.

#### Scenario: Required field left empty on create
- **WHEN** an admin submits the create page with name, department, email address, or role/access left empty
- **THEN** the system shows a validation error and does not submit the host employee

#### Scenario: Required field left empty on edit
- **WHEN** an admin submits the edit page with name, department, email address, or role/access left empty
- **THEN** the system shows a validation error and does not submit the host employee

### Requirement: Submitting a valid new host employee adds it to the list
The system SHALL, when the create page is submitted with all required fields present, create the host employee, navigate back to the Host Employees list, show the new host employee in the visible list, and trigger a success notification.

#### Scenario: Host employee created successfully
- **WHEN** an admin submits the create page with all required fields present and the creation succeeds
- **THEN** the system navigates back to the Host Employees list, shows the new host employee in the table, and triggers a success notification

### Requirement: Host employee creation failure keeps the form open with entered values
The system SHALL, when creating a host employee fails, trigger an error notification and SHALL keep the admin on the create page with their entered values retained.

#### Scenario: Host employee creation fails
- **WHEN** an admin submits the create page and the creation fails
- **THEN** the system triggers an error notification and the admin remains on the create page with the entered values retained

### Requirement: Editing a host employee opens the form pre-filled with its current details
The system SHALL, when a row's "Edit" action is activated, navigate to the edit page pre-filled with that host employee's current name, department, email address, role/access, and status.

#### Scenario: Edit opened
- **WHEN** an admin activates a host employee row's "Edit" action
- **THEN** the system navigates to the edit page pre-filled with that host employee's current details across every field

### Requirement: Submitting a valid host employee edit updates the list
The system SHALL, when the edit page is submitted with all required fields present, update the host employee, navigate back to the Host Employees list, reflect the updated details in the table, and trigger a success notification.

#### Scenario: Host employee updated successfully
- **WHEN** an admin submits the edit page with all required fields present and the update succeeds
- **THEN** the system navigates back to the Host Employees list, shows the updated details in the table, and triggers a success notification

### Requirement: Host employee update failure keeps the form open with entered values
The system SHALL, when updating a host employee fails, trigger an error notification and SHALL leave the admin on the edit page with their entered values.

#### Scenario: Host employee update fails
- **WHEN** an admin submits the edit page and the update fails
- **THEN** the system triggers an error notification and the admin remains on the edit page with the entered values

### Requirement: Deleting a host employee requires confirmation
The system SHALL, when a row's "Delete" action is activated, show a confirmation dialog before deleting, and SHALL NOT delete the host employee unless the admin confirms.

#### Scenario: Delete requested
- **WHEN** an admin activates a host employee row's "Delete" action
- **THEN** the system shows a confirmation dialog and does not yet delete the host employee

#### Scenario: Delete cancelled
- **WHEN** an admin dismisses the delete confirmation dialog without confirming
- **THEN** the host employee remains in the table unchanged

### Requirement: Confirmed deletion removes the host employee and notifies on failure
The system SHALL, when the admin confirms deletion, delete the host employee, remove it from the visible list, and trigger a success notification on success; on failure it SHALL trigger an error notification and leave the host employee in the list.

#### Scenario: Delete confirmed and succeeds
- **WHEN** an admin confirms deletion of a host employee and the deletion succeeds
- **THEN** the system removes that host employee from the table and triggers a success notification

#### Scenario: Delete confirmed and fails
- **WHEN** an admin confirms deletion of a host employee and the deletion fails
- **THEN** the system triggers an error notification and the host employee remains in the table

### Requirement: Filters and Import Hosts are presented but not yet functional
The system SHALL display the "Filters" and "Import Hosts" controls per the design, but SHALL NOT apply any filtering or import when either is activated.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the visible host employees do not change

#### Scenario: Import Hosts activated
- **WHEN** an admin activates "Import Hosts"
- **THEN** no host employees are imported and the visible list does not change
