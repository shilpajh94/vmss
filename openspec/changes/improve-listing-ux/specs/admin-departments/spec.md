## MODIFIED Requirements

### Requirement: Department list can be filtered by branch and status
The system SHALL, when "Filters" is activated, show a filter panel offering Branch and Status fields (each defaulting to "All"), and SHALL, as soon as a filter changes, send the selected filters as query parameters on a fresh request to the departments list endpoint and render the returned page, without a separate confirm step. The system SHALL let an admin clear all active filters back to "All" in one action, which SHALL re-request the list with no filter parameters.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the system shows the Branch and Status filter fields

#### Scenario: Filter selected narrows the list
- **WHEN** an admin selects a Branch and/or Status value
- **THEN** the system requests the departments list with those values as query parameters and the table shows the returned page of matching departments

#### Scenario: Multiple filters combine
- **WHEN** an admin has selected values for both Branch and Status
- **THEN** the system requests the departments list with both values as query parameters and the table shows only departments matching both

#### Scenario: Filters cleared
- **WHEN** an admin activates "Clear filters"
- **THEN** the system re-requests the departments list with no filter parameters and the table shows the first page of the full department list again

## ADDED Requirements

### Requirement: Department list is paginated
The system SHALL request the departments list one page at a time using the API's `page`/`pageSize` query parameters, SHALL show pagination controls reflecting the response's `total` and `totalPages`, and SHALL re-request the appropriate page when the admin navigates to a different page or changes the page size. Changing an active filter SHALL reset the current page back to 1.

#### Scenario: Departments page loads its first page
- **WHEN** the Departments page loads with no page specified
- **THEN** the system requests page 1 and the pagination control shows the correct total and total page count

#### Scenario: Admin navigates to the next page
- **WHEN** an admin activates the "next page" control and a further page exists
- **THEN** the system requests the next page and replaces the table's rows with that page's departments

#### Scenario: Last page reached disables further forward navigation
- **WHEN** the currently displayed page is the last page reported by `totalPages`
- **THEN** the "next page" control is disabled

#### Scenario: Changing a filter resets to page 1
- **WHEN** an admin is viewing a page other than 1 and changes the Branch or Status filter
- **THEN** the system requests page 1 of the filtered result set, not the page the admin was previously on
