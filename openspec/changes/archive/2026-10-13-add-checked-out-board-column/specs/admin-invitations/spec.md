## RENAMED Requirements

- FROM: `### Requirement: Invitations are grouped into four status columns with live counts`
- TO: `### Requirement: Invitations are grouped into five status columns with live counts`

## MODIFIED Requirements

### Requirement: Invitations are grouped into five status columns with live counts
The system SHALL group invitations into five columns, in this order: Requested, Approved, Checked-in, Checked-out, Denied. Each column SHALL show a count badge equal to the server's total number of invitations in that status matching the active search and filters, using the same board component as the staff dashboard. The count SHALL NOT be limited to the number of cards currently loaded. When a status filter is selected, only that status's column SHALL load invitations; the other columns SHALL show zero. Every status the status filter offers, including Checked-out, SHALL have a matching column.

#### Scenario: Invitations load successfully
- **WHEN** the invitations list loads successfully
- **THEN** each invitation appears under the column matching its status, and each column's count badge shows the server's total for that status

#### Scenario: Checked-out invitations appear in their own column
- **WHEN** the invitations list loads and some invitations have the status `checked_out`
- **THEN** those invitations appear in the Checked-out column, which sits between Checked-in and Denied, and its count badge shows the server's total of checked-out invitations matching the active search and filters

#### Scenario: Empty column
- **WHEN** a status column has zero invitations
- **THEN** the system shows an empty-state message instead of any cards

#### Scenario: Status filter limits loading to one column
- **WHEN** an admin selects the "Approved" status filter
- **THEN** only the Approved column loads invitations, and the Requested, Checked-in, Checked-out, and Denied columns show a count of zero and their empty state

#### Scenario: Checked-out status filter loads the Checked-out column
- **WHEN** an admin selects the "Checked-out" status filter
- **THEN** only the Checked-out column loads invitations and shows the server's total, and the other four columns show a count of zero and their empty state
