## MODIFIED Requirements

### Requirement: Search filters visible invitations by visitor name or tracking ID
The system SHALL, as the admin types in the search field, send the entered text (debounced) as a query parameter on the invitations list request and show only the invitations the server returns as matching by visitor name or tracking ID (case-insensitive), across all columns, rather than narrowing an already-fetched in-memory list.

#### Scenario: Search narrows the board
- **WHEN** an admin enters text in the search field
- **THEN** the system requests the invitations list with that text as a query parameter and only the returned invitations remain visible, in their existing columns

## ADDED Requirements

### Requirement: Invitations board can be filtered by status, registration type, and source
The system SHALL, when "Filters" is activated, show a filter panel offering Status, Registration Type, and Source fields (each defaulting to "All"), and SHALL, as soon as a filter changes, send the selected filters as query parameters on a fresh request to the invitations list endpoint and re-render the board's columns from the returned result, without a separate confirm step. The system SHALL let an admin clear all active filters back to "All" in one action.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the system shows the Status, Registration Type, and Source filter fields

#### Scenario: Filter selected narrows the board
- **WHEN** an admin selects a Status, Registration Type, and/or Source value
- **THEN** the system requests the invitations list with those values as query parameters and the board's columns reflect only the returned invitations

#### Scenario: Filters cleared
- **WHEN** an admin activates "Clear filters"
- **THEN** the system re-requests the invitations list with no filter parameters and the board shows the full, unfiltered set again

### Requirement: The board's fetch is bounded but not paginated
The system SHALL fetch the invitations board's data as a single bounded request (a `pageSize` large enough to cover realistic per-tenant invitation volume) rather than exposing page-forward/page-back controls, since each of the board's four status columns needs its full, accurate membership and count to render correctly — a paged fetch could under-populate a column until an admin paged further.

#### Scenario: Board load requests a bounded page size
- **WHEN** the Invitations page loads (with or without filters active)
- **THEN** the request to the invitations list endpoint specifies a `pageSize` covering the configured bound, and no page-forward/page-back control is shown on this page
