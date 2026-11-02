## ADDED Requirements

### Requirement: Branch Code Is Read-Only When Editing
On the branch edit form the Branch Code SHALL be displayed but not
editable, because the API does not accept a code change on update. The form
SHALL NOT report a change as saved that was never sent.

#### Scenario: Editing an existing branch
- **WHEN** an admin opens an existing branch for editing
- **THEN** the Branch Code is shown read-only, and every other editable
  field saves as before
