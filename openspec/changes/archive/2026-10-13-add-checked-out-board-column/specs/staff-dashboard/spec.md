## RENAMED Requirements

- FROM: `### Requirement: Visit requests are grouped into four status columns with live counts`
- TO: `### Requirement: Visit requests are grouped into five status columns with live counts`

## MODIFIED Requirements

### Requirement: Visit requests are grouped into five status columns with live counts
The system SHALL group visit requests into five columns, in this order: Requested, Approved, Checked-in, Checked-out, Denied. Each column SHALL show a count badge equal to the total number of visit requests in that status that match the active search and filters, as reported by the server. The count SHALL NOT be limited to the number of cards currently loaded in the column.

#### Scenario: Requests load successfully
- **WHEN** the visit-requests list loads successfully
- **THEN** each request appears under the column matching its status, and each column's count badge shows the server's total for that status

#### Scenario: Count reflects the full total, not the loaded cards
- **WHEN** 250 visit requests are in the Requested status and only the first 20 have been loaded into the Requested column
- **THEN** the Requested column's count badge shows 250

#### Scenario: Checked-out visitors stay visible on the board
- **WHEN** a visitor on one of the staff member's visit requests checks out
- **THEN** after the next refresh or poll, that request appears in the Checked-out column instead of disappearing from the board, and the Checked-in and Checked-out counts reflect the move

## ADDED Requirements

### Requirement: Checked-out cards are read-only
The system SHALL show a card in the Checked-out column with Visitor Info as its only action. It SHALL NOT offer approve, deny, reschedule, delegate, or edit on it. A Checked-out card SHALL NOT be draggable, and the Checked-out column SHALL NOT accept dropped cards. This applies equally to the admin Invitations board, which uses the same board component.

#### Scenario: Checked-out card actions
- **WHEN** a staff member views a card in the Checked-out column
- **THEN** the card shows a "Visitor Info" action and no Approve, Deny, Reschedule, Delegate, or Edit action

#### Scenario: Visitor Info on a checked-out card
- **WHEN** a staff member activates "Visitor Info" on a Checked-out card
- **THEN** the Visitor Info modal opens for that visit and shows its status as "Checked Out"

#### Scenario: Cannot drop onto the Checked-out column
- **WHEN** a staff member drags a Requested card over the Checked-out column and releases it
- **THEN** the card stays in the Requested column and no status change is sent to the server

### Requirement: Checked-out column empty state
The system SHALL show the message "No checked-out visits" when the Checked-out column has no visit requests that match the active search and filters.

#### Scenario: No checked-out visits
- **WHEN** the Checked-out column has zero visit requests
- **THEN** it shows "No checked-out visits" instead of any cards
