## MODIFIED Requirements

### Requirement: Security gate list can be filtered by building, gate type, and security level
The system SHALL, when "Filters" is activated, show a filter panel offering Building, Gate Type, and Security Level fields (each defaulting to "All"), and SHALL, as soon as a filter changes, send the selected filters as query parameters on a fresh request to the security gates list endpoint and render the returned page, without a separate confirm step. The system SHALL let an admin clear all active filters back to "All" in one action, which SHALL re-request the list with no filter parameters.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the system shows the Building, Gate Type, and Security Level filter fields

#### Scenario: Filter selected narrows the list
- **WHEN** an admin selects a Building, Gate Type, and/or Security Level value
- **THEN** the system requests the security gates list with those values as query parameters and the table shows the returned page of matching security gates

#### Scenario: Multiple filters combine
- **WHEN** an admin has selected values for more than one of Building, Gate Type, and Security Level
- **THEN** the system requests the security gates list with all selected values as query parameters and the table shows only security gates matching all of them

#### Scenario: Filters cleared
- **WHEN** an admin activates "Clear filters"
- **THEN** the system re-requests the security gates list with no filter parameters and the table shows the first page of the full security gate list again

## ADDED Requirements

### Requirement: Security gate list is paginated
The system SHALL request the security gates list one page at a time using the API's `page`/`pageSize` query parameters, SHALL show pagination controls reflecting the response's `total` and `totalPages`, and SHALL re-request the appropriate page when the admin navigates to a different page or changes the page size. Changing an active filter SHALL reset the current page back to 1.

#### Scenario: Security gates page loads its first page
- **WHEN** the Security Gates page loads with no page specified
- **THEN** the system requests page 1 and the pagination control shows the correct total and total page count

#### Scenario: Admin navigates to the next page
- **WHEN** an admin activates the "next page" control and a further page exists
- **THEN** the system requests the next page and replaces the table's rows with that page's security gates

#### Scenario: Last page reached disables further forward navigation
- **WHEN** the currently displayed page is the last page reported by `totalPages`
- **THEN** the "next page" control is disabled

#### Scenario: Changing a filter resets to page 1
- **WHEN** an admin is viewing a page other than 1 and changes the Building, Gate Type, or Security Level filter
- **THEN** the system requests page 1 of the filtered result set, not the page the admin was previously on
