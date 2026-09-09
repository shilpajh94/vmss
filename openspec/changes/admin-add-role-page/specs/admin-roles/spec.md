## ADDED Requirements

### Requirement: Admin section requires an authenticated session on the create-role page
The system SHALL check for a staff auth token before rendering the create-role page, and SHALL redirect to `/admin/login` instead of rendering when no token is present.

#### Scenario: No token present on the create-role page
- **WHEN** a browser without a staff auth token navigates to `/admin/roles/new`
- **THEN** the system redirects to `/admin/login` and does not render the page

### Requirement: An "Add Role" action opens the create-role page
The system SHALL show an "Add Role" action on the Roles list, and SHALL navigate to the create-role page when it is activated.

#### Scenario: Add Role activated
- **WHEN** an admin activates "Add Role" on the Roles list
- **THEN** the system navigates to the create-role page

### Requirement: The create-role page loads the permission catalog
The system SHALL, when the create-role page loads, fetch the current staff user and the complete permission catalog, then show a name field, a description field, and one checkbox per catalog permission (its code and description), all unchecked by default.

#### Scenario: Permission catalog loads successfully
- **WHEN** the create-role page loads and the fetch succeeds
- **THEN** the page shows an empty name field, an empty description field, and one unchecked checkbox per catalog permission

#### Scenario: Load failure is reported without crashing
- **WHEN** fetching the permission catalog fails
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: Submitting the create-role page requires a role name
The system SHALL require a non-empty role name before submitting, and SHALL show a validation message and not submit the request when the name is blank.

#### Scenario: Submit attempted with a blank name
- **WHEN** an admin activates "Create Role" with the name field empty or whitespace-only
- **THEN** the system shows a validation message and does not call the backend

### Requirement: Submitting the create-role page creates a new role
The system SHALL, when "Create Role" is activated with a non-empty name, request creation of a role with the entered name, the entered description (or none), and the set of currently checked catalog permission codes. On success it SHALL navigate back to the Roles list, trigger a success notification, and the new role SHALL appear as a Custom role in the Roles list. On failure it SHALL trigger an error notification showing the backend's message and keep the admin on the page with their entered values intact.

#### Scenario: Create succeeds
- **WHEN** an admin enters a name, optionally a description, checks some permissions, and activates "Create Role", and the creation succeeds
- **THEN** the system navigates back to the Roles list, triggers a success notification, and the new role appears in the list marked Custom

#### Scenario: Create fails
- **WHEN** an admin activates "Create Role" and the creation request fails
- **THEN** the system triggers an error notification containing the backend's error message, the admin remains on the create-role page, and the entered name, description, and permission selections are unchanged

### Requirement: Cancel discards the draft role and returns to the Roles list
The system SHALL, when "Cancel" is activated on the create-role page, navigate back to the Roles list without creating a role.

#### Scenario: Cancel activated
- **WHEN** an admin fills in some fields on the create-role page and then activates "Cancel"
- **THEN** the system navigates back to the Roles list and no new role is created
