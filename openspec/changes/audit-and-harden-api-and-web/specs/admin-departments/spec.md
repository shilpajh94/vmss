## ADDED Requirements

### Requirement: A Department's Branch Is Read-Only When Editing
On the edit-department page the Branch select SHALL be displayed but not
editable, because the API does not accept moving a department to another
branch. It stays editable when creating a department.

#### Scenario: Editing an existing department
- **WHEN** an admin opens an existing department for editing
- **THEN** its branch is shown read-only
