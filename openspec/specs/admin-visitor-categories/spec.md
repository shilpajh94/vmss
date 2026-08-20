# admin-visitor-categories Specification

## Purpose

The admin-visitor-categories capability is the Super Admin's Visitor Categories Registry screen at `/admin/visitor-categories`, plus its Add/Edit Category page: it lets an admin view, add, edit, and delete the organisation's visitor classifications, each carrying a badge color and compliance policy details (NDA requirement, escort requirement, max visit duration).

## Requirements

### Requirement: Admin section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Visitor Categories list or the Add/Edit Category page, and SHALL redirect to `/staff/login` instead of rendering when no token is present.

#### Scenario: No token present on the list
- **WHEN** a browser without a staff auth token navigates to `/admin/visitor-categories`
- **THEN** the system redirects to `/staff/login` and does not render the page

#### Scenario: No token present on the form
- **WHEN** a browser without a staff auth token navigates to `/admin/visitor-categories/new`
- **THEN** the system redirects to `/staff/login` and does not render the page

### Requirement: Admin sidebar and top bar render with "Visitor Categories" active
The system SHALL render, for an authenticated session, the Admin sidebar with "Visitor Categories" shown as the active item, and the Admin top bar showing the Visitor-Categories-specific description and the signed-in staff member's name and role.

#### Scenario: Admin views the Visitor Categories page
- **WHEN** an authenticated admin's Visitor Categories page finishes loading
- **THEN** the sidebar shows "Visitor Categories" marked active and the top bar shows the signed-in staff member's name and role

### Requirement: Visitor category list loads on page entry
The system SHALL, when the Visitor Categories page loads, fetch the current list of visitor categories and render one table row per category showing its name, description, badge color, NDA requirement, escort requirement, and max duration.

#### Scenario: Visitor categories load successfully
- **WHEN** the Visitor Categories page loads and the fetch succeeds
- **THEN** the table shows one row per visitor category with its name, description, badge color, NDA requirement, escort requirement, and max duration

### Requirement: Zero visitor categories shows the shared empty state
The system SHALL show the shared empty-state component in place of the table's rows when the visitor category list loads successfully with zero categories.

#### Scenario: No visitor categories exist
- **WHEN** the visitor category list loads successfully with zero categories
- **THEN** the system shows the shared empty-state component instead of any table rows

### Requirement: Visitor category list load failure is reported without crashing
The system SHALL, when the visitor category list fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the visitor category list fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: Add Category navigates to a dedicated page
The system SHALL, when "Add Category" is activated from the Visitor Categories list, navigate to a dedicated Add Category page.

#### Scenario: Add Category activated
- **WHEN** an admin activates "Add Category" on the Visitor Categories list
- **THEN** the system navigates to the Add Category page

#### Scenario: Cancel on the Add Category page
- **WHEN** an admin activates "Cancel" on the Add Category page
- **THEN** the system navigates back to the Visitor Categories list without creating a category

### Requirement: Adding a visitor category requires a name
The system SHALL, on the Add Category page, request the category name, a description, a badge color (chosen from a fixed palette), an NDA requirement, an escort requirement, and a max duration. The system SHALL require the category name to be non-empty before submission succeeds. Description, NDA requirement, escort requirement, and max duration are optional, and badge color defaults to the first palette option.

#### Scenario: Required field left empty
- **WHEN** an admin submits the Add Category page with the category name left empty
- **THEN** the system shows a validation error and does not submit the category

### Requirement: Badge color is chosen from a fixed palette
The system SHALL offer badge color as a fixed set of named palette options (Blue, Orange, Gold, Grey) rather than a free-form color value, and SHALL render each category's chosen color as a colored swatch next to its name in the list.

#### Scenario: Badge color options loaded
- **WHEN** the Add Category page loads
- **THEN** the Badge Color field offers the fixed set of palette options

#### Scenario: Badge color renders as a swatch
- **WHEN** the Visitor Categories list loads successfully
- **THEN** each row shows its category's chosen badge color as a colored swatch with its palette name

### Requirement: Submitting a valid new visitor category adds it to the list
The system SHALL, when the Add Category page is submitted with the category name present, create the visitor category, navigate back to the Visitor Categories list, show the new category in the visible list, and trigger a success notification.

#### Scenario: Visitor category created successfully
- **WHEN** an admin submits the Add Category page with the category name present and the creation succeeds
- **THEN** the system navigates back to the Visitor Categories list, shows the new category in the table, and triggers a success notification

### Requirement: Visitor category creation failure keeps the admin on the page with entered values
The system SHALL, when creating a visitor category fails, trigger an error notification and SHALL keep the admin on the Add Category page with their entered values retained.

#### Scenario: Visitor category creation fails
- **WHEN** an admin submits the Add Category page and the creation fails
- **THEN** the system triggers an error notification and the admin remains on the page with the entered values retained

### Requirement: Editing a visitor category opens the same page pre-filled with its current details
The system SHALL, when a row's "Edit" action is activated, navigate to the Edit Category page pre-filled with that category's current name, description, badge color, NDA requirement, escort requirement, and max duration.

#### Scenario: Edit opened
- **WHEN** an admin activates a visitor category row's "Edit" action
- **THEN** the system navigates to the Edit Category page pre-filled with that category's current details

### Requirement: Submitting a valid visitor category edit updates the list
The system SHALL, when the Edit Category page is submitted with the category name present, update the visitor category, navigate back to the Visitor Categories list, reflect the updated details in the table, and trigger a success notification.

#### Scenario: Visitor category updated successfully
- **WHEN** an admin submits the Edit Category page with the category name present and the update succeeds
- **THEN** the system navigates back to the Visitor Categories list, shows the updated details in the table, and triggers a success notification

### Requirement: Visitor category update failure keeps the admin on the page with entered values
The system SHALL, when updating a visitor category fails, trigger an error notification and SHALL keep the admin on the Edit Category page with their entered values retained.

#### Scenario: Visitor category update fails
- **WHEN** an admin submits the Edit Category page and the update fails
- **THEN** the system triggers an error notification and the admin remains on the page with the entered values retained

### Requirement: Deleting a visitor category requires confirmation
The system SHALL, when a row's "Delete" action is activated, show a confirmation dialog before deleting, and SHALL NOT delete the visitor category unless the admin confirms.

#### Scenario: Delete requested
- **WHEN** an admin activates a visitor category row's "Delete" action
- **THEN** the system shows a confirmation dialog and does not yet delete the category

#### Scenario: Delete cancelled
- **WHEN** an admin dismisses the delete confirmation dialog without confirming
- **THEN** the visitor category remains in the table unchanged

### Requirement: Confirmed deletion removes the visitor category and notifies on failure
The system SHALL, when the admin confirms deletion, delete the visitor category, remove it from the visible list, and trigger a success notification on success; on failure it SHALL trigger an error notification and leave the category in the list.

#### Scenario: Delete confirmed and succeeds
- **WHEN** an admin confirms deletion of a visitor category and the deletion succeeds
- **THEN** the system removes that category from the table and triggers a success notification

#### Scenario: Delete confirmed and fails
- **WHEN** an admin confirms deletion of a visitor category and the deletion fails
- **THEN** the system triggers an error notification and the category remains in the table

### Requirement: Escort requirement highlights when always required
The system SHALL visually emphasize the Escort Required column when a category's stored escort requirement text indicates escort is always required, distinguishing it from other escort requirement values.

#### Scenario: Escort always required is emphasized
- **WHEN** the Visitor Categories list contains a category whose escort requirement text indicates escort is always required
- **THEN** that row's Escort Required cell renders with distinct emphasis from rows without that indication

### Requirement: Filters affordance is presented but not yet functional
The system SHALL display the "Filters" control per the design, but SHALL NOT apply any filtering when it is activated.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the visible visitor categories do not change
