## ADDED Requirements

### Requirement: Category default zones are managed on the category page
The system SHALL show, on the Edit Category page, a default-zones section to users who hold `zones:view`, listing the zones currently set as the category's defaults and letting users who hold `zones:manage` save a new set that replaces the previous one. The section SHALL be hidden when the zone feature is off.

#### Scenario: Defaults load
- **WHEN** an authorised user opens Edit Category
- **THEN** the default-zones section shows the category's current default zones

#### Scenario: Save defaults
- **WHEN** a `zones:manage` user changes the selection and saves
- **THEN** the system sends the complete set, shows the saved set, and triggers a success notification

#### Scenario: Read-only viewer
- **WHEN** a user with `zones:view` but not `zones:manage` opens Edit Category
- **THEN** the section is shown read-only

#### Scenario: Save fails
- **WHEN** the save request fails
- **THEN** the system keeps the selection and shows the error

#### Scenario: Empty defaults warn
- **WHEN** the category has no default zones
- **THEN** the section warns that visits in this category without their own zones will be denied every zone

#### Scenario: New category
- **WHEN** the user is on the Add Category page, before the category exists
- **THEN** the default-zones section is not shown, and zones can be set after the category is saved
