# admin-host-employees Specification

## Purpose

The admin-host-employees capability is the Super Admin's Employees Directory at `/admin/host-employees`: it renders the Admin section shell with "Employees" active and lets an admin view, add, edit, and delete the internal staff authorized to sponsor and host corporate visitors.

## Requirements

### Requirement: Admin section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Employees page, and SHALL redirect to `/staff/login` instead of rendering the page when no token is present.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token navigates to `/admin/host-employees`
- **THEN** the system redirects to `/staff/login` and does not render the page

#### Scenario: Token present
- **WHEN** a browser with a staff auth token navigates to `/admin/host-employees`
- **THEN** the system renders the Employees page

### Requirement: Admin sidebar and top bar render with "Employees" active
The system SHALL render, for an authenticated session, the Admin sidebar with "Employees" shown as the active item, and the Admin top bar showing "Organization Admin" with the Employees-specific description and the signed-in staff member's name and role.

#### Scenario: Admin views the Employees page
- **WHEN** an authenticated admin's Employees page finishes loading
- **THEN** the sidebar shows "Employees" marked active and the top bar shows the signed-in staff member's name and role

### Requirement: Employee list loads on page entry
The system SHALL, when the Employees page loads, fetch the current list of employees and render one table row per employee showing its name, department, branch, email address, role/access, and status.

#### Scenario: Employees load successfully
- **WHEN** the Employees page loads and the fetch succeeds
- **THEN** the table shows one row per employee with its name, department, branch, email address, role/access, and status

### Requirement: Zero employees shows the shared empty state
The system SHALL show the shared empty-state component in place of the table's rows when the employee list loads successfully with zero employees.

#### Scenario: No employees exist
- **WHEN** the employee list loads successfully with zero employees
- **THEN** the system shows the shared empty-state component instead of any table rows

### Requirement: Employee list load failure is reported without crashing
The system SHALL, when the employee list fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the employee list fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: Add Employee navigates to a dedicated create page
The system SHALL, when "Add Employee" is activated from the Employees list, navigate to a dedicated create page instead of opening a modal.

#### Scenario: Add Employee activated
- **WHEN** an admin activates "Add Employee" on the Employees list
- **THEN** the system navigates to the create page

#### Scenario: Cancel on the create page
- **WHEN** an admin activates "Cancel" on the create page
- **THEN** the system navigates back to the Employees list without creating an employee

### Requirement: Creating or editing an employee requires name, department, email, and role/access
The system SHALL, on both the create page and the edit page, request the employee's name, department, email address, role/access level, and status, and SHALL require name, department, email address, and role/access to be non-empty before submission succeeds. Status defaults to active and is not required-validated.

#### Scenario: Required field left empty on create
- **WHEN** an admin submits the create page with name, department, email address, or role/access left empty
- **THEN** the system shows a validation error and does not submit the employee

#### Scenario: Required field left empty on edit
- **WHEN** an admin submits the edit page with name, department, email address, or role/access left empty
- **THEN** the system shows a validation error and does not submit the employee

### Requirement: Submitting a valid new employee adds it to the list
The system SHALL, when the create page is submitted with all required fields present, create the employee, navigate back to the Employees list, show the new employee in the visible list, and trigger a success notification.

#### Scenario: Employee created successfully
- **WHEN** an admin submits the create page with all required fields present and the creation succeeds
- **THEN** the system navigates back to the Employees list, shows the new employee in the table, and triggers a success notification

### Requirement: Employee creation failure keeps the form open with entered values
The system SHALL, when creating an employee fails, trigger an error notification and SHALL keep the admin on the create page with their entered values retained.

#### Scenario: Employee creation fails
- **WHEN** an admin submits the create page and the creation fails
- **THEN** the system triggers an error notification and the admin remains on the create page with the entered values retained

### Requirement: Editing an employee opens the form pre-filled with its current details
The system SHALL, when a row's "Edit" action is activated, navigate to the edit page pre-filled with that employee's current name, department, email address, role/access, and status.

#### Scenario: Edit opened
- **WHEN** an admin activates an employee row's "Edit" action
- **THEN** the system navigates to the edit page pre-filled with that employee's current details across every field

### Requirement: Submitting a valid employee edit updates the list
The system SHALL, when the edit page is submitted with all required fields present, update the employee, navigate back to the Employees list, reflect the updated details in the table, and trigger a success notification.

#### Scenario: Employee updated successfully
- **WHEN** an admin submits the edit page with all required fields present and the update succeeds
- **THEN** the system navigates back to the Employees list, shows the updated details in the table, and triggers a success notification

### Requirement: Employee update failure keeps the form open with entered values
The system SHALL, when updating an employee fails, trigger an error notification and SHALL leave the admin on the edit page with their entered values.

#### Scenario: Employee update fails
- **WHEN** an admin submits the edit page and the update fails
- **THEN** the system triggers an error notification and the admin remains on the edit page with the entered values

### Requirement: Deleting an employee requires confirmation
The system SHALL, when a row's "Delete" action is activated, show a confirmation dialog before deleting, and SHALL NOT delete the employee unless the admin confirms.

#### Scenario: Delete requested
- **WHEN** an admin activates an employee row's "Delete" action
- **THEN** the system shows a confirmation dialog and does not yet delete the employee

#### Scenario: Delete cancelled
- **WHEN** an admin dismisses the delete confirmation dialog without confirming
- **THEN** the employee remains in the table unchanged

### Requirement: Confirmed deletion removes the employee and notifies on failure
The system SHALL, when the admin confirms deletion, delete the employee, remove it from the visible list, and trigger a success notification on success; on failure it SHALL trigger an error notification and leave the employee in the list.

#### Scenario: Delete confirmed and succeeds
- **WHEN** an admin confirms deletion of an employee and the deletion succeeds
- **THEN** the system removes that employee from the table and triggers a success notification

#### Scenario: Delete confirmed and fails
- **WHEN** an admin confirms deletion of an employee and the deletion fails
- **THEN** the system triggers an error notification and the employee remains in the table

### Requirement: Import Hosts is presented but not yet functional
The system SHALL display the "Import Hosts" control per the design, but SHALL NOT import any host employees when it is activated.

#### Scenario: Import Hosts activated
- **WHEN** an admin activates "Import Hosts"
- **THEN** no host employees are imported and the visible list does not change

### Requirement: Employee list can be filtered by department, role, and status
The system SHALL, when "Filters" is activated, show a filter panel offering Department, Role, and Status fields (each defaulting to "All"), and SHALL narrow the visible employees to those matching every selected filter as soon as a filter changes, without a separate confirm step. The system SHALL let an admin clear all active filters back to "All" in one action.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the system shows the Department, Role, and Status filter fields

#### Scenario: Filter selected narrows the list
- **WHEN** an admin selects a specific Department, Role, or Status value
- **THEN** the table immediately shows only employees matching every currently selected filter

#### Scenario: Multiple filters combine
- **WHEN** an admin has selected values for more than one of Department, Role, and Status
- **THEN** the table shows only employees matching all of the selected filters at once

#### Scenario: Filters cleared
- **WHEN** an admin activates "Clear filters"
- **THEN** every filter resets to "All" and the table shows the full employee list again

### Requirement: No filter matches shows a distinct empty state
The system SHALL, when one or more filters or a search are active and no employee matches them, show a message indicating no employees match the current search or filters, distinct from the message shown when the organisation has zero employees at all.

#### Scenario: No matches for active filters
- **WHEN** one or more filters are active and no employee matches them
- **THEN** the system shows a "no employees match" message instead of the zero-employees empty state

#### Scenario: No matches for search text
- **WHEN** search text is entered and no employee matches it
- **THEN** the system shows the "no employees match" message instead of the zero-employees empty state

### Requirement: Employee list can be searched by name, email, or employee code
The system SHALL show a search box on the Employees page and SHALL narrow the employee list server-side to employees whose full name, email, or employee code contains the typed text (case-insensitive), sending the text as the `search` parameter of the employees list request. The system SHALL send the trimmed text only after typing has paused for about 300 ms, SHALL omit the parameter when the trimmed text is empty, SHALL limit the input to 255 characters, and SHALL return to the first page whenever the search text changes. Search SHALL combine with the Department, Role, and Status filters so that only employees matching all of them are shown, and the total and page count SHALL reflect the searched results.

#### Scenario: Search narrows the list
- **WHEN** an admin types "dina" into the search box and pauses
- **THEN** the table shows only employees whose name, email, or employee code contains "dina", ignoring case

#### Scenario: Typing does not request on every keystroke
- **WHEN** an admin types several characters in quick succession
- **THEN** the system sends a single list request after typing pauses, not one per keystroke

#### Scenario: Search resets to the first page
- **WHEN** an admin is on a later page and changes the search text
- **THEN** the list reloads from page 1

#### Scenario: Search combines with filters
- **WHEN** an admin has entered search text and selected a Department, Role, or Status filter
- **THEN** the table shows only employees matching the search and every selected filter

#### Scenario: Blank search behaves as no search
- **WHEN** the search box is empty or contains only whitespace
- **THEN** the list request carries no `search` parameter and the full (filtered) list is shown

#### Scenario: Pagination reflects search results
- **WHEN** a search matches fewer employees than a full page
- **THEN** the pagination controls reflect the reduced total
