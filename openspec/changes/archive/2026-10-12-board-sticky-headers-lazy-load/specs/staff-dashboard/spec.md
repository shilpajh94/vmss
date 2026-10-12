## MODIFIED Requirements

### Requirement: Visit requests are grouped into four status columns with live counts
The system SHALL group visit requests into four columns — Requested, Approved, Checked-in, Denied — each showing a count badge equal to the total number of visit requests in that status that match the active search and filters, as reported by the server. The count SHALL NOT be limited to the number of cards currently loaded in the column.

#### Scenario: Requests load successfully
- **WHEN** the visit-requests list loads successfully
- **THEN** each request appears under the column matching its status, and each column's count badge shows the server's total for that status

#### Scenario: Count reflects the full total, not the loaded cards
- **WHEN** 250 visit requests are in the Requested status and only the first 20 have been loaded into the Requested column
- **THEN** the Requested column's count badge shows 250

### Requirement: Search filters visible requests by visitor, host, or REQ ID
The system SHALL, as the staff member types in the search field, show only visit requests whose visitor name or REQ ID contains the entered text (case-insensitive), across all columns. The search SHALL be applied by the server to every column's results, so matches beyond the cards already loaded are found, and each column's count badge SHALL reflect the searched total.

#### Scenario: Search narrows the board
- **WHEN** a staff member enters text in the search field
- **THEN** only visit requests whose visitor name or REQ ID contains that text are shown, in their existing columns, and each column's count shows how many matches exist in that status

#### Scenario: Search finds a request that was not loaded yet
- **WHEN** a staff member searches for the REQ ID of a request that is older than every card loaded in its column
- **THEN** that request appears in its column

#### Scenario: Search is cleared
- **WHEN** a staff member clears the search field
- **THEN** each column reloads from its first page with no search applied

### Requirement: Filters narrow the board by purpose of visit and registration type
The system SHALL provide a "Filters" control that lets a staff member select a Purpose of Visit and/or a Registration Type (Individual / Group). When one or both are selected, the system SHALL show only visit requests matching all selected criteria, combined with any active search text, across all columns. The filters SHALL be applied by the server to every column's results, and each column's count badge SHALL reflect the filtered total. Clearing a filter SHALL restore requests that only failed to match that criterion.

#### Scenario: Filtering by purpose of visit
- **WHEN** a staff member selects a Purpose of Visit filter value
- **THEN** only visit requests whose purpose of visit matches that value are shown, in their existing columns

#### Scenario: Filtering by registration type
- **WHEN** a staff member selects a Registration Type filter value
- **THEN** only visit requests whose registration type matches that value are shown, in their existing columns

#### Scenario: Combined with search
- **WHEN** a staff member has both a search term and a filter active
- **THEN** only visit requests matching both the search term and the active filter(s) are shown

#### Scenario: Changing a filter restarts every column from its first page
- **WHEN** a staff member has scrolled a column past its first page and then changes a filter
- **THEN** every column reloads from its first page with the new filter applied

#### Scenario: Filters cleared
- **WHEN** a staff member clears all active filters
- **THEN** all visit requests matching only the current search text (if any) are shown again

### Requirement: Refresh reloads the visit-requests list
The system SHALL present exactly one refresh control on the dashboard. When that control is activated, the system SHALL re-fetch, for every column, the pages that column has already loaded, and re-render the board with the latest data. A column the staff member has scrolled into SHALL keep its loaded depth and scroll position.

#### Scenario: Only one refresh control is shown
- **WHEN** the dashboard finishes loading
- **THEN** exactly one refresh control is visible on the page

#### Scenario: Staff refreshes the board
- **WHEN** a staff member activates the refresh control
- **THEN** the system re-fetches every column's loaded pages and updates the board with the result

#### Scenario: Refresh keeps a scrolled column's depth
- **WHEN** a staff member has loaded 60 cards into the Requested column, scrolled down, and activates the refresh control
- **THEN** the Requested column still holds up to 60 cards after the refresh and is not scrolled back to the top

### Requirement: Board refreshes automatically in the background
The system SHALL periodically re-fetch, on a fixed interval, the pages each column has already loaded, without requiring staff to activate the refresh control, and SHALL update the board with the result without showing the full-board loading state or resetting any column's scroll position. A request whose status changed SHALL move from its old column to its new one. The system SHALL NOT trigger an automatic refresh while a deny, reschedule, or delegate action is in progress or its dialog is open.

#### Scenario: Board updates without manual refresh
- **WHEN** the automatic refresh interval elapses while the dashboard is open
- **THEN** the system re-fetches each column's loaded pages and updates the board with the result, without showing the full-board loading state

#### Scenario: A request that changed status moves columns
- **WHEN** a request loaded in the Requested column is approved by someone else and the automatic refresh interval elapses
- **THEN** that request no longer appears in the Requested column, appears in the Approved column, and both columns' counts update

#### Scenario: Automatic refresh is suppressed during an in-progress action
- **WHEN** the automatic refresh interval elapses while a deny, reschedule, or delegate dialog is open
- **THEN** the system does not re-fetch the visit-requests list until that dialog is closed

## ADDED Requirements

### Requirement: Status column headers stay visible while cards scroll
The system SHALL keep each status column's header (label and count badge) visible at all times while the staff member scrolls through that column's cards, so the status of every card on screen is always identifiable. At `lg` and wider, each column's cards SHALL scroll within that column. The page header, search field, and filters SHALL also stay in place.

#### Scenario: Scrolling a long column on desktop
- **WHEN** a staff member scrolls down through 40 cards in the Requested column at 1280px wide
- **THEN** the "Requested" header and its count stay visible at the top of that column, and the other columns' headers stay visible too

#### Scenario: Columns scroll independently
- **WHEN** a staff member scrolls the Requested column down at 1280px wide
- **THEN** the Approved, Checked-in, and Denied columns keep their own scroll position

### Requirement: Columns load visit requests lazily in pages
The system SHALL load each status column's visit requests from the server in pages of 20, starting with the first page when the board opens. When the staff member scrolls near the end of a column's loaded cards and more exist on the server, the system SHALL load that column's next page and append it, without a full-board loading state and without reloading other columns. The system SHALL show a loading indicator at the end of the column while a page loads. When every request in the column is loaded, it SHALL NOT request further pages. A card SHALL NOT appear twice in the same column, even if new requests arrive between page loads.

#### Scenario: First page on open
- **WHEN** the dashboard opens and the Requested status has 250 visit requests
- **THEN** the Requested column shows the 20 most recent and its count badge shows 250

#### Scenario: Scrolling loads the next page
- **WHEN** a staff member scrolls to the end of the 20 cards loaded in the Requested column
- **THEN** a loading indicator appears at the end of that column, and the next 20 requests are appended beneath the existing cards

#### Scenario: Column fully loaded
- **WHEN** every visit request in a column has been loaded and the staff member scrolls to its end
- **THEN** no further page is requested for that column

#### Scenario: No duplicates when new requests arrive mid-scroll
- **WHEN** a new visit request is submitted after the first page of a column loaded and the staff member then scrolls to load the next page
- **THEN** no card appears twice in that column

#### Scenario: A page load fails
- **WHEN** loading a column's next page fails
- **THEN** the already-loaded cards stay visible, and the end of the column shows a retry control that loads that page again when activated
