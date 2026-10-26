## ADDED Requirements

### Requirement: Add Employee page offers an optional password
The system SHALL show a masked "Password" field on the Add Employee create page, with a control to reveal or hide the entered text. The field SHALL be optional. When a non-empty password is entered, the system SHALL require it to be at least 8 characters before submission succeeds. The Edit page SHALL NOT show a password field.

#### Scenario: Password left blank
- **WHEN** an admin submits the create page with all required fields present and the password empty
- **THEN** the employee is created without a password and no validation error is shown for the password

#### Scenario: Password too short
- **WHEN** an admin submits the create page with a password shorter than 8 characters
- **THEN** the system shows a validation error on the password field and does not submit the employee

#### Scenario: Valid password
- **WHEN** an admin submits the create page with all required fields present and a password of at least 8 characters
- **THEN** the system creates the employee with that password set

#### Scenario: Reveal and hide
- **WHEN** an admin activates the show/hide control on the password field
- **THEN** the entered text toggles between masked and visible

### Requirement: Password is set after the employee is created
The system SHALL, when a password was entered, set it for the new employee via the staff-user endpoint before the employee is added to the directory, SHALL NOT send any password for existing employees, and SHALL NOT retain the password after the page is left.

#### Scenario: Create with password
- **WHEN** an admin creates an employee with a password
- **THEN** the system sets that password and creates the employee so the employee can sign in with their email and it
