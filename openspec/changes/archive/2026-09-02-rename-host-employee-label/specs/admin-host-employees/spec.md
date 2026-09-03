## MODIFIED Requirements

### Requirement: Admin section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Employees page, and SHALL redirect to `/staff/login` instead of rendering the page when no token is present.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token navigates to `/admin/host-employees`
- **THEN** the system redirects to `/staff/login` and does not render the page

#### Scenario: Token present
- **WHEN** a browser with a staff auth token navigates to `/admin/host-employees`
- **THEN** the system renders the Employees page

## REMOVED Requirements

### Requirement: Admin sidebar and top bar render with "Host Employees" active
**Reason**: "Host Employees" is being relabeled to "Employees" throughout the admin UI; see the new requirement below.
**Migration**: No admin-facing migration — the sidebar item and top bar now read "Employees" instead of "Host Employees"; the route and sidebar key are unchanged.

### Requirement: Host employee list loads on page entry
**Reason**: Relabeled to "Employee list loads on page entry" as part of the "Host Employee" → "Employee" rename.
**Migration**: No admin-facing migration — same behavior, relabeled wording.

### Requirement: Zero host employees shows the shared empty state
**Reason**: Relabeled to "Zero employees shows the shared empty state" as part of the rename.
**Migration**: No admin-facing migration — same behavior, relabeled wording.

### Requirement: Host employee list load failure is reported without crashing
**Reason**: Relabeled to "Employee list load failure is reported without crashing" as part of the rename.
**Migration**: No admin-facing migration — same behavior, relabeled wording.

### Requirement: Add Host Employee navigates to a dedicated create page
**Reason**: The button is relabeled "Add Employee"; requirement relabeled to match.
**Migration**: No admin-facing migration — same behavior, relabeled wording.

### Requirement: Creating or editing a host employee requires name, department, email, and role/access
**Reason**: Relabeled to "Creating or editing an employee requires..." as part of the rename.
**Migration**: No admin-facing migration — same behavior, relabeled wording.

### Requirement: Submitting a valid new host employee adds it to the list
**Reason**: Relabeled to "Submitting a valid new employee adds it to the list" as part of the rename.
**Migration**: No admin-facing migration — same behavior, relabeled wording.

### Requirement: Host employee creation failure keeps the form open with entered values
**Reason**: Relabeled to "Employee creation failure keeps the form open with entered values" as part of the rename.
**Migration**: No admin-facing migration — same behavior, relabeled wording.

### Requirement: Editing a host employee opens the form pre-filled with its current details
**Reason**: Relabeled to "Editing an employee opens the form pre-filled with its current details" as part of the rename.
**Migration**: No admin-facing migration — same behavior, relabeled wording.

### Requirement: Submitting a valid host employee edit updates the list
**Reason**: Relabeled to "Submitting a valid employee edit updates the list" as part of the rename.
**Migration**: No admin-facing migration — same behavior, relabeled wording.

### Requirement: Host employee update failure keeps the form open with entered values
**Reason**: Relabeled to "Employee update failure keeps the form open with entered values" as part of the rename.
**Migration**: No admin-facing migration — same behavior, relabeled wording.

### Requirement: Deleting a host employee requires confirmation
**Reason**: Relabeled to "Deleting an employee requires confirmation" as part of the rename.
**Migration**: No admin-facing migration — same behavior, relabeled wording.

### Requirement: Confirmed deletion removes the host employee and notifies on failure
**Reason**: Relabeled to "Confirmed deletion removes the employee and notifies on failure" as part of the rename.
**Migration**: No admin-facing migration — same behavior, relabeled wording.

## ADDED Requirements

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
