## REMOVED Requirements

### Requirement: Activating a card expands it and loads its approval-step progress
**Reason**: Cards no longer expand. The one thing expansion showed, the current approval step and who it is pending on, is already on every collapsed card as the "Level X/Y · Pending: …" badge, because detail for Requested and Approved cards is preloaded. Activating a card now opens its Visitor Info instead (see "Activating a card opens its Visitor Info").
**Migration**: No data migration. Staff who clicked a card to see approval progress read the badge instead; staff who used the Visitor Info button can click anywhere on the card.

### Requirement: A card offers a Reschedule button for requests that are still submitted or approved
**Reason**: Reschedule changes from a full-width labelled button into a compact icon button to reduce card height. The behaviour is otherwise unchanged (see "A card offers a Reschedule icon button for requests that are still submitted or approved").
**Migration**: Staff use the calendar icon on the card; the modal and its rules are identical.

### Requirement: A card offers a Delegate button for requests with a current approval step
**Reason**: Delegate changes from a full-width labelled button into a compact icon button to reduce card height. The behaviour is otherwise unchanged (see "A card offers a Delegate icon button for requests with a current approval step").
**Migration**: Staff use the delegate icon on the card; the modal and its rules are identical.

## ADDED Requirements

### Requirement: Activating a card opens its Visitor Info
The system SHALL open the Visitor Info modal for a visit request when a staff member activates the card's body by mouse click, tap, or keyboard (Enter or Space while the card has focus). Activating any button or icon button on the card SHALL perform only that control's action and SHALL NOT also open Visitor Info. When the dashboard loads with an `invitationId` query parameter naming a visit request, the system SHALL open that visit's Visitor Info modal once.

#### Scenario: Clicking a card opens Visitor Info
- **WHEN** a staff member clicks a card anywhere outside its buttons
- **THEN** the Visitor Info modal opens for that visit request

#### Scenario: Keyboard activation
- **WHEN** a card has keyboard focus and the staff member presses Enter or Space
- **THEN** the Visitor Info modal opens for that visit request

#### Scenario: Card buttons do not also open Visitor Info
- **WHEN** a staff member activates the Approve, Deny, or Check Out button, or any icon button, on a card
- **THEN** only that control's action runs, and the Visitor Info modal does not open

#### Scenario: Deep link opens Visitor Info
- **WHEN** the dashboard is opened with `?invitationId=<id>` (for example, from a clicked push notification)
- **THEN** the Visitor Info modal for that visit request opens once the page loads

### Requirement: Cards show only their deciding actions as buttons
The system SHALL render as card-face buttons only the actions that decide a request's next state. An actionable Requested card SHALL show "Approve" and "Deny" side by side in one row. When Reception's step is current, it SHALL show "Approve & Delegate" (if a further step follows) or "Approve" (if Reception is the only step), with "Deny" beside it. A Checked-in card SHALL show "Check Out" only to staff holding the Admin or Reception role. Approved, Checked-out, and Denied cards, and Requested cards that are not yet actionable, SHALL show no card-face buttons. Visitor Info, Reschedule, Edit, and Delegate SHALL NOT appear as labelled card-face buttons; they are icon buttons (see "Secondary card actions are icon buttons").

#### Scenario: Requested card actions
- **WHEN** a staff member views an actionable Requested card that is not on Reception's step
- **THEN** the card shows "Approve" and "Deny" buttons on one row and no other card-face buttons

#### Scenario: Reception step with a further step
- **WHEN** a Reception user views a Requested card whose current step is Reception's and whose workflow has more than one step
- **THEN** the card shows "Approve & Delegate" and "Deny" buttons on one row

#### Scenario: Approved card has no card-face buttons
- **WHEN** a staff member views a card in the Approved column
- **THEN** the card shows no labelled card-face buttons, only its icon row

### Requirement: Secondary card actions are icon buttons
The system SHALL show the secondary actions as a row of compact icon buttons along the bottom of each card, separate from the labelled card-face buttons. The row SHALL contain, in this order and only when eligible:
- "Visitor info" (always)
- "Reschedule" (status `submitted` or `approved`)
- "Edit" (status `submitted` or `approved`)
- "Delegate" (a current approval step exists that is not Reception's own step)

Each icon button SHALL have an accessible name of "<action> for <REQ ID>" and SHALL show the action's name as a tooltip on hover and keyboard focus. Activating one SHALL perform the same action as the button it replaces. Below `lg`, each icon button SHALL have a tap target of at least 40×40 CSS pixels.

#### Scenario: Requested card icons
- **WHEN** a staff member views a Requested card whose status is `submitted` and that has a current approval step not on Reception's step
- **THEN** the icon row shows Visitor info, Reschedule, Edit, and Delegate, in that order

#### Scenario: Approved card icons
- **WHEN** a staff member views an Approved card with no current approval step
- **THEN** the icon row shows Visitor info, Reschedule, and Edit, in that order

#### Scenario: Denied card icons
- **WHEN** a staff member views a Denied card
- **THEN** the icon row shows only Visitor info

#### Scenario: Icon names are discoverable
- **WHEN** a staff member hovers over or tabs to an icon button
- **THEN** a tooltip shows that action's name, and assistive technology announces "<action> for <REQ ID>"

### Requirement: A card offers a Reschedule icon button for requests that are still submitted or approved
The system SHALL show a "Reschedule" icon button on any visit request card whose status is `submitted` or `approved`. Activating it SHALL open a modal dialog requiring both a new date and a new time before its save action is enabled. On save it SHALL update the invitation's preferred visit date/time, close the modal, refresh the board, and trigger a success notification. On failure it SHALL keep the modal open and trigger an error notification showing the backend's message.

#### Scenario: Reschedule item only for eligible statuses
- **WHEN** a visit request's status is not `submitted` or `approved`
- **THEN** its card does not show a Reschedule icon button

#### Scenario: Reschedule modal opens from the icon
- **WHEN** a staff member activates the Reschedule icon button on an eligible card
- **THEN** the system opens a modal dialog with empty date and time fields

#### Scenario: Save disabled until both fields are filled
- **WHEN** the reschedule modal's date or time field is empty
- **THEN** the save action is disabled

#### Scenario: Reschedule succeeds
- **WHEN** a staff member fills both fields in the reschedule modal and activates save
- **THEN** the system updates the invitation's preferred date/time, closes the modal, refreshes the board, and triggers a success notification

#### Scenario: Reschedule fails
- **WHEN** a reschedule save attempt fails
- **THEN** the system triggers an error notification containing the backend's error message and the modal remains open

### Requirement: A card offers a Delegate icon button for requests with a current approval step
The system SHALL show a "Delegate" icon button on any visit request card whose invitation has a current approval step that is not Reception's own step. Activating it SHALL open a modal dialog. The modal SHALL offer a host picker scoped to the step's configured approver role, or all hosts when the step is not role-scoped, and SHALL require a selection before its confirm action is enabled. On confirmation it SHALL reassign the current approval step to the selected host, close the modal, refresh the board, and trigger a success notification naming the delegate. On failure it SHALL keep the modal open and trigger an error notification showing the backend's message.

#### Scenario: Delegate item only when a step is pending
- **WHEN** a visit request's invitation has no current approval step
- **THEN** its card does not show a Delegate icon button

#### Scenario: Delegate modal opens from the icon
- **WHEN** a staff member activates the Delegate icon button on an eligible card
- **THEN** the system opens a modal dialog with a host picker

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

### Requirement: The workspace header and search bar are compact
The system SHALL render the staff dashboard's "Visits" title and subtitle as a compact block, and the search field at the same 40px height as the purpose and registration-type filters. From `lg` up, the search field and both filters SHALL sit on one row, with the search field taking the remaining width. Below `lg` they SHALL wrap as they do today, with no horizontal overflow.

#### Scenario: Desktop filter row
- **WHEN** the staff dashboard is viewed at a desktop width (`lg` or wider)
- **THEN** the search field, purpose filter, and registration-type filter appear on a single row at equal height

#### Scenario: Narrow screen
- **WHEN** the staff dashboard is viewed at 360px wide
- **THEN** the search field and filters stack without horizontal page scroll

## MODIFIED Requirements

### Requirement: Visit request cards display identifying details
The system SHALL render, for each visit request, an avatar showing the visitor's initials, the REQ ID, the visitor's name, the assigned host's name, and the scheduled visit date and time. The scheduled time is the request's current preferred visit date/time, distinct from the timestamp the request was submitted. The visitor's name and REQ ID SHALL appear beside the avatar. Purpose of visit and host SHALL share a single line that truncates with an ellipsis rather than wrapping, with the full text available on hover. The scheduled date/time SHALL appear directly beneath that line, above any card-face buttons.

#### Scenario: Card renders request details
- **WHEN** a visit request is displayed on the board
- **THEN** its card shows the visitor's initials, REQ ID, name, host name, and the scheduled visit date/time

#### Scenario: Long host label does not wrap
- **WHEN** a card's purpose and host together are wider than the card
- **THEN** the purpose/host line stays on one line, ends in an ellipsis, and shows the full text on hover

#### Scenario: Scheduled time updates after a reschedule
- **WHEN** a visit request's preferred visit date/time has been changed by a reschedule action
- **THEN** the card shows the updated scheduled visit date/time after the board next refreshes

### Requirement: An in-progress approval step shows its pending approver by name
The system SHALL, when a card's invitation has a current approval step, show on the card a badge reading "Level X/Y" together with the name of who the step is pending on. That name is the role's name when the step is assigned to a role, or that person's full name when it is assigned to a specific host user. When the current step is stepOrder 0 (Reception) and the workflow has more than one total step, the system SHALL instead show the *next* step's (stepOrder 1) required role as the pending approver.

#### Scenario: Step pending on a role
- **WHEN** a card's current approval step is assigned to a role, and that step is not Reception's (stepOrder 0) step in a multi-step workflow
- **THEN** the card's badge shows that role's name as the pending approver

#### Scenario: Step pending on a specific host
- **WHEN** a card's current approval step is assigned to a specific user (the invitation's host)
- **THEN** the card's badge shows that user's full name as the pending approver

#### Scenario: Reception's step previews the next level instead of naming itself
- **WHEN** a card's current approval step is stepOrder 0 (Reception) and the workflow has more than one total step
- **THEN** the card's badge shows the next step's required role as the pending approver, instead of naming Reception's own step

#### Scenario: Single-step Reception-only workflow is unaffected
- **WHEN** a card's current approval step is stepOrder 0 (Reception) and the workflow has only one total step
- **THEN** the card's badge shows Reception's own step as the pending approver, unchanged

### Requirement: Checked-out cards are read-only
The system SHALL let a card in the Checked-out column open Visitor Info, by activating the card or its Visitor info icon button, and SHALL offer no other action on it. It SHALL NOT offer approve, deny, reschedule, delegate, or edit, and SHALL show no labelled card-face buttons. A Checked-out card SHALL NOT be draggable, and the Checked-out column SHALL NOT accept dropped cards. This applies equally to the admin Invitations board, which uses the same board component.

#### Scenario: Checked-out card actions
- **WHEN** a staff member views a card in the Checked-out column
- **THEN** the card shows no labelled card-face buttons, and its icon row shows only Visitor info

#### Scenario: Visitor Info on a checked-out card
- **WHEN** a staff member activates a Checked-out card or its Visitor info icon button
- **THEN** the Visitor Info modal opens for that visit and shows its status as "Checked Out"

#### Scenario: Cannot drop onto the Checked-out column
- **WHEN** a staff member drags a Requested card over the Checked-out column and releases it
- **THEN** the card stays in the Requested column and no status change is sent to the server
