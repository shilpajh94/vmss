## Purpose

The admin-security-gates capability is the Super Admin's Security Gates & Turnstiles Register screen at `/admin/security-gates`, plus its Register/Edit Gate page: it lets an admin view, add, edit, and delete the organisation's physical access-control gates and turnstiles, each associated with a building and, optionally, a floor.

## ADDED Requirements

### Requirement: Admin section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Security Gates list or the Register/Edit Gate page, and SHALL redirect to `/staff/login` instead of rendering when no token is present.

#### Scenario: No token present on the list
- **WHEN** a browser without a staff auth token navigates to `/admin/security-gates`
- **THEN** the system redirects to `/staff/login` and does not render the page

#### Scenario: No token present on the form
- **WHEN** a browser without a staff auth token navigates to `/admin/security-gates/new`
- **THEN** the system redirects to `/staff/login` and does not render the page

### Requirement: Admin sidebar and top bar render with "Security Gates" active
The system SHALL render, for an authenticated session, the Admin sidebar with "Security Gates" shown as the active item, and the Admin top bar showing the Security-Gates-specific description and the signed-in staff member's name and role.

#### Scenario: Admin views the Security Gates page
- **WHEN** an authenticated admin's Security Gates page finishes loading
- **THEN** the sidebar shows "Security Gates" marked active and the top bar shows the signed-in staff member's name and role

### Requirement: Security gate list loads on page entry
The system SHALL, when the Security Gates page loads, fetch the current list of security gates and render one table row per gate showing its name/ID, building, floor, gate type, auth method, and connectivity status.

#### Scenario: Security gates load successfully
- **WHEN** the Security Gates page loads and the fetch succeeds
- **THEN** the table shows one row per security gate with its name/ID, building, floor, gate type, auth method, and connectivity status

### Requirement: Zero security gates shows the shared empty state
The system SHALL show the shared empty-state component in place of the table's rows when the security gate list loads successfully with zero gates.

#### Scenario: No security gates exist
- **WHEN** the security gate list loads successfully with zero gates
- **THEN** the system shows the shared empty-state component instead of any table rows

### Requirement: Security gate list load failure is reported without crashing
The system SHALL, when the security gate list fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the security gate list fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: Register Gate navigates to a dedicated page
The system SHALL, when "Register Gate" is activated from the Security Gates list, navigate to a dedicated Register Gate page.

#### Scenario: Register Gate activated
- **WHEN** an admin activates "Register Gate" on the Security Gates list
- **THEN** the system navigates to the Register Gate page

#### Scenario: Cancel on the Register Gate page
- **WHEN** an admin activates "Cancel" on the Register Gate page
- **THEN** the system navigates back to the Security Gates list without creating a gate

### Requirement: Registering a security gate requires a name and a building
The system SHALL, on the Register Gate page, request the gate name/ID, an associated building (chosen from the organisation's existing buildings), a floor (chosen from the selected building's floors), a gate type (Bidirectional, Entry Only, Exit Only, or High Security), an auth method, and a connectivity status of Online, Maintenance, or Offline. The system SHALL require the gate name/ID and building to be non-empty before submission succeeds. Floor and auth method are optional; gate type defaults to Bidirectional and connectivity status defaults to Online.

#### Scenario: Required field left empty
- **WHEN** an admin submits the Register Gate page with the gate name/ID or building left empty
- **THEN** the system shows a validation error and does not submit the gate

### Requirement: Building options come from the organisation's existing buildings
The system SHALL populate the Building field's options from the same building data the Buildings Register page lists, so an admin can only associate a security gate with a building that actually exists.

#### Scenario: Building options loaded
- **WHEN** the Register Gate page loads
- **THEN** the Building field offers every building currently in the organisation's building list

### Requirement: Floor options are limited to the selected building's floors
The system SHALL populate the Floor field's options from the floors belonging to the currently selected building, and SHALL clear any previously selected floor when the admin changes the Building field to a different building.

#### Scenario: Building selected
- **WHEN** an admin selects a building on the Register Gate page
- **THEN** the Floor field offers only the floors belonging to that building

#### Scenario: Building changed after a floor was selected
- **WHEN** an admin changes the selected building after already choosing a floor
- **THEN** the previously selected floor is cleared and the Floor field offers the new building's floors

### Requirement: Submitting a valid new security gate adds it to the list
The system SHALL, when the Register Gate page is submitted with all required fields present, create the security gate, navigate back to the Security Gates list, show the new gate in the visible list, and trigger a success notification.

#### Scenario: Security gate created successfully
- **WHEN** an admin submits the Register Gate page with all required fields present and the creation succeeds
- **THEN** the system navigates back to the Security Gates list, shows the new gate in the table, and triggers a success notification

### Requirement: Security gate creation failure keeps the admin on the page with entered values
The system SHALL, when creating a security gate fails, trigger an error notification and SHALL keep the admin on the Register Gate page with their entered values retained.

#### Scenario: Security gate creation fails
- **WHEN** an admin submits the Register Gate page and the creation fails
- **THEN** the system triggers an error notification and the admin remains on the page with the entered values retained

### Requirement: Editing a security gate opens the same page pre-filled with its current details
The system SHALL, when a row's "Edit" action is activated, navigate to the Edit Gate page pre-filled with that gate's current name/ID, building, floor, gate type, auth method, and connectivity status.

#### Scenario: Edit opened
- **WHEN** an admin activates a security gate row's "Edit" action
- **THEN** the system navigates to the Edit Gate page pre-filled with that gate's current details

### Requirement: Submitting a valid security gate edit updates the list
The system SHALL, when the Edit Gate page is submitted with all required fields present, update the security gate, navigate back to the Security Gates list, reflect the updated details in the table, and trigger a success notification.

#### Scenario: Security gate updated successfully
- **WHEN** an admin submits the Edit Gate page with all required fields present and the update succeeds
- **THEN** the system navigates back to the Security Gates list, shows the updated details in the table, and triggers a success notification

### Requirement: Security gate update failure keeps the admin on the page with entered values
The system SHALL, when updating a security gate fails, trigger an error notification and SHALL keep the admin on the Edit Gate page with their entered values retained.

#### Scenario: Security gate update fails
- **WHEN** an admin submits the Edit Gate page and the update fails
- **THEN** the system triggers an error notification and the admin remains on the page with the entered values retained

### Requirement: Deleting a security gate requires confirmation
The system SHALL, when a row's "Delete" action is activated, show a confirmation dialog before deleting, and SHALL NOT delete the security gate unless the admin confirms.

#### Scenario: Delete requested
- **WHEN** an admin activates a security gate row's "Delete" action
- **THEN** the system shows a confirmation dialog and does not yet delete the gate

#### Scenario: Delete cancelled
- **WHEN** an admin dismisses the delete confirmation dialog without confirming
- **THEN** the security gate remains in the table unchanged

### Requirement: Confirmed deletion removes the security gate and notifies on failure
The system SHALL, when the admin confirms deletion, delete the security gate, remove it from the visible list, and trigger a success notification on success; on failure it SHALL trigger an error notification and leave the gate in the list.

#### Scenario: Delete confirmed and succeeds
- **WHEN** an admin confirms deletion of a security gate and the deletion succeeds
- **THEN** the system removes that gate from the table and triggers a success notification

#### Scenario: Delete confirmed and fails
- **WHEN** an admin confirms deletion of a security gate and the deletion fails
- **THEN** the system triggers an error notification and the gate remains in the table

### Requirement: Gate type is shown as one of four distinct states
The system SHALL render each security gate's gate type as one of "Bidirectional", "Entry Only", "Exit Only", or "High Security", each with a visually distinct badge, matching the gate's stored gate type.

#### Scenario: Gate types render distinctly
- **WHEN** the Security Gates list contains gates of each gate type
- **THEN** each row shows its own gate type as a badge visually distinct from the other gate types

### Requirement: Connectivity status is shown as one of three distinct states
The system SHALL render each security gate's connectivity status as one of "Online", "Maintenance", or "Offline", each with a visually distinct badge, matching the gate's stored connectivity status.

#### Scenario: Connectivity statuses render distinctly
- **WHEN** the Security Gates list contains gates with Online, Maintenance, and Offline connectivity
- **THEN** each row shows its own connectivity status as a badge visually distinct from the other two statuses

### Requirement: Filters affordance is presented but not yet functional
The system SHALL display the "Filters" control per the design, but SHALL NOT apply any filtering when it is activated.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the visible security gates do not change
