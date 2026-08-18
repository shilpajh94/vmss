# admin-buildings Specification

## Purpose

The admin-buildings capability is the Super Admin's Buildings Registry screen at `/admin/buildings`, plus its Add/Edit Building page: it lets an admin view, add, edit, and delete the organisation's buildings, each associated with a branch and composed of floors, each floor optionally holding its own security checkpoints.

## Requirements

### Requirement: Admin section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Buildings list or the Add/Edit Building page, and SHALL redirect to `/staff/login` instead of rendering when no token is present.

#### Scenario: No token present on the list
- **WHEN** a browser without a staff auth token navigates to `/admin/buildings`
- **THEN** the system redirects to `/staff/login` and does not render the page

#### Scenario: No token present on the form
- **WHEN** a browser without a staff auth token navigates to `/admin/buildings/new`
- **THEN** the system redirects to `/staff/login` and does not render the page

### Requirement: Admin sidebar and top bar render with "Buildings" active
The system SHALL render, for an authenticated session, the Admin sidebar with "Buildings" shown as the active item, and the Admin top bar showing "Organization Admin" with the Buildings-specific description and the signed-in staff member's name and role.

#### Scenario: Admin views the Buildings page
- **WHEN** an authenticated admin's Buildings page finishes loading
- **THEN** the sidebar shows "Buildings" marked active and the top bar shows the signed-in staff member's name and role

### Requirement: Building list loads on page entry
The system SHALL, when the Buildings page loads, fetch the current list of buildings and render one table row per building showing its name, branch, address, total floor count, reception desks, and status.

#### Scenario: Buildings load successfully
- **WHEN** the Buildings page loads and the fetch succeeds
- **THEN** the table shows one row per building with its name, branch, address, total floor count, reception desks, and status

### Requirement: Zero buildings shows the shared empty state
The system SHALL show the shared empty-state component in place of the table's rows when the building list loads successfully with zero buildings.

#### Scenario: No buildings exist
- **WHEN** the building list loads successfully with zero buildings
- **THEN** the system shows the shared empty-state component instead of any table rows

### Requirement: Building list load failure is reported without crashing
The system SHALL, when the building list fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the building list fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: Add Building navigates to a dedicated page
The system SHALL, when "Add Building" is activated from the Buildings list, navigate to a dedicated Add Building page.

#### Scenario: Add Building activated
- **WHEN** an admin activates "Add Building" on the Buildings list
- **THEN** the system navigates to the Add Building page

#### Scenario: Cancel on the Add Building page
- **WHEN** an admin activates "Cancel" on the Add Building page
- **THEN** the system navigates back to the Buildings list without creating a building

### Requirement: Adding a building requires a name and a branch
The system SHALL, on the Add Building page, request the building name, an associated branch (chosen from the organisation's existing branches), a street address, and an active/inactive status, and SHALL require the building name and branch to be non-empty before submission succeeds. Street address and status are optional (status defaults to active).

#### Scenario: Required field left empty
- **WHEN** an admin submits the Add Building page with the building name or branch left empty
- **THEN** the system shows a validation error and does not submit the building

### Requirement: Branch options come from the organisation's existing branches
The system SHALL populate the Branch field's options from the same branch data the Branches Register page lists.

#### Scenario: Branch options loaded
- **WHEN** the Add Building page loads
- **THEN** the Branch field offers every branch currently in the organisation's branch list

### Requirement: Floors can be added, renamed, and removed on the Add/Edit Building page
The system SHALL, on the Add/Edit Building page, let an admin add a floor (via a modal requesting a floor name, capacity, access level, associated departments, and status), edit an existing floor's details (via the same modal, pre-filled), and remove a floor after confirmation — all as in-progress edits to the form, not persisted independently of the building.

#### Scenario: Floor added
- **WHEN** an admin submits the Add Floor modal with a non-empty name
- **THEN** the system adds that floor, with its entered capacity, access level, associated departments, and status, to the form's floor list, without making a network request

#### Scenario: Floor renamed
- **WHEN** an admin submits the Edit Floor modal with a non-empty name
- **THEN** the system updates that floor's name and other entered details in the form's floor list, without making a network request

#### Scenario: Floor removal requires confirmation
- **WHEN** an admin activates a floor's "Delete" action
- **THEN** the system shows a confirmation dialog and does not remove the floor until the admin confirms

#### Scenario: Floor removed
- **WHEN** an admin confirms removing a floor
- **THEN** the system removes that floor and its checkpoints from the form's floor list, without making a network request

### Requirement: Each floor can be expanded to manage its security checkpoints
The system SHALL let an admin expand or collapse a floor card, and, while expanded, add a checkpoint (via a modal requesting a checkpoint name), rename an existing checkpoint, and remove a checkpoint after confirmation — all as in-progress edits to the form.

#### Scenario: Floor expanded
- **WHEN** an admin activates a collapsed floor card
- **THEN** the system expands it to show that floor's security checkpoints

#### Scenario: Checkpoint added
- **WHEN** an admin submits the Add Checkpoint modal with a non-empty name for an expanded floor
- **THEN** the system adds that checkpoint to the floor's checkpoint list, without making a network request

#### Scenario: Checkpoint removal requires confirmation
- **WHEN** an admin activates a checkpoint's "Delete" action
- **THEN** the system shows a confirmation dialog and does not remove the checkpoint until the admin confirms

### Requirement: Submitting a valid new building adds it to the list
The system SHALL, when the Add Building page is submitted with all required fields present, create the building — including its current floors and checkpoints — navigate back to the Buildings list, show the new building in the visible list, and trigger a success notification.

#### Scenario: Building created successfully
- **WHEN** an admin submits the Add Building page with all required fields present and the creation succeeds
- **THEN** the system navigates back to the Buildings list, shows the new building in the table, and triggers a success notification

### Requirement: Building creation failure keeps the admin on the page with entered values
The system SHALL, when creating a building fails, trigger an error notification and SHALL keep the admin on the Add Building page with their entered values — including floors and checkpoints — retained.

#### Scenario: Building creation fails
- **WHEN** an admin submits the Add Building page and the creation fails
- **THEN** the system triggers an error notification and the admin remains on the page with the entered values retained

### Requirement: Editing a building opens the same page pre-filled with its current details
The system SHALL, when a row's "Edit" action is activated, navigate to the Edit Building page pre-filled with that building's current name, branch, street address, status, floors, and each floor's checkpoints.

#### Scenario: Edit opened
- **WHEN** an admin activates a building row's "Edit" action
- **THEN** the system navigates to the Edit Building page pre-filled with that building's current details, floors, and checkpoints

### Requirement: Submitting a valid building edit updates the list
The system SHALL, when the Edit Building page is submitted with all required fields present, update the building, navigate back to the Buildings list, reflect the updated details in the table, and trigger a success notification.

#### Scenario: Building updated successfully
- **WHEN** an admin submits the Edit Building page with all required fields present and the update succeeds
- **THEN** the system navigates back to the Buildings list, shows the updated details in the table, and triggers a success notification

### Requirement: Building update failure keeps the admin on the page with entered values
The system SHALL, when updating a building fails, trigger an error notification and SHALL keep the admin on the Edit Building page with their entered values retained.

#### Scenario: Building update fails
- **WHEN** an admin submits the Edit Building page and the update fails
- **THEN** the system triggers an error notification and the admin remains on the page with the entered values retained

### Requirement: Deleting a building requires confirmation
The system SHALL, when a row's "Delete" action is activated, show a confirmation dialog before deleting, and SHALL NOT delete the building unless the admin confirms.

#### Scenario: Delete requested
- **WHEN** an admin activates a building row's "Delete" action
- **THEN** the system shows a confirmation dialog and does not yet delete the building

#### Scenario: Delete cancelled
- **WHEN** an admin dismisses the delete confirmation dialog without confirming
- **THEN** the building remains in the table unchanged

### Requirement: Confirmed deletion removes the building and notifies on failure
The system SHALL, when the admin confirms deletion, delete the building, remove it from the visible list, and trigger a success notification on success; on failure it SHALL trigger an error notification and leave the building in the list.

#### Scenario: Delete confirmed and succeeds
- **WHEN** an admin confirms deletion of a building and the deletion succeeds
- **THEN** the system removes that building from the table and triggers a success notification

#### Scenario: Delete confirmed and fails
- **WHEN** an admin confirms deletion of a building and the deletion fails
- **THEN** the system triggers an error notification and the building remains in the table

### Requirement: Filters affordance is presented but not yet functional
The system SHALL display the "Filters" control per the design, but SHALL NOT apply any filtering when it is activated.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the visible buildings do not change
