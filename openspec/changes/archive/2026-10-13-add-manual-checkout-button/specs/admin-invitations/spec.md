## ADDED Requirements

### Requirement: Checked-in cards on the admin board offer the same manual check-out
The system SHALL offer, on every card in the admin Invitations board's Checked-in column, the same confirmed "Check Out" action specified for the staff-dashboard capability's board, with the same confirmation, success, conflict, and failure behaviour. Admins SHALL always see the action on Checked-in cards on this page.

#### Scenario: Admin checks out a visitor from the Invitations board
- **WHEN** an admin activates "Check Out" on a Checked-in card on the Invitations page and confirms
- **THEN** the visitor is checked out, a success notification is shown, and after the board reloads the card appears in the Checked-out column

#### Scenario: Check Out with the Checked-in status filter active
- **WHEN** the admin board's status filter is set to Checked-in and an admin checks a visitor out from that column
- **THEN** after the reload the card no longer appears in the Checked-in column, and the Checked-in count decreases by one
