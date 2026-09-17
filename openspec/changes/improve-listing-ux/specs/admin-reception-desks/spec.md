## MODIFIED Requirements

### Requirement: Reception desk list can be filtered by building, floor, and status
The system SHALL, when "Filters" is activated, show a filter panel offering Building, Floor, and Status fields (each defaulting to "All"). A reception desk belongs to a Floor, not directly to a Building — the API has no building-level filter for this endpoint — so Building SHALL act as a client-side narrowing of the Floor field's own options only (selecting a Building narrows which floors the Floor field offers) and SHALL NOT itself be sent to the server. Floor and Status SHALL, as soon as either changes, be sent as query parameters on a fresh request to the reception desks list endpoint, and the returned page SHALL be rendered, without a separate confirm step. The system SHALL let an admin clear all active filters (including the Building narrowing) back to "All" in one action, which SHALL re-request the list with no filter parameters.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the system shows the Building, Floor, and Status filter fields

#### Scenario: Selecting a Building narrows the Floor options without a request
- **WHEN** an admin selects a Building value
- **THEN** the Floor field's options narrow to that building's floors, and no request is sent until a Floor and/or Status value is also selected

#### Scenario: Filter selected narrows the list
- **WHEN** an admin selects a Floor and/or Status value
- **THEN** the system requests the reception desks list with those values as query parameters and the table shows the returned page of matching reception desks

#### Scenario: Multiple filters combine
- **WHEN** an admin has selected both a Floor and a Status value
- **THEN** the system requests the reception desks list with both as query parameters and the table shows only reception desks matching both

#### Scenario: Filters cleared
- **WHEN** an admin activates "Clear filters"
- **THEN** the system re-requests the reception desks list with no filter parameters and the table shows the first page of the full reception desk list again

## ADDED Requirements

### Requirement: Reception desk list is paginated
The system SHALL request the reception desks list one page at a time using the API's `page`/`pageSize` query parameters, SHALL show pagination controls reflecting the response's `total` and `totalPages`, and SHALL re-request the appropriate page when the admin navigates to a different page. Changing the Floor or Status filter SHALL reset the current page back to 1; changing only the Building narrowing SHALL NOT, since it sends no request by itself.

#### Scenario: Reception desks page loads its first page
- **WHEN** the Reception Desks page loads with no page specified
- **THEN** the system requests page 1 and the pagination control shows the correct total and total page count

#### Scenario: Admin navigates to the next page
- **WHEN** an admin activates the "next page" control and a further page exists
- **THEN** the system requests the next page and replaces the table's rows with that page's reception desks

#### Scenario: Last page reached disables further forward navigation
- **WHEN** the currently displayed page is the last page reported by `totalPages`
- **THEN** the "next page" control is disabled

#### Scenario: Changing the Floor or Status filter resets to page 1
- **WHEN** an admin is viewing a page other than 1 and changes the Floor or Status filter
- **THEN** the system requests page 1 of the filtered result set, not the page the admin was previously on
