## ADDED Requirements

### Requirement: A Floor's Building Is Read-Only When Editing
On the edit-floor page the Building select SHALL be displayed but not
editable, because the API does not accept moving a floor to another
building. It stays editable when creating a floor.

#### Scenario: Editing an existing floor
- **WHEN** an admin opens an existing floor for editing
- **THEN** its building is shown read-only
