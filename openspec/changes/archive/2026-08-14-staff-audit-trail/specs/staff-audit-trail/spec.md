## Purpose

The staff-audit-trail capability gives an authenticated staff member a complete, filterable history of check-in, check-out, and review activity for the visitors they host, so they can audit what happened and when.

## ADDED Requirements

### Requirement: Audit Trail page requires an authenticated staff session
The system SHALL check for a staff auth token before rendering the Audit Trail page, and SHALL redirect to `/staff/login` instead of rendering the page when no token is present.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token navigates to the Audit Trail page
- **THEN** the system redirects to `/staff/login` and does not render the page

#### Scenario: Token present
- **WHEN** a browser with a staff auth token navigates to the Audit Trail page
- **THEN** the system renders the Audit Trail page

### Requirement: Page renders the sidebar, workspace header, and audit trail content
The system SHALL render, for an authenticated session, the shared staff sidebar with "Audit trail" selected, a workspace header showing the "Audit Trail" title and a description of its scope, and the audit trail content (summary stats, filters, activity log, pagination).

#### Scenario: Authenticated staff views the Audit Trail page
- **WHEN** an authenticated staff member's Audit Trail page finishes loading
- **THEN** the sidebar (with "Audit trail" selected), the "Audit Trail" header, the summary stats, the filter bar, and the activity log are all visible

### Requirement: Workspace header shows the signed-in staff member
The system SHALL display the signed-in staff member's name and role in the workspace header, retrieved from the current-staff-user API, consistent with the staff-dashboard header.

#### Scenario: Current user loads successfully
- **WHEN** the page loads and the current-staff-user request succeeds
- **THEN** the header displays that staff member's name and role

### Requirement: Sign out ends the session and returns to login
The system SHALL, when "Sign out" is activated, clear the stored auth token and navigate to `/staff/login`.

#### Scenario: Staff signs out
- **WHEN** a staff member activates "Sign out"
- **THEN** the auth token is cleared and the system navigates to `/staff/login`

### Requirement: Summary stats reflect the signed-in staff member's hosted visitors
The system SHALL show three summary stats — Total Check-ins, Denied Entries, and Overstayed Visits — counted only from activity for visit requests where the signed-in staff member is the host.

#### Scenario: Stats load successfully
- **WHEN** the audit trail data loads successfully
- **THEN** each stat shows the count of matching activity for the signed-in staff member's hosted visitors

### Requirement: Date-range filter narrows the activity log
The system SHALL let the staff member choose a date range for the activity log, defaulting to "Last 30 days", and SHALL show only activity within the selected range.

#### Scenario: Staff narrows by date range
- **WHEN** a staff member selects a different date range
- **THEN** the activity log shows only entries whose timestamp falls within that range

### Requirement: Activity-type filter narrows the activity log
The system SHALL let the staff member filter the activity log to a specific activity type (e.g. Check-in, Check-out, Rejected, Modified, Escalated, Approved), defaulting to "All Activities".

#### Scenario: Staff narrows by activity type
- **WHEN** a staff member selects a specific activity type
- **THEN** the activity log shows only entries of that activity type

#### Scenario: Staff clears the activity type filter
- **WHEN** a staff member selects "All Activities"
- **THEN** the activity log shows entries of every activity type, subject to the other active filters

### Requirement: Search filters the activity log by visitor name
The system SHALL, as the staff member types in the visitor-name search field, show only activity log entries whose visitor name contains the entered text (case-insensitive), subject to the other active filters.

#### Scenario: Search narrows the activity log
- **WHEN** a staff member enters text in the visitor-name search field
- **THEN** only activity log entries whose visitor name contains that text remain visible

#### Scenario: Search is cleared
- **WHEN** a staff member clears the visitor-name search field
- **THEN** the activity log returns to reflecting only the other active filters

### Requirement: Activity log entries show identifying and contextual details
The system SHALL render, for each activity log entry, its timestamp, activity type, visitor name, a description, the zone, the access method, and a status.

#### Scenario: Entry renders its details
- **WHEN** an activity log entry is displayed
- **THEN** its row shows the timestamp, activity type, visitor name, description, zone, method, and status

### Requirement: Status is shown as a labeled pill
The system SHALL render each activity log entry's status as a labeled pill (e.g. Approved, Rejected, Completed, Modified, Flagged) styled to visually distinguish status categories.

#### Scenario: Entry status renders as a pill
- **WHEN** an activity log entry is displayed
- **THEN** its status appears as a labeled pill

### Requirement: Empty activity log shows an empty-state message
The system SHALL, when no activity log entries match the active filters, show an empty-state message in place of the table rows.

#### Scenario: No entries match
- **WHEN** the active filters match zero activity log entries
- **THEN** the system shows an empty-state message instead of table rows

### Requirement: Activity log is paginated
The system SHALL divide the filtered activity log into pages, show the current range and total count (e.g. "Showing 1-8 of 481 results"), and let the staff member move to the next or previous page.

#### Scenario: Staff navigates to the next page
- **WHEN** a staff member activates the next-page control and a further page exists
- **THEN** the system shows the next page of entries and updates the displayed range

#### Scenario: Staff navigates to the previous page
- **WHEN** a staff member activates the previous-page control and a prior page exists
- **THEN** the system shows the previous page of entries and updates the displayed range

#### Scenario: No further page exists
- **WHEN** the staff member is on the last page
- **THEN** the next-page control has no effect

### Requirement: List load failure is reported without crashing
The system SHALL, when the audit trail data fails to load, show an error message on the page and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the audit trail data fails to load
- **THEN** the system shows an error message and lets the staff member retry
