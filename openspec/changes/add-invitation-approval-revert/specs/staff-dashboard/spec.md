## ADDED Requirements

### Requirement: Every invitation action is confirmed before its request is sent
The system SHALL NOT send any request that changes an invitation until the staff member has explicitly confirmed that action in a dialog. This applies to:
- Approve and approve-step
- Approve & Delegate and Delegate
- Deny and reject-step
- Revert approval
- Check Out
- Reschedule and Edit

Each confirmation SHALL name the action, the visitor, and the REQ ID. For form-based actions (Reschedule, Edit, Delegate, Approve & Delegate), submitting the form SHALL first show a confirmation step that summarizes what will change: the new date/time, the edited fields, or the selected employee. Cancelling that step SHALL return to the form with the staff member's input preserved. While a confirmed request is in flight, the dialog's confirm button SHALL be disabled and show a progress label, so repeated activation sends no second request. The board's background refresh SHALL be skipped while any confirmation dialog is open or any confirmed request is in flight.

#### Scenario: Cancelling a confirmation sends nothing
- **WHEN** a staff member starts any listed action and cancels its confirmation
- **THEN** no request is sent and the card stays where it was

#### Scenario: Form actions confirm a summary first
- **WHEN** a staff member fills the Reschedule form with a new date and time and submits it
- **THEN** a confirmation shows the visitor, REQ ID, and the new date and time, and no reschedule request is sent until the staff member confirms

#### Scenario: Backing out of a form confirmation keeps the input
- **WHEN** a staff member cancels the confirmation step of an Edit, Reschedule, Delegate, or Approve & Delegate form
- **THEN** the form is shown again with the values they had entered

#### Scenario: Double activation sends one request
- **WHEN** a staff member activates a confirm button twice in quick succession
- **THEN** exactly one request is sent and the button shows its progress label until it settles

#### Scenario: Background refresh waits for a confirmation
- **WHEN** any confirmation dialog is open, or its request is in flight, as the refresh interval elapses
- **THEN** the board skips that refresh

### Requirement: An Approved card offers a confirmed Revert approval action
The system SHALL show a "Revert approval" icon button on every card in the Approved column. Activating it SHALL open a dialog that:
- explains that the visit goes back to Requested and the visitor's pass stops working until it is approved again;
- names the visitor and REQ ID;
- requires a reason of 1–500 characters, with whitespace-only treated as empty.

The confirm action SHALL stay disabled until a reason is entered. On confirmation the system SHALL send one revert request for that invitation with the reason. On success it SHALL close the dialog, refresh the board (the card now appears in Requested, back at the first approval step for workflow-backed requests), and trigger a success notification naming the visitor. On failure it SHALL trigger an error notification with the server's message. For a 409, meaning the visit is no longer approved or the visitor has already checked in, it SHALL close the dialog and refresh the board so the card shows its current column. For any other failure it SHALL keep the dialog open with the reason preserved.

#### Scenario: Reverting a mistakenly approved visit
- **WHEN** a staff member activates "Revert approval" on an Approved card, enters a reason, and confirms, and the server accepts it
- **THEN** the dialog closes, a success notification is shown, and after the board reloads the card appears in the Requested column with the Approved and Requested counts updated

#### Scenario: Reason is required
- **WHEN** the revert dialog's reason field is empty or whitespace-only
- **THEN** the confirm action is disabled

#### Scenario: The visitor checked in meanwhile
- **WHEN** a staff member confirms a revert but the server rejects it with 409
- **THEN** an error notification shows the server's message, the dialog closes, and the board reloads so the card shows its current column

#### Scenario: Missing permission
- **WHEN** a staff member whose role lacks the revert permission confirms a revert and the server rejects it with 403
- **THEN** an error notification shows the server's message, the dialog stays open with the reason intact, and the card stays in Approved

#### Scenario: Revert is offered only on Approved cards
- **WHEN** a staff member views cards in the Requested, Checked-in, Checked-out, or Denied columns
- **THEN** none of them shows a "Revert approval" action

### Requirement: Visitor Info shows a reverted approval
The system SHALL, in the Visitor Info modal for an invitation whose status is `submitted` and whose `approvalRevertedAt` is set, show an "Approval reverted" note with the revert time, the reason, and the reverting user's name where it can be resolved (otherwise no name). It SHALL NOT show the note for invitations in any other status.

#### Scenario: Reverted request shows the note
- **WHEN** a staff member opens Visitor Info for a Requested invitation whose approval was reverted
- **THEN** the modal shows "Approval reverted" with the time and reason

#### Scenario: Re-approved request hides the note
- **WHEN** a reverted invitation has been approved again and its Visitor Info is opened
- **THEN** no "Approval reverted" note is shown

## MODIFIED Requirements

### Requirement: Dropping a requested card on Approved approves it, using the step endpoint when a workflow is active
The system SHALL, when a card is dropped on the Approved column or its card-face "Approve" button is activated, open an approval confirmation naming the visitor and REQ ID, and SHALL approve that invitation only after the staff member confirms: if it has a current approval step, approve that specific step; otherwise approve the invitation directly. Cancelling the confirmation SHALL send no request and leave the card in Requested. On success it SHALL close the confirmation, refresh the board and trigger a success notification; on failure it SHALL trigger an error notification showing the backend's message. A card whose current approval step is stepOrder 0 (Reception) in a workflow with more than one total step SHALL NOT be draggable to the Approved column at all — "Approve & Delegate" is the only way to advance it.

#### Scenario: Approving a non-workflow invitation
- **WHEN** a staff member approves a card for an invitation with no configured approval workflow and confirms
- **THEN** the system approves the invitation directly, refreshes the board, and triggers a success notification

#### Scenario: Approving a workflow-backed invitation's current step
- **WHEN** a staff member approves a card for an invitation with a current approval step, other than a Reception step with a further step following, and confirms
- **THEN** the system approves that specific step, refreshes the board, and triggers a success notification

#### Scenario: Approval is not sent without confirmation
- **WHEN** a staff member activates "Approve" on a Requested card on the staff dashboard
- **THEN** an approval confirmation opens and no approve request is sent until it is confirmed

#### Scenario: Approval rejected by the backend
- **WHEN** a confirmed approve attempt (direct or step-based) fails
- **THEN** the system triggers an error notification containing the backend's error message and the board is not otherwise changed

#### Scenario: A Reception-step, multi-step card cannot be drag-approved
- **WHEN** a card's current approval step is stepOrder 0 (Reception) and the workflow has more than one total step
- **THEN** the card cannot be dragged to the Approved column, and only "Approve & Delegate" is available to advance it

### Requirement: Secondary card actions are icon buttons
The system SHALL show the secondary actions as a row of compact icon buttons along the bottom of each card, separate from the labelled card-face buttons. The row SHALL contain, in this order and only when eligible:
- "Visitor info" (always)
- "Reschedule" (status `submitted` or `approved`)
- "Edit" (status `submitted` or `approved`)
- "Delegate" (a current approval step exists that is not Reception's own step)
- "Revert approval" (status `approved`)

Each icon button SHALL have an accessible name of "<action> for <REQ ID>" and SHALL show the action's name as a tooltip on hover and keyboard focus. Activating one SHALL perform the same action as the button it replaces. Below `lg`, each icon button SHALL have a tap target of at least 40×40 CSS pixels.

#### Scenario: Requested card icons
- **WHEN** a staff member views a Requested card whose status is `submitted` and that has a current approval step not on Reception's step
- **THEN** the icon row shows Visitor info, Reschedule, Edit, and Delegate, in that order

#### Scenario: Approved card icons
- **WHEN** a staff member views an Approved card with no current approval step
- **THEN** the icon row shows Visitor info, Reschedule, Edit, and Revert approval, in that order

#### Scenario: Denied card icons
- **WHEN** a staff member views a Denied card
- **THEN** the icon row shows only Visitor info

#### Scenario: Icon names are discoverable
- **WHEN** a staff member hovers over or tabs to an icon button
- **THEN** a tooltip shows that action's name, and assistive technology announces "<action> for <REQ ID>"
