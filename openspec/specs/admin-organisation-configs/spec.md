# admin-organisation-configs Specification

## Purpose

The admin-organisation-configs capability is the Super Admin's Organisation Configs screen at `/admin/organisation-configs`: it renders the Admin section shell (sidebar and top bar) and lets an admin view and edit the organisation's name, logo, default timezone, and visitor policy/security defaults.

## Requirements

### Requirement: Admin section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Organisation Configs page, and SHALL redirect to `/staff/login` instead of rendering the page when no token is present.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token navigates to `/admin/organisation-configs`
- **THEN** the system redirects to `/staff/login` and does not render the page

#### Scenario: Token present
- **WHEN** a browser with a staff auth token navigates to `/admin/organisation-configs`
- **THEN** the system renders the Organisation Configs page

### Requirement: Admin sidebar renders all admin navigation sections with "Organisation Configs" active
The system SHALL render, for an authenticated session, a sidebar with the brand mark and navigation items — Dashboard, Organisation Configs, Branches, Departments, Buildings, Floors, Reception Desks, Security Gates, Employees, Visitor Categories — with "Organisation Configs" shown as the active item.

#### Scenario: Admin views the Organisation Configs page
- **WHEN** an authenticated admin's Organisation Configs page finishes loading
- **THEN** the sidebar shows all ten navigation items with "Organisation Configs" marked active

### Requirement: Only "Organisation Configs" sidebar navigation is functional
The system SHALL render the other nine sidebar navigation items (Dashboard, Branches, Departments, Buildings, Floors, Reception Desks, Security Gates, Employees, Visitor Categories) per the design, but SHALL NOT navigate anywhere when any of them is activated.

#### Scenario: Inert nav item activated
- **WHEN** an admin activates a sidebar navigation item other than "Organisation Configs"
- **THEN** the current view does not change

### Requirement: Top bar shows the section title and the signed-in admin
The system SHALL display, in the top bar, the title "Organization Admin" with its supporting description, and the signed-in staff member's name and role retrieved from the current-staff-user API.

#### Scenario: Current user loads successfully
- **WHEN** the Organisation Configs page loads and the current-staff-user request succeeds
- **THEN** the top bar displays that staff member's name and role

### Requirement: Top bar notification affordance is presented but not yet functional
The system SHALL render the notification indicator in the top bar per the design, but SHALL NOT show notifications when it is activated. The top bar SHALL NOT render a workspace search field.

#### Scenario: Notification indicator activated
- **WHEN** an admin activates the notification indicator
- **THEN** the visible page content does not change

#### Scenario: No workspace search field rendered
- **WHEN** the Organisation Configs page loads
- **THEN** the top bar does not show a workspace search field

### Requirement: Filters affordance is presented but not yet functional
The system SHALL display the "Filters" control per the design, but SHALL NOT apply any filtering when it is activated.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the page content does not change

### Requirement: Organisation configuration loads on page entry
The system SHALL, when the Organisation Configs page loads, fetch the current organisation configuration — organisation name, logo, default timezone, and auto-approve setting — and populate the form with the retrieved values.

#### Scenario: Configuration loads successfully
- **WHEN** the Organisation Configs page loads and the fetch succeeds
- **THEN** the General Information and Visitor Policy & Security fields are populated with the retrieved organisation configuration

### Requirement: Configuration load failure is reported without crashing
The system SHALL, when the organisation configuration fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the organisation configuration fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: General Information section captures organisation name and default timezone
The system SHALL let an admin edit the organisation name in a text field and choose the default timezone from a list of available timezones.

#### Scenario: Admin edits organisation name
- **WHEN** an admin changes the text in the "Organisation Name" field
- **THEN** the field reflects the newly entered text as unsaved

#### Scenario: Admin changes default timezone
- **WHEN** an admin selects a different value from the "Default Timezone" list
- **THEN** the field reflects the newly selected timezone as unsaved

### Requirement: Organisation logo can be uploaded with type and size validation
The system SHALL let an admin upload a PNG or JPG organisation logo up to 5MB, SHALL reject files of a different type or larger size with an inline error, and SHALL show the uploaded logo as a preview on success.

#### Scenario: Valid logo uploaded
- **WHEN** an admin uploads a PNG or JPG file of 5MB or less
- **THEN** the system uploads the file and shows it as the logo preview

#### Scenario: Invalid file type
- **WHEN** an admin uploads a file that is not PNG or JPG
- **THEN** the system shows an inline error and does not change the logo preview

#### Scenario: File too large
- **WHEN** an admin uploads a PNG or JPG file larger than 5MB
- **THEN** the system shows an inline error and does not change the logo preview

### Requirement: Visitor Policy & Security section captures auto-approve setting
The system SHALL let an admin toggle "Auto-approve pre-registered visitors" on or off. The system SHALL NOT display a pass badge expiry duration control in this section.

#### Scenario: Admin toggles auto-approve
- **WHEN** an admin activates the "Auto-approve pre-registered visitors" toggle
- **THEN** the toggle reflects the new on/off state as unsaved

#### Scenario: No badge expiry control shown
- **WHEN** the Organisation Configs page loads
- **THEN** the Visitor Policy & Security section does not show a "Pass Badge Expiry Duration" field

### Requirement: Cancel Changes discards unsaved edits
The system SHALL, when "Cancel Changes" is activated, revert every field to the organisation configuration last successfully loaded or saved, discarding any unsaved edits.

#### Scenario: Admin cancels unsaved edits
- **WHEN** an admin has unsaved edits and activates "Cancel Changes"
- **THEN** every field reverts to the last loaded or saved organisation configuration

### Requirement: Save Configs persists the edited configuration
The system SHALL, when "Save Configs" is activated, submit the current form values to persist the organisation configuration, and SHALL trigger a success notification when the save succeeds.

#### Scenario: Save succeeds
- **WHEN** an admin activates "Save Configs" and the update succeeds
- **THEN** the system persists the edited organisation name, logo, default timezone, and auto-approve setting, and triggers a success notification

### Requirement: Save failure is reported without discarding the admin's edits
The system SHALL, when saving the organisation configuration fails, trigger an error notification and SHALL leave the admin's edited field values in place.

#### Scenario: Save fails
- **WHEN** an admin activates "Save Configs" and the update fails
- **THEN** the system triggers an error notification and the form retains the admin's edited values
