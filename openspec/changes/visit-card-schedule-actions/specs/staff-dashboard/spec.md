## REMOVED Requirements

### Requirement: An expanded card offers rescheduling for requests that are still submitted or approved
**Reason**: Superseded by the "A card offers a Reschedule button for requests that are still submitted or approved" requirement below — rescheduling moves from an inline form shown only on an expanded card to a dedicated button that opens a modal, independent of card expansion.
**Migration**: No user-facing migration; the reschedule capability itself is unchanged, only its trigger and presentation.

#### Scenario: Reschedule form only for eligible statuses
- **WHEN** a card for an invitation whose status is not `submitted` or `approved` is expanded
- **THEN** the system does not show a reschedule form on that card

#### Scenario: Save disabled until both fields are filled
- **WHEN** an expanded, reschedulable card's date or time field is empty
- **THEN** the save action is disabled

#### Scenario: Reschedule succeeds
- **WHEN** a staff member fills both fields and activates save
- **THEN** the system updates the invitation's preferred date/time, refreshes the board, and triggers a success notification

#### Scenario: Reschedule fails
- **WHEN** a reschedule save attempt fails
- **THEN** the system triggers an error notification containing the backend's error message

## ADDED Requirements

### Requirement: A card offers a Reschedule button for requests that are still submitted or approved
The system SHALL show a "Reschedule" button on any visit request card whose status is `submitted` or `approved`. Activating it SHALL open a modal dialog requiring both a new date and a new time before its save action is enabled. On save it SHALL update the invitation's preferred visit date/time, close the modal, refresh the board, and trigger a success notification; on failure it SHALL keep the modal open and trigger an error notification showing the backend's message.

#### Scenario: Reschedule button only for eligible statuses
- **WHEN** a visit request's status is not `submitted` or `approved`
- **THEN** its card does not show a Reschedule button

#### Scenario: Reschedule modal opens on activation
- **WHEN** a staff member activates the Reschedule button on an eligible card
- **THEN** the system opens a modal dialog with empty date and time fields, without expanding or collapsing the card's approval-step progress

#### Scenario: Save disabled until both fields are filled
- **WHEN** the reschedule modal's date or time field is empty
- **THEN** the save action is disabled

#### Scenario: Reschedule succeeds
- **WHEN** a staff member fills both fields in the reschedule modal and activates save
- **THEN** the system updates the invitation's preferred date/time, closes the modal, refreshes the board, and triggers a success notification

#### Scenario: Reschedule fails
- **WHEN** a reschedule save attempt fails
- **THEN** the system triggers an error notification containing the backend's error message and the modal remains open

### Requirement: A card offers a Delegate button for requests with a current approval step
The system SHALL show a "Delegate" button on any visit request card whose invitation has a current approval step. Activating it SHALL open a modal dialog offering a host picker scoped to the step's configured approver role (or all hosts, when the step is not role-scoped) and requiring a selection before its confirm action is enabled. On confirmation it SHALL reassign the current approval step to the selected host, close the modal, refresh the board, and trigger a success notification naming the delegate; on failure it SHALL keep the modal open and trigger an error notification showing the backend's message.

#### Scenario: Delegate button only when a step is pending
- **WHEN** a visit request's invitation has no current approval step
- **THEN** its card does not show a Delegate button

#### Scenario: Delegate modal opens on activation
- **WHEN** a staff member activates the Delegate button on an eligible card
- **THEN** the system opens a modal dialog with a host picker, without expanding or collapsing the card's approval-step progress

#### Scenario: Host picker scoped to the step's role
- **WHEN** the current approval step is assigned to a specific role
- **THEN** the delegate modal's host picker offers only hosts holding that role

#### Scenario: Confirm disabled until a host is selected
- **WHEN** no host is selected in the delegate modal
- **THEN** the confirm action is disabled

#### Scenario: Delegate succeeds
- **WHEN** a staff member selects a host in the delegate modal and activates confirm
- **THEN** the system reassigns the current approval step to that host, closes the modal, refreshes the board, and triggers a success notification naming the delegate

#### Scenario: Delegate fails
- **WHEN** a delegate confirmation attempt fails
- **THEN** the system triggers an error notification containing the backend's error message and the modal remains open

## MODIFIED Requirements

### Requirement: Visit request cards display identifying details
The system SHALL render, for each visit request, an avatar showing the visitor's initials, the REQ ID, the visitor's name, the assigned host's name, and the scheduled visit date and time (the request's current preferred visit date/time), distinct from the timestamp the request was submitted.

#### Scenario: Card renders request details
- **WHEN** a visit request is displayed on the board
- **THEN** its card shows the visitor's initials, REQ ID, name, host name, and the scheduled visit date/time

#### Scenario: Scheduled time updates after a reschedule
- **WHEN** a visit request's preferred visit date/time has been changed by a reschedule action
- **THEN** the card shows the updated scheduled visit date/time after the board next refreshes
