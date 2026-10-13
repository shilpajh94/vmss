## MODIFIED Requirements

### Requirement: Invitations are grouped into four status columns with live counts
The system SHALL group invitations into four columns — Requested, Approved, Checked-in, Denied — each showing a count badge equal to the server's total number of invitations in that status matching the active search and filters, using the same board component as the staff dashboard. The count SHALL NOT be limited to the number of cards currently loaded. When a status filter is selected, only that status's column SHALL load invitations; the other columns SHALL show zero.

#### Scenario: Invitations load successfully
- **WHEN** the invitations list loads successfully
- **THEN** each invitation appears under the column matching its status, and each column's count badge shows the server's total for that status

#### Scenario: Empty column
- **WHEN** a status column has zero invitations
- **THEN** the system shows an empty-state message instead of any cards

#### Scenario: Status filter limits loading to one column
- **WHEN** an admin selects the "Approved" status filter
- **THEN** only the Approved column loads invitations, and the Requested, Checked-in, and Denied columns show a count of zero and their empty state

### Requirement: Refresh reloads the invitations list
The system SHALL, when the refresh action is activated, re-fetch every column's already-loaded pages, the role list, and the employee directory, and re-render the board with the latest data. A column the admin has scrolled into SHALL keep its loaded depth and scroll position.

#### Scenario: Admin refreshes the board
- **WHEN** an admin activates the refresh action
- **THEN** the system re-fetches the underlying data and updates the board with the result

#### Scenario: Refresh keeps a scrolled column's depth
- **WHEN** an admin has loaded 60 cards into a column and activates the refresh action
- **THEN** that column still holds up to 60 cards after the refresh and is not scrolled back to the top

## ADDED Requirements

### Requirement: Invitations board pins its column headers and loads columns lazily
The admin Invitations board SHALL keep each column's header visible while its cards scroll. It SHALL load each column in pages of 20 as the admin scrolls, without duplicates, and SHALL stop requesting pages once a column is fully loaded. This is the same behaviour the staff dashboard defines in "Status column headers stay visible while cards scroll" and "Columns load visit requests lazily in pages".

#### Scenario: Scrolling a long column
- **WHEN** an admin scrolls to the end of the 20 cards loaded in the Requested column at 1280px wide
- **THEN** the "Requested" header and count stay visible, a loading indicator appears at the end of the column, and the next 20 invitations are appended

#### Scenario: Search change restarts columns
- **WHEN** an admin has scrolled a column past its first page and then changes the search text
- **THEN** every column reloads from its first page with the new search applied
