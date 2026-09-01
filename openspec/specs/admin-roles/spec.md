# admin-roles Specification

## Purpose

The admin-roles capability is the Super Admin's Roles & Permissions screen at `/admin/roles`, plus its permission-edit page: it lets an admin see every role and what it can do, adjust a role's granted permissions against the full permission catalog, and backfill any permission a role is missing without manual backend intervention.

## Requirements

### Requirement: Admin section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Roles list or the permission-edit page, and SHALL redirect to `/admin/login` instead of rendering when no token is present.

#### Scenario: No token present on the list
- **WHEN** a browser without a staff auth token navigates to `/admin/roles`
- **THEN** the system redirects to `/admin/login` and does not render the page

#### Scenario: No token present on the edit page
- **WHEN** a browser without a staff auth token navigates to `/admin/roles/:id/edit`
- **THEN** the system redirects to `/admin/login` and does not render the page

### Requirement: Admin sidebar and top bar render with "Roles & Permissions" active
The system SHALL render, for an authenticated session, the Admin sidebar with "Roles & Permissions" shown as the active item, and the Admin top bar showing the signed-in staff member's name and role.

#### Scenario: Admin views the Roles page
- **WHEN** an authenticated admin's Roles page finishes loading
- **THEN** the sidebar shows "Roles & Permissions" marked active

### Requirement: Roles list loads on page entry
The system SHALL, when the Roles page loads, fetch the organisation's roles and show each one's name, description, granted-permission count, and whether it is a standard or custom role.

#### Scenario: Roles load successfully
- **WHEN** the Roles page loads and the fetch succeeds
- **THEN** the page lists every role with its name, description, permission count, and Standard/Custom badge

#### Scenario: No roles exist
- **WHEN** the role list loads successfully with zero roles
- **THEN** the system shows an empty-state message instead of the table

#### Scenario: Roles list load failure is reported without crashing
- **WHEN** the role list fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: Editing a role opens its permission-edit page
The system SHALL, when a role's edit action is activated, navigate to that role's permission-edit page.

#### Scenario: Edit activated
- **WHEN** an admin activates a role's edit action on the Roles list
- **THEN** the system navigates to that role's permission-edit page

### Requirement: The permission-edit page loads the role and the full permission catalog
The system SHALL, on the permission-edit page, fetch the target role and the complete permission catalog, then show one checkbox per catalog permission (its code and description), pre-checked for every permission the role currently has — even a permission the role has that is no longer present in the catalog is preserved, not silently dropped.

#### Scenario: Role and catalog load successfully
- **WHEN** the permission-edit page loads for a valid role id
- **THEN** the page shows the role's name and description, and one checkbox per catalog permission, checked according to the role's current `permissionCodes`

#### Scenario: Role id does not match any role
- **WHEN** the permission-edit page loads for an id that matches no role
- **THEN** the system shows an error message instead of the permission checklist

#### Scenario: Load failure is reported without crashing
- **WHEN** fetching the role list or the permission catalog fails
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: Saving the permission-edit page replaces the role's granted permissions
The system SHALL, when "Save Permissions" is activated, update the role's permission codes to exactly the set of currently checked catalog permissions (plus any pre-existing permission not in the catalog, left untouched), then navigate back to the Roles list and trigger a success notification. On failure it SHALL trigger an error notification showing the backend's message and keep the admin on the page.

#### Scenario: Save succeeds
- **WHEN** an admin toggles some checkboxes and activates "Save Permissions" and the update succeeds
- **THEN** the system navigates back to the Roles list and triggers a success notification

#### Scenario: Save fails
- **WHEN** an admin activates "Save Permissions" and the update fails
- **THEN** the system triggers an error notification containing the backend's error message and the admin remains on the page

### Requirement: Cancel discards changes and returns to the Roles list
The system SHALL, when "Cancel" is activated on the permission-edit page, navigate back to the Roles list without saving any change.

#### Scenario: Cancel activated
- **WHEN** an admin toggles some checkboxes and then activates "Cancel"
- **THEN** the system navigates back to the Roles list and the role's permissions are unchanged

### Requirement: Resync Permissions additively backfills missing catalog permissions
The system SHALL, when "Resync Permissions" is activated on the Roles list, request the backend to grant every standard role any catalog permission it is currently missing — never revoking a permission a role already has — then show, per role, which permission codes (if any) were newly granted, and refresh the roles list. On failure it SHALL trigger an error notification showing the backend's message.

#### Scenario: Resync grants missing permissions
- **WHEN** an admin activates "Resync Permissions" and one or more roles were missing catalog permissions
- **THEN** the system shows each affected role's name and the permission codes it was just granted, and triggers a success notification summarizing the total granted

#### Scenario: Resync finds nothing to grant
- **WHEN** an admin activates "Resync Permissions" and every role already has everything the catalog grants it
- **THEN** the system shows a message that every role is already up to date

#### Scenario: Resync fails
- **WHEN** a resync attempt fails
- **THEN** the system triggers an error notification containing the backend's error message
