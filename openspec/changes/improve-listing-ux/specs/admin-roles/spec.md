## ADDED Requirements

### Requirement: Role list is paginated
The system SHALL request the roles list one page at a time using the API's `page`/`pageSize` query parameters, SHALL show pagination controls reflecting the response's `total` and `totalPages`, and SHALL re-request the appropriate page when the admin navigates to a different page.

#### Scenario: Roles page loads its first page
- **WHEN** the Roles page loads with no page specified
- **THEN** the system requests page 1 and the pagination control shows the correct total and total page count

#### Scenario: Admin navigates to the next page
- **WHEN** an admin activates the "next page" control and a further page exists
- **THEN** the system requests the next page and replaces the list's rows with that page's roles

#### Scenario: Last page reached disables further forward navigation
- **WHEN** the currently displayed page is the last page reported by `totalPages`
- **THEN** the "next page" control is disabled
