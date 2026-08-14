## Purpose

The staff-dashboard capability is the authenticated staff landing screen at `/staff/dashboard`: it shows every visit request for the organisation grouped by status so staff can review activity at a glance.

## ADDED Requirements

### Requirement: Dashboard requires an authenticated session
The system SHALL check for a staff auth token before rendering the dashboard, and SHALL redirect to `/staff/login` instead of rendering the dashboard when no token is present.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token navigates to `/staff/dashboard`
- **THEN** the system redirects to `/staff/login` and does not render the dashboard

#### Scenario: Token present
- **WHEN** a browser with a staff auth token navigates to `/staff/dashboard`
- **THEN** the system renders the dashboard

### Requirement: Dashboard renders the sidebar, workspace header, and kanban board
The system SHALL render, for an authenticated session, a sidebar (brand mark, "All visitors" / "My actions" / "Audit trail" navigation with "All visitors" selected, and a "Help & Support" link) and a main workspace containing the header, search bar, and visit-requests kanban board.

#### Scenario: Authenticated staff views the dashboard
- **WHEN** an authenticated staff member's dashboard finishes loading
- **THEN** the sidebar, the "Visits" workspace header, the search bar, and the kanban board are all visible

### Requirement: Other sidebar navigation items are visible but not yet functional
The system SHALL render the "My actions" and "Audit trail" sidebar items and the "Help & Support" link per the design, but SHALL NOT navigate anywhere when they are activated.

#### Scenario: Inert nav item activated
- **WHEN** a staff member activates "My actions", "Audit trail", or "Help & Support"
- **THEN** the current view does not change

### Requirement: Workspace header shows the signed-in staff member
The system SHALL display the signed-in staff member's name and role in the workspace header, retrieved from the current-staff-user API.

#### Scenario: Current user loads successfully
- **WHEN** the dashboard loads and the current-staff-user request succeeds
- **THEN** the header displays that staff member's name and role

### Requirement: Sign out ends the session and returns to login
The system SHALL, when "Sign out" is activated, clear the stored auth token and navigate to `/staff/login`.

#### Scenario: Staff signs out
- **WHEN** a staff member activates "Sign out"
- **THEN** the auth token is cleared and the system navigates to `/staff/login`

### Requirement: Visit requests are grouped into four status columns with live counts
The system SHALL group visit requests into four columns — Requested, Approved, Checked-in, Denied — each showing a count badge equal to the number of requests currently in that column.

#### Scenario: Requests load successfully
- **WHEN** the visit-requests list loads successfully
- **THEN** each request appears under the column matching its status, and each column's count badge reflects the number of requests shown in it

### Requirement: Visit request cards display identifying details
The system SHALL render, for each visit request, an avatar showing the visitor's initials, the REQ ID, the visitor's name, the assigned host's name, and the scheduled date and time.

#### Scenario: Card renders request details
- **WHEN** a visit request is displayed on the board
- **THEN** its card shows the visitor's initials, REQ ID, name, host name, and scheduled date/time

### Requirement: Empty status columns show an empty-state message
The system SHALL, when a status column has no visit requests, show an empty-state message in place of any cards.

#### Scenario: Column has no requests
- **WHEN** a status column has zero visit requests
- **THEN** the system shows an empty-state message instead of any cards

### Requirement: Search filters visible requests by visitor, host, or REQ ID
The system SHALL, as the staff member types in the search field, show only visit requests whose visitor name, host name, or REQ ID contains the entered text (case-insensitive), across all columns.

#### Scenario: Search narrows the board
- **WHEN** a staff member enters text in the search field
- **THEN** only visit requests whose visitor name, host name, or REQ ID contains that text remain visible, in their existing columns

#### Scenario: Search is cleared
- **WHEN** a staff member clears the search field
- **THEN** all loaded visit requests are shown again

### Requirement: Filters affordance is presented but not yet functional
The system SHALL display the "Filters" control per the design, but SHALL NOT apply any filtering when it is activated.

#### Scenario: Filters activated
- **WHEN** a staff member activates "Filters"
- **THEN** the visible visit requests do not change

### Requirement: Refresh reloads the visit-requests list
The system SHALL, when a refresh action is activated, re-fetch the visit-requests list from the backend and re-render the board with the latest data.

#### Scenario: Staff refreshes the board
- **WHEN** a staff member activates a refresh action
- **THEN** the system re-fetches the visit-requests list and updates the board with the result

### Requirement: List load failure is reported without crashing
The system SHALL, when the visit-requests list fails to load, show an error message on the dashboard and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the visit-requests list fails to load
- **THEN** the system shows an error message and lets the staff member retry
