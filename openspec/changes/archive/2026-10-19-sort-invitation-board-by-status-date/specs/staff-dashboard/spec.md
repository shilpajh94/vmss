## MODIFIED Requirements

### Requirement: Columns load visit requests lazily in pages
The system SHALL load each status column's visit requests from the server in pages of 20, starting with the first page when the board opens. Each column SHALL be ordered newest first by when each request entered that column's status: submission (or approval revert, or reschedule out of Archived) for Requested, approval for Approved, latest check-in for Checked-in, latest check-out for Checked-out, denial for Denied, and archiving for Archived. The order SHALL NOT depend on the original submission time, and it SHALL stay the same across page loads, refreshes, and background polling. When the staff member scrolls near the end of a column's loaded cards and more exist on the server, the system SHALL load that column's next page and append it, without a full-board loading state and without reloading other columns. The system SHALL show a loading indicator at the end of the column while a page loads. When every request in the column is loaded, it SHALL NOT request further pages. A card SHALL NOT appear twice in the same column, even if new requests arrive between page loads.

#### Scenario: First page on open
- **WHEN** the dashboard opens and the Requested status has 250 visit requests
- **THEN** the Requested column shows the 20 most recently submitted and its count badge shows 250

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

#### Scenario: Checked-in column shows the latest check-in first
- **WHEN** visitor A, whose request was submitted three days ago, checked in five minutes ago, and visitor B, whose request was submitted yesterday, checked in two hours ago
- **THEN** A's card appears above B's card in the Checked-in column

#### Scenario: Approved column shows the latest approval first
- **WHEN** a request submitted last week is approved now, while another request submitted today was approved this morning
- **THEN** the request approved now appears at the top of the Approved column

#### Scenario: Closed tabs order by their own status time
- **WHEN** a staff member opens the Checked-out, Denied, or Archived tab of the Closed column
- **THEN** that tab lists requests newest first by check-out, denial, or archive time respectively

#### Scenario: Background refresh keeps the order
- **WHEN** the board refreshes in the background, or a staff member scrolls to load another page
- **THEN** the column keeps the same status-time order, with no card moving out of sequence
