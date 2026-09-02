# admin-floors Specification

## Purpose

The admin-floors capability is the Super Admin's global Floors Inventory screen at `/admin/floors`, plus its Add/Edit Floor page: it lets an admin view, add, edit, and delete a floor belonging to any building, including its capacity, access level, associated departments, and status.

## Requirements

### Requirement: Admin section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Floors list or the Add/Edit Floor page, and SHALL redirect to `/staff/login` instead of rendering when no token is present.

#### Scenario: No token present on the list
- **WHEN** a browser without a staff auth token navigates to `/admin/floors`
- **THEN** the system redirects to `/staff/login` and does not render the page

#### Scenario: No token present on the form
- **WHEN** a browser without a staff auth token navigates to `/admin/floors/new`
- **THEN** the system redirects to `/staff/login` and does not render the page

### Requirement: Admin sidebar and top bar render with "Floors" active
The system SHALL render, for an authenticated session, the Admin sidebar with "Floors" shown as the active item, and the Admin top bar showing "Organization Admin" with the Floors-specific description and the signed-in staff member's name and role.

#### Scenario: Admin views the Floors page
- **WHEN** an authenticated admin's Floors page finishes loading
- **THEN** the sidebar shows "Floors" marked active and the top bar shows the signed-in staff member's name and role

### Requirement: Floor list loads on page entry, spanning every building
The system SHALL, when the Floors page loads, fetch every building and every department, and render one table row per floor — across all buildings — showing its name/number, parent building, associated department names, capacity, access level, and status.

#### Scenario: Floors load successfully
- **WHEN** the Floors page loads and the fetch succeeds
- **THEN** the table shows one row per floor, across every building, with its name/number, building, department names, capacity, access level, and status

### Requirement: Zero floors shows the shared empty state
The system SHALL show the shared empty-state component in place of the table's rows when, across every building, there are zero floors.

#### Scenario: No floors exist
- **WHEN** the floor list loads successfully and no building has any floors
- **THEN** the system shows the shared empty-state component instead of any table rows

### Requirement: Floor list load failure is reported without crashing
The system SHALL, when the floor list fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the floor list fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: Add Floor navigates to a dedicated page
The system SHALL, when "Add Floor" is activated from the Floors list, navigate to a dedicated Add Floor page.

#### Scenario: Add Floor activated
- **WHEN** an admin activates "Add Floor" on the Floors list
- **THEN** the system navigates to the Add Floor page

#### Scenario: Cancel on the Add Floor page
- **WHEN** an admin activates "Cancel" on the Add Floor page
- **THEN** the system navigates back to the Floors list without creating a floor

### Requirement: Adding a floor requires a name and a building
The system SHALL, on the Add Floor page, request the floor name, an associated building (chosen from every existing building), a capacity count and unit (Guests or Staff), an access level (Public, Restricted, or Secure), zero or more associated departments, and an active/inactive status, and SHALL require the floor name and building to be non-empty before submission succeeds. Capacity, access level, departments, and status are optional (access level defaults to Public, status defaults to active).

#### Scenario: Required field left empty
- **WHEN** an admin submits the Add Floor page with the floor name or building left empty
- **THEN** the system shows a validation error and does not submit the floor

### Requirement: Building and department options come from existing data
The system SHALL populate the Building field's options from every existing building, and the Department(s) selector's options from every existing department.

#### Scenario: Options loaded
- **WHEN** the Add Floor page loads
- **THEN** the Building field offers every existing building and the Department(s) selector offers every existing department

### Requirement: Submitting a valid new floor adds it to the list
The system SHALL, when the Add Floor page is submitted with all required fields present, add the floor to its selected building's floor data, navigate back to the Floors list, show the new floor in the visible list, and trigger a success notification.

#### Scenario: Floor created successfully
- **WHEN** an admin submits the Add Floor page with all required fields present and the creation succeeds
- **THEN** the system navigates back to the Floors list, shows the new floor in the table, and triggers a success notification

### Requirement: Floor creation failure keeps the admin on the page with entered values
The system SHALL, when creating a floor fails, trigger an error notification and SHALL keep the admin on the Add Floor page with their entered values retained.

#### Scenario: Floor creation fails
- **WHEN** an admin submits the Add Floor page and the creation fails
- **THEN** the system triggers an error notification and the admin remains on the page with the entered values retained

### Requirement: Editing a floor opens the same page pre-filled with its current details
The system SHALL, when a row's "Edit" action is activated, navigate to the Edit Floor page pre-filled with that floor's current name, building, capacity, access level, associated departments, and status.

#### Scenario: Edit opened
- **WHEN** an admin activates a floor row's "Edit" action
- **THEN** the system navigates to the Edit Floor page pre-filled with that floor's current details

### Requirement: Submitting a valid floor edit updates the list
The system SHALL, when the Edit Floor page is submitted with all required fields present, update the floor within its building's data, navigate back to the Floors list, reflect the updated details in the table, and trigger a success notification.

#### Scenario: Floor updated successfully
- **WHEN** an admin submits the Edit Floor page with all required fields present and the update succeeds
- **THEN** the system navigates back to the Floors list, shows the updated details in the table, and triggers a success notification

### Requirement: Floor update failure keeps the admin on the page with entered values
The system SHALL, when updating a floor fails, trigger an error notification and SHALL keep the admin on the Edit Floor page with their entered values retained.

#### Scenario: Floor update fails
- **WHEN** an admin submits the Edit Floor page and the update fails
- **THEN** the system triggers an error notification and the admin remains on the page with the entered values retained

### Requirement: Deleting a floor requires confirmation
The system SHALL, when a row's "Delete" action is activated, show a confirmation dialog before deleting, and SHALL NOT delete the floor unless the admin confirms.

#### Scenario: Delete requested
- **WHEN** an admin activates a floor row's "Delete" action
- **THEN** the system shows a confirmation dialog and does not yet delete the floor

#### Scenario: Delete cancelled
- **WHEN** an admin dismisses the delete confirmation dialog without confirming
- **THEN** the floor remains in the table unchanged

### Requirement: Confirmed deletion removes the floor and notifies on failure
The system SHALL, when the admin confirms deletion, remove the floor from its building's data, remove it from the visible list, and trigger a success notification on success; on failure it SHALL trigger an error notification and leave the floor in the list.

#### Scenario: Delete confirmed and succeeds
- **WHEN** an admin confirms deletion of a floor and the deletion succeeds
- **THEN** the system removes that floor from the table and triggers a success notification

#### Scenario: Delete confirmed and fails
- **WHEN** an admin confirms deletion of a floor and the deletion fails
- **THEN** the system triggers an error notification and the floor remains in the table

### Requirement: Floor list can be filtered by building, access level, and status
The system SHALL, when "Filters" is activated, show a filter panel offering Building, Access Level, and Status fields (each defaulting to "All"), and SHALL narrow the visible floors to those matching every selected filter as soon as a filter changes, without a separate confirm step. The system SHALL let an admin clear all active filters back to "All" in one action.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the system shows the Building, Access Level, and Status filter fields

#### Scenario: Filter selected narrows the list
- **WHEN** an admin selects a specific Building, Access Level, or Status value
- **THEN** the table immediately shows only floors matching every currently selected filter

#### Scenario: Multiple filters combine
- **WHEN** an admin has selected values for more than one of Building, Access Level, and Status
- **THEN** the table shows only floors matching all of the selected filters at once

#### Scenario: Filters cleared
- **WHEN** an admin activates "Clear filters"
- **THEN** every filter resets to "All" and the table shows the full floor list again

### Requirement: No filter matches shows a distinct empty state
The system SHALL, when one or more filters are active and no floor matches them, show a message indicating no floors match the current filters, distinct from the message shown when the organisation has zero floors at all.

#### Scenario: No matches for active filters
- **WHEN** one or more filters are active and no floor matches them
- **THEN** the system shows a "no floors match these filters" message instead of the zero-floors empty state
