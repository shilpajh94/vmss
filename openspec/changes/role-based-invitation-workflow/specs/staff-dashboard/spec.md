## MODIFIED Requirements

### Requirement: Visit request cards display identifying details
The system SHALL render, for each visit request, an avatar showing the visitor's initials, the REQ ID, the visitor's name, the scheduled date and time, and the assigned host's name when one has been assigned — showing an "Unassigned — Front Office" placeholder instead when no host has yet been delegated, rather than a blank or missing field.

#### Scenario: Card renders request details
- **WHEN** a visit request whose ownership step has already been delegated to a specific host is displayed on the board
- **THEN** its card shows the visitor's initials, REQ ID, name, that host's name, and scheduled date/time

#### Scenario: Card renders an unassigned placeholder before delegation
- **WHEN** a visit request whose ownership step has not yet been delegated to a specific person is displayed on the board
- **THEN** its card shows "Unassigned — Front Office" in place of a host name, rather than a blank field

### Requirement: An in-progress approval step shows its pending approver by name
The system SHALL, when an expanded card's invitation has a current approval step, show "Step X of Y" together with the name of who it is pending on: the role's name when the step is assigned to a role — including the invitation's `stepOrder` 0 ownership step, now always role-assigned to the front-office role until delegated — or that person's full name when it is assigned to a specific host user (after delegation).

#### Scenario: Step pending on a role
- **WHEN** an expanded card's current approval step is assigned to a role
- **THEN** the system shows that role's name as the pending approver

#### Scenario: Freshly submitted invitation shows the front-office role as pending approver
- **WHEN** an expanded card's invitation has just been submitted and its `stepOrder` 0 step has not yet been delegated
- **THEN** the system shows the front-office role's name (not a person) as the pending approver

#### Scenario: Step pending on a specific host
- **WHEN** an expanded card's current approval step is assigned to a specific user (the invitation's resolved host, via delegation)
- **THEN** the system shows that user's full name as the pending approver

## ADDED Requirements

### Requirement: A card offers an Edit button for requests that are still submitted or approved
The system SHALL show an "Edit" button on any visit request card whose status is `submitted` or `approved`. Activating it SHALL open a modal dialog pre-filled with the invitation's current purpose of visit, preferred visit date/time, expected duration, location/building/department to visit, and additional notes — all editable — alongside the visitor's own personal details (name, email, phone, ID proof, photo), the visitor category, and the assigned host, all shown read-only in the same modal (host reassignment stays the Delegate button's job, not this modal's). On save it SHALL update the edited fields, close the modal, refresh the board, and trigger a success notification; on failure it SHALL keep the modal open and trigger an error notification showing the backend's message.

#### Scenario: Edit button only for eligible statuses
- **WHEN** a visit request's status is not `submitted` or `approved`
- **THEN** its card does not show an Edit button

#### Scenario: Edit modal shows visitor details and host as read-only
- **WHEN** a staff member activates the Edit button on an eligible card
- **THEN** the modal shows the visitor's personal details, visitor category, and assigned host as read-only text, with no control to change any of them

#### Scenario: Edit modal allows changing visit-detail fields
- **WHEN** a staff member changes the purpose, date, time, duration, department, or notes fields in the Edit modal and activates save
- **THEN** the system updates those fields on the invitation, closes the modal, refreshes the board, and triggers a success notification

#### Scenario: Edit fails
- **WHEN** an edit save attempt fails
- **THEN** the system triggers an error notification containing the backend's error message and the modal remains open

### Requirement: The Delegate action's host picker is unfiltered for the invitation-ownership step
The system SHALL, when the Delegate action (see the `visit-card-schedule-actions`-introduced Delegate button and modal) targets an invitation's `stepOrder` 0 ownership step, offer every active host employee at the branch in its host picker — not filtered down to holders of the front-office role — since the real host is normally not a front-office employee. For any later, category-configured workflow step, the Delegate action's host picker SHALL remain filtered to holders of that step's configured role, unchanged.

#### Scenario: Ownership step's delegate picker shows every host, not just front-office staff
- **WHEN** a staff member activates Delegate on a card whose current pending step is the invitation's `stepOrder` 0 ownership step
- **THEN** the host picker offers every active host employee at the branch, regardless of whether they hold the front-office role

#### Scenario: Later workflow step's delegate picker stays role-filtered
- **WHEN** a staff member activates Delegate on a card whose current pending step is a later, category-configured role-identified step
- **THEN** the host picker offers only hosts holding that step's configured role, exactly as before this change
