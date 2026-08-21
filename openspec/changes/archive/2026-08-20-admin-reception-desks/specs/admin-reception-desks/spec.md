## Purpose

The admin-reception-desks capability is the Super Admin's Reception Desks Register screen at `/admin/reception-desks`, plus its Add/Edit Reception Desk page: it lets an admin view, add, edit, and delete the organisation's on-site reception desks, each associated with a building and, optionally, a floor and an assigned receptionist.

## ADDED Requirements

### Requirement: Admin section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Reception Desks list or the Add/Edit Reception Desk page, and SHALL redirect to `/staff/login` instead of rendering when no token is present.

#### Scenario: No token present on the list
- **WHEN** a browser without a staff auth token navigates to `/admin/reception-desks`
- **THEN** the system redirects to `/staff/login` and does not render the page

#### Scenario: No token present on the form
- **WHEN** a browser without a staff auth token navigates to `/admin/reception-desks/new`
- **THEN** the system redirects to `/staff/login` and does not render the page

### Requirement: Admin sidebar and top bar render with "Reception Desks" active
The system SHALL render, for an authenticated session, the Admin sidebar with "Reception Desks" shown as the active item, and the Admin top bar showing the Reception-Desks-specific description and the signed-in staff member's name and role.

#### Scenario: Admin views the Reception Desks page
- **WHEN** an authenticated admin's Reception Desks page finishes loading
- **THEN** the sidebar shows "Reception Desks" marked active and the top bar shows the signed-in staff member's name and role

### Requirement: Reception desk list loads on page entry
The system SHALL, when the Reception Desks page loads, fetch the current list of reception desks and render one table row per desk showing its name, building, floor, assigned receptionist, operating hours, and status.

#### Scenario: Reception desks load successfully
- **WHEN** the Reception Desks page loads and the fetch succeeds
- **THEN** the table shows one row per reception desk with its name, building, floor, assigned receptionist, operating hours, and status

### Requirement: Zero reception desks shows the shared empty state
The system SHALL show the shared empty-state component in place of the table's rows when the reception desk list loads successfully with zero desks.

#### Scenario: No reception desks exist
- **WHEN** the reception desk list loads successfully with zero desks
- **THEN** the system shows the shared empty-state component instead of any table rows

### Requirement: Reception desk list load failure is reported without crashing
The system SHALL, when the reception desk list fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the reception desk list fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: Add Reception Desk navigates to a dedicated page
The system SHALL, when "Add Desk" is activated from the Reception Desks list, navigate to a dedicated Add Reception Desk page.

#### Scenario: Add Desk activated
- **WHEN** an admin activates "Add Desk" on the Reception Desks list
- **THEN** the system navigates to the Add Reception Desk page

#### Scenario: Cancel on the Add Reception Desk page
- **WHEN** an admin activates "Cancel" on the Add Reception Desk page
- **THEN** the system navigates back to the Reception Desks list without creating a desk

### Requirement: Adding a reception desk requires a name and a building
The system SHALL, on the Add Reception Desk page, request the desk name, an associated building (chosen from the organisation's existing buildings), a floor (chosen from the selected building's floors), an assigned receptionist, operating hours (from/to), and a status of Active, Maintenance, or Inactive. The system SHALL require the desk name and building to be non-empty before submission succeeds. Floor, assigned receptionist, and operating hours are optional, and status defaults to Active.

#### Scenario: Required field left empty
- **WHEN** an admin submits the Add Reception Desk page with the desk name or building left empty
- **THEN** the system shows a validation error and does not submit the desk

### Requirement: Building options come from the organisation's existing buildings
The system SHALL populate the Building field's options from the same building data the Buildings Register page lists, so an admin can only associate a reception desk with a building that actually exists.

#### Scenario: Building options loaded
- **WHEN** the Add Reception Desk page loads
- **THEN** the Building field offers every building currently in the organisation's building list

### Requirement: Floor options are limited to the selected building's floors
The system SHALL populate the Floor field's options from the floors belonging to the currently selected building, and SHALL clear any previously selected floor when the admin changes the Building field to a different building.

#### Scenario: Building selected
- **WHEN** an admin selects a building on the Add Reception Desk page
- **THEN** the Floor field offers only the floors belonging to that building

#### Scenario: Building changed after a floor was selected
- **WHEN** an admin changes the selected building after already choosing a floor
- **THEN** the previously selected floor is cleared and the Floor field offers the new building's floors

### Requirement: Assigned receptionist options come from the organisation's existing host employees
The system SHALL populate the Assigned Receptionist field's options from the organisation's existing host employees, and SHALL allow the field to be left unassigned.

#### Scenario: Receptionist options loaded
- **WHEN** the Add Reception Desk page loads
- **THEN** the Assigned Receptionist field offers every host employee currently in the organisation, plus an option to leave the desk unassigned

### Requirement: Submitting a valid new reception desk adds it to the list
The system SHALL, when the Add Reception Desk page is submitted with all required fields present, create the reception desk, navigate back to the Reception Desks list, show the new desk in the visible list, and trigger a success notification.

#### Scenario: Reception desk created successfully
- **WHEN** an admin submits the Add Reception Desk page with all required fields present and the creation succeeds
- **THEN** the system navigates back to the Reception Desks list, shows the new desk in the table, and triggers a success notification

### Requirement: Reception desk creation failure keeps the admin on the page with entered values
The system SHALL, when creating a reception desk fails, trigger an error notification and SHALL keep the admin on the Add Reception Desk page with their entered values retained.

#### Scenario: Reception desk creation fails
- **WHEN** an admin submits the Add Reception Desk page and the creation fails
- **THEN** the system triggers an error notification and the admin remains on the page with the entered values retained

### Requirement: Editing a reception desk opens the same page pre-filled with its current details
The system SHALL, when a row's "Edit" action is activated, navigate to the Edit Reception Desk page pre-filled with that desk's current name, building, floor, assigned receptionist, operating hours, and status.

#### Scenario: Edit opened
- **WHEN** an admin activates a reception desk row's "Edit" action
- **THEN** the system navigates to the Edit Reception Desk page pre-filled with that desk's current details

### Requirement: Submitting a valid reception desk edit updates the list
The system SHALL, when the Edit Reception Desk page is submitted with all required fields present, update the reception desk, navigate back to the Reception Desks list, reflect the updated details in the table, and trigger a success notification.

#### Scenario: Reception desk updated successfully
- **WHEN** an admin submits the Edit Reception Desk page with all required fields present and the update succeeds
- **THEN** the system navigates back to the Reception Desks list, shows the updated details in the table, and triggers a success notification

### Requirement: Reception desk update failure keeps the admin on the page with entered values
The system SHALL, when updating a reception desk fails, trigger an error notification and SHALL keep the admin on the Edit Reception Desk page with their entered values retained.

#### Scenario: Reception desk update fails
- **WHEN** an admin submits the Edit Reception Desk page and the update fails
- **THEN** the system triggers an error notification and the admin remains on the page with the entered values retained

### Requirement: Deleting a reception desk requires confirmation
The system SHALL, when a row's "Delete" action is activated, show a confirmation dialog before deleting, and SHALL NOT delete the reception desk unless the admin confirms.

#### Scenario: Delete requested
- **WHEN** an admin activates a reception desk row's "Delete" action
- **THEN** the system shows a confirmation dialog and does not yet delete the desk

#### Scenario: Delete cancelled
- **WHEN** an admin dismisses the delete confirmation dialog without confirming
- **THEN** the reception desk remains in the table unchanged

### Requirement: Confirmed deletion removes the reception desk and notifies on failure
The system SHALL, when the admin confirms deletion, delete the reception desk, remove it from the visible list, and trigger a success notification on success; on failure it SHALL trigger an error notification and leave the desk in the list.

#### Scenario: Delete confirmed and succeeds
- **WHEN** an admin confirms deletion of a reception desk and the deletion succeeds
- **THEN** the system removes that desk from the table and triggers a success notification

#### Scenario: Delete confirmed and fails
- **WHEN** an admin confirms deletion of a reception desk and the deletion fails
- **THEN** the system triggers an error notification and the desk remains in the table

### Requirement: Status is shown as one of three distinct states
The system SHALL render each reception desk's status as one of "Active", "Maintenance", or "Inactive", each with a visually distinct badge, matching the desk's stored status.

#### Scenario: Desk statuses render distinctly
- **WHEN** the Reception Desks list contains desks with Active, Maintenance, and Inactive status
- **THEN** each row shows its own status as a badge visually distinct from the other two statuses

### Requirement: Filters affordance is presented but not yet functional
The system SHALL display the "Filters" control per the design, but SHALL NOT apply any filtering when it is activated.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the visible reception desks do not change
