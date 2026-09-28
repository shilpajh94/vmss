## MODIFIED Requirements

### Requirement: Branch list can be filtered by status
The system SHALL, when "Filters" is activated, show a filter panel offering a Status field (Active/Inactive, defaulting to "All"), and SHALL, as soon as the selected status changes, send that status as a query parameter on a fresh request to the branches list endpoint and render the returned page, without a separate confirm step. The system SHALL let an admin clear the active filter back to "All", which SHALL re-request the list with no status parameter.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the system shows the Status filter field

#### Scenario: Filter selected narrows the list
- **WHEN** an admin selects a specific Status value
- **THEN** the system requests the branches list with that status as a query parameter and the table shows the returned page of matching branches

#### Scenario: Filters cleared
- **WHEN** an admin activates "Clear filters"
- **THEN** the system re-requests the branches list with no status parameter and the table shows the first page of the full branch list again

## ADDED Requirements

### Requirement: Branch list is paginated
The system SHALL request the branches list one page at a time using the API's `page`/`pageSize` query parameters, SHALL show pagination controls reflecting the response's `total` and `totalPages`, and SHALL re-request the appropriate page when the admin navigates to a different page or changes the page size. Changing an active status filter SHALL reset the current page back to 1.

#### Scenario: Branches page loads its first page
- **WHEN** the Branches page loads with no page specified
- **THEN** the system requests page 1 and the pagination control shows the correct total and total page count

#### Scenario: Admin navigates to the next page
- **WHEN** an admin activates the "next page" control and a further page exists
- **THEN** the system requests the next page and replaces the table's rows with that page's branches

#### Scenario: Last page reached disables further forward navigation
- **WHEN** the currently displayed page is the last page reported by `totalPages`
- **THEN** the "next page" control is disabled

#### Scenario: Changing the status filter resets to page 1
- **WHEN** an admin is viewing a page other than 1 and selects a new Status filter value
- **THEN** the system requests page 1 of the filtered result set, not the page the admin was previously on
