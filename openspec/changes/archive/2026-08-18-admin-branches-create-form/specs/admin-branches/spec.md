## ADDED Requirements

### Requirement: Add Branch navigates to a dedicated create page
The system SHALL, when "Add Branch" is activated from the Branches list, navigate to a dedicated create-branch page instead of opening a modal.

#### Scenario: Add Branch activated
- **WHEN** an admin activates "Add Branch" on the Branches list
- **THEN** the system navigates to the create-branch page

#### Scenario: Cancel on the create page
- **WHEN** an admin activates "Cancel" on the create-branch page
- **THEN** the system navigates back to the Branches list without creating a branch

### Requirement: Creating or editing a branch requires the full identity, geography, and operations field set
The system SHALL, on both the create-branch page and the edit-branch form, request branch name, branch code, location/city, country, physical address, contact person, contact email, contact phone, operating hours (from/to), operational status, and internal notes, and SHALL require branch name, branch code, location/city, country, physical address, contact person, contact email, and contact phone to be non-empty before submission succeeds. Operating hours, operational status, and internal notes are optional.

#### Scenario: Required field left empty on create
- **WHEN** an admin submits the create-branch page with branch name, branch code, location/city, country, physical address, contact person, contact email, or contact phone left empty
- **THEN** the system shows a validation error and does not submit the branch

#### Scenario: Required field left empty on edit
- **WHEN** an admin submits the edit-branch form with branch name, branch code, location/city, country, physical address, contact person, contact email, or contact phone left empty
- **THEN** the system shows a validation error and does not submit the branch

## MODIFIED Requirements

### Requirement: Submitting a valid new branch adds it to the list
The system SHALL, when the create-branch page is submitted with all required fields present, create the branch, navigate back to the Branches list, show the new branch in the visible list, and trigger a success notification.

#### Scenario: Branch created successfully
- **WHEN** an admin submits the create-branch page with all required fields present and the creation succeeds
- **THEN** the system navigates back to the Branches list, shows the new branch in the table, and triggers a success notification

### Requirement: Branch creation failure keeps the form open with entered values
The system SHALL, when creating a branch fails, trigger an error notification and SHALL keep the admin on the create-branch page with their entered values retained.

#### Scenario: Branch creation fails
- **WHEN** an admin submits the create-branch page and the creation fails
- **THEN** the system triggers an error notification and the admin remains on the create-branch page with the entered values retained

### Requirement: Editing a branch opens the form pre-filled with its current details
The system SHALL, when a row's "Edit" action is activated, open a modal form pre-filled with that branch's current branch name, branch code, location/city, country, physical address, contact person, contact email, contact phone, operating hours, operational status, and internal notes.

#### Scenario: Edit opened
- **WHEN** an admin activates a branch row's "Edit" action
- **THEN** the system opens the edit modal pre-filled with that branch's current details across every field

## REMOVED Requirements

### Requirement: Adding a branch requires name, location/city, branch code, and contact person
**Reason**: Superseded by the dedicated create-branch page and its expanded, required field set.
**Migration**: See "Add Branch navigates to a dedicated create page" and "Creating or editing a branch requires the full identity, geography, and operations field set".
