## MODIFIED Requirements

### Requirement: Floors can be added, renamed, and removed on the Add/Edit Building page
The system SHALL, on the Add/Edit Building page, let an admin add a floor (via a modal requesting a floor name, capacity, access level, associated departments, and status), edit an existing floor's details (via the same modal, pre-filled), and remove a floor after confirmation — all as in-progress edits to the form, not persisted independently of the building.

#### Scenario: Floor added
- **WHEN** an admin submits the Add Floor modal with a non-empty name
- **THEN** the system adds that floor, with its entered capacity, access level, associated departments, and status, to the form's floor list, without making a network request

#### Scenario: Floor renamed
- **WHEN** an admin submits the Edit Floor modal with a non-empty name
- **THEN** the system updates that floor's name and other entered details in the form's floor list, without making a network request

#### Scenario: Floor removal requires confirmation
- **WHEN** an admin activates a floor's "Delete" action
- **THEN** the system shows a confirmation dialog and does not remove the floor until the admin confirms

#### Scenario: Floor removed
- **WHEN** an admin confirms removing a floor
- **THEN** the system removes that floor and its checkpoints from the form's floor list, without making a network request
