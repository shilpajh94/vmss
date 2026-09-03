## MODIFIED Requirements

### Requirement: Editing a building opens the same page pre-filled with its current details
The system SHALL, when a row's "Edit" action is activated, navigate to the Edit Building page, fetch that building's current details, and pre-fill the page with its name, branch, code, street address, status, floors, and each floor's checkpoints.

#### Scenario: Edit opened
- **WHEN** an admin activates a building row's "Edit" action
- **THEN** the system navigates to the Edit Building page pre-filled with that building's current name, branch, code, street address, status, floors, and checkpoints

#### Scenario: Building details cannot be found
- **WHEN** the Edit Building page loads for a building id that cannot be found
- **THEN** the system shows an error message on the page instead of rendering a blank or default-valued form
