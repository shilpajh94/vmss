## Purpose

The admin-zones capability is the zone register at `/admin/zones`: it lets staff with the right permissions view, add, edit, and delete the site zones that visits are granted access to, and hides all zone UI when the backend's zone access feature is off.

## ADDED Requirements

### Requirement: Zone UI is hidden when the feature is off
The system SHALL treat a 404 response from the zone list fetch as "zone access is disabled" and SHALL hide every zone-related entry point (sidebar item, category default zones, visit zone picker, inside-by-zone view, zone timeline filters) instead of showing an error.

#### Scenario: Feature disabled on the backend
- **WHEN** the zone list fetch returns 404
- **THEN** the system shows no zone-related navigation or sections anywhere in the portal and shows no error notification

#### Scenario: Feature enabled
- **WHEN** the zone list fetch succeeds
- **THEN** the zone-related navigation and sections are available to users who hold the matching permissions

### Requirement: Zone register requires authentication and `zones:view`
The system SHALL redirect to `/staff/login` when no staff auth token is present, and SHALL show the Zones entry and page only to users who hold `zones:view`.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token navigates to `/admin/zones`
- **THEN** the system redirects to `/staff/login` and does not render the page

#### Scenario: User lacks `zones:view`
- **WHEN** a signed-in user without `zones:view` opens the portal
- **THEN** the sidebar shows no Zones entry and `/admin/zones` is not rendered for them

### Requirement: Zone list loads with filtering, sorting and pagination
The system SHALL fetch the zone list and show one row per zone with its name, code, branch, building, floor, linked gates, and active state. The list SHALL support filtering by active state, sorting by name or created date in either direction, and paging, and SHALL narrow to the selected branch when a branch is selected.

#### Scenario: Zones load successfully
- **WHEN** the Zones page loads and the fetch succeeds
- **THEN** the table shows one row per zone with its name, code, branch, building, floor, linked gates, and active state

#### Scenario: Filter by active state
- **WHEN** the user filters the list to inactive zones
- **THEN** the table shows only inactive zones

#### Scenario: Sort and page
- **WHEN** the user changes the sort field, sort direction, or page
- **THEN** the list reloads for that sort and page

#### Scenario: Zero zones
- **WHEN** the list loads successfully with zero zones
- **THEN** the system shows the shared empty-state component

#### Scenario: Load failure
- **WHEN** the zone list fails to load with an error other than 404
- **THEN** the system shows an error message, triggers an error notification, and allows retrying without reloading the page

### Requirement: Managing zones requires `zones:manage`
The system SHALL show the Add, Edit, and Delete actions only to users who hold `zones:manage`.

#### Scenario: Viewer without manage permission
- **WHEN** a user with `zones:view` but not `zones:manage` opens the Zones page
- **THEN** the page lists zones and shows no Add, Edit, or Delete action

### Requirement: Adding a zone
The system SHALL let a `zones:manage` user create a zone by providing a branch, a name, and a code (all required), and optionally a building, a floor, and linked gates. The building choice SHALL be limited to the chosen branch's buildings, the floor choice to the chosen building's floors, and the gate choice to gates in that building.

#### Scenario: Required field missing
- **WHEN** the user submits the Add Zone form with the branch, name, or code empty
- **THEN** the system shows a validation error and does not submit

#### Scenario: Zone created
- **WHEN** the user submits a valid Add Zone form
- **THEN** the system creates the zone, returns to the list showing it, and triggers a success notification

#### Scenario: Creation fails
- **WHEN** the create request fails
- **THEN** the system keeps the user on the form with the entered values and shows the error

### Requirement: Editing a zone
The system SHALL open the same form pre-filled with the zone's current details, SHALL show the branch as read-only, and SHALL save changes to name, code, building, floor, gates, and active state.

#### Scenario: Branch cannot be changed
- **WHEN** the user opens the Edit Zone form
- **THEN** the branch field is shown but cannot be changed

#### Scenario: Zone updated
- **WHEN** the user submits a valid edit
- **THEN** the system saves it, returns to the list showing the updated zone, and triggers a success notification

#### Scenario: Update fails
- **WHEN** the update request fails
- **THEN** the system keeps the user on the form with the entered values and shows the error

### Requirement: Deleting a zone requires confirmation
The system SHALL ask for confirmation before deleting a zone and SHALL remove it from the list only after the delete succeeds.

#### Scenario: Delete confirmed
- **WHEN** the user confirms deleting a zone
- **THEN** the system deletes it, removes it from the list, and triggers a success notification

#### Scenario: Delete cancelled
- **WHEN** the user cancels the confirmation
- **THEN** the zone is not deleted

#### Scenario: Delete fails
- **WHEN** the delete request fails
- **THEN** the zone stays in the list and the system shows an error notification

### Requirement: Zone list exposes gate links for the guard app
The system SHALL keep each zone's linked gates (`gateIds`) in the zone list data so that the guard app can resolve its gate and zone from `GET /zones`.

#### Scenario: Zone has linked gates
- **WHEN** the zone list is fetched
- **THEN** each zone carries the ids of its linked gates, and the Zones page shows them by name
