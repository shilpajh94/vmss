## ADDED Requirements

### Requirement: Checked-in cards offer a confirmed manual check-out to Admin and Reception
The system SHALL show a "Check Out" action on every card in the Checked-in column when the signed-in staff member holds the Admin or Reception role. It SHALL NOT show this action to staff who hold neither role, and it SHALL NOT show it on cards in any other column. Activating the action SHALL open a confirmation dialog that names the visitor and the tracking ID. The visit SHALL be checked out only after the staff member confirms. On confirmation the system SHALL send one check-out request for that visit, carrying a single idempotency key for that confirmation.

#### Scenario: Reception sees Check Out on a checked-in card
- **WHEN** a staff member with the Reception role views a card in the Checked-in column
- **THEN** the card shows both "Visitor Info" and "Check Out" actions

#### Scenario: Host does not see Check Out
- **WHEN** a staff member with only the Host role views a card in the Checked-in column
- **THEN** the card shows "Visitor Info" and no "Check Out" action

#### Scenario: Check Out is limited to the Checked-in column
- **WHEN** a Reception or Admin staff member views cards in the Requested, Approved, Checked-out, or Denied columns
- **THEN** none of those cards shows a "Check Out" action

#### Scenario: Cancelling the confirmation changes nothing
- **WHEN** a staff member activates "Check Out" on a checked-in card and then cancels the confirmation dialog
- **THEN** the dialog closes, no check-out request is sent, and the card stays in the Checked-in column

#### Scenario: Confirming checks the visitor out
- **WHEN** a staff member confirms the check-out of a checked-in visitor and the server accepts it
- **THEN** the dialog closes, a success notification names the visitor as checked out, and after the board reloads the card appears in the Checked-out column with the Checked-in and Checked-out counts updated

#### Scenario: Confirm cannot be submitted twice
- **WHEN** a staff member confirms a check-out and the request is still in flight
- **THEN** the confirm button is disabled and reads "Checking out…", and activating it again sends no second request

#### Scenario: The visitor already left by QR scan
- **WHEN** a staff member confirms a check-out but the server reports the visit is no longer checked in
- **THEN** an error notification shows the server's message, the dialog closes, and the board reloads so the card shows its current column

#### Scenario: The server rejects the check-out
- **WHEN** a staff member confirms a check-out and the server rejects it for any other reason (for example, missing permission or a network failure)
- **THEN** an error notification shows the failure message, and the card stays in the Checked-in column

#### Scenario: Background refresh does not interrupt a check-out
- **WHEN** the check-out confirmation dialog is open or its request is in flight and the background refresh interval elapses
- **THEN** the board skips that refresh, so the dialog and card are not disrupted
