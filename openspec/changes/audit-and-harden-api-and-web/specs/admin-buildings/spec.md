## ADDED Requirements

### Requirement: A Building's Branch Is Read-Only When Editing
On the edit-building page the Branch select SHALL be displayed but not
editable, because the API does not accept moving a building to another
branch. It stays editable when creating a building.

#### Scenario: Editing an existing building
- **WHEN** an admin opens an existing building for editing
- **THEN** its branch is shown read-only
