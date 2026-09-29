## Purpose

The admin-audit-trail capability gives an authenticated admin a complete, filterable, organisation-wide history of check-in, check-out, and review activity across all hosts and visitors, restricted to admins only.

## ADDED Requirements

### Requirement: Audit Trail page requires an authenticated session
The system SHALL check for a staff auth token before rendering the Audit Trail page, and SHALL redirect to `/admin/login` instead of rendering the page when no token is present.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token navigates to `/admin/audit-trail`
- **THEN** the system redirects to `/admin/login` and does not render the page

#### Scenario: Token present
- **WHEN** a browser with a staff auth token navigates to `/admin/audit-trail`
- **THEN** the system renders the Audit Trail page

### Requirement: Audit Trail page is restricted to admins only
The system SHALL, once the current-staff-user response has loaded, check whether the signed-in user is an admin, and SHALL redirect a non-admin authenticated user to `/staff/dashboard` instead of rendering the Audit Trail page or its data.

#### Scenario: Admin views the page
- **WHEN** an authenticated user whose current-staff-user response indicates they are an admin navigates to `/admin/audit-trail`
- **THEN** the system renders the Audit Trail page

#### Scenario: Non-admin staff member is redirected
- **WHEN** an authenticated user whose current-staff-user response indicates they are not an admin navigates to `/admin/audit-trail`
- **THEN** the system redirects to `/staff/dashboard` and does not render the Audit Trail page or fetch its data

### Requirement: Page renders the admin sidebar, top bar, and audit trail content
The system SHALL render, for an authenticated admin session, the Admin sidebar with "Audit Trail" shown as the active item, the Admin top bar showing the signed-in admin's name and role, and the audit trail content (summary stats, filters, activity log, pagination).

#### Scenario: Admin views the Audit Trail page
- **WHEN** an authenticated admin's Audit Trail page finishes loading
- **THEN** the sidebar (with "Audit Trail" marked active), the top bar, the summary stats, the filter bar, and the activity log are all visible

### Requirement: Summary stats reflect organisation-wide activity
The system SHALL show three summary stats — Total Check-ins, Denied Entries, and Overstayed Visits — counted from activity across every host and visitor in the organisation, not limited to any single host.

#### Scenario: Stats load successfully
- **WHEN** the audit trail data loads successfully
- **THEN** each stat shows the organisation-wide count of matching activity

### Requirement: Date-range filter narrows the activity log
The system SHALL let the admin choose a date range for the activity log, defaulting to "Last 30 days", and SHALL show only activity within the selected range.

#### Scenario: Admin narrows by date range
- **WHEN** an admin selects a different date range
- **THEN** the activity log shows only entries whose timestamp falls within that range

### Requirement: Activity-type filter narrows the activity log
The system SHALL let the admin filter the activity log to a specific activity type (e.g. Check-in, Check-out, Rejected, Modified, Escalated, Approved), defaulting to "All Activities".

#### Scenario: Admin narrows by activity type
- **WHEN** an admin selects a specific activity type
- **THEN** the activity log shows only entries of that activity type

#### Scenario: Admin clears the activity type filter
- **WHEN** an admin selects "All Activities"
- **THEN** the activity log shows entries of every activity type, subject to the other active filters

### Requirement: Search filters the activity log by visitor name
The system SHALL, as the admin types in the visitor-name search field, show only activity log entries whose visitor name contains the entered text (case-insensitive), subject to the other active filters.

#### Scenario: Search narrows the activity log
- **WHEN** an admin enters text in the visitor-name search field
- **THEN** only activity log entries whose visitor name contains that text remain visible

#### Scenario: Search is cleared
- **WHEN** an admin clears the visitor-name search field
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
The system SHALL divide the filtered activity log into pages, show the current range and total count (e.g. "Showing 1-8 of 481 results"), and let the admin move to the next or previous page.

#### Scenario: Admin navigates to the next page
- **WHEN** an admin activates the next-page control and a further page exists
- **THEN** the system shows the next page of entries and updates the displayed range

#### Scenario: Admin navigates to the previous page
- **WHEN** an admin activates the previous-page control and a prior page exists
- **THEN** the system shows the previous page of entries and updates the displayed range

#### Scenario: No further page exists
- **WHEN** the admin is on the last page
- **THEN** the next-page control has no effect

### Requirement: Admin can request and download an audit report
The system SHALL let the admin request an audit report in one or more formats for the current date-range/activity-type filters, and SHALL let them download a completed report once it is ready.

#### Scenario: Report request succeeds
- **WHEN** an admin requests a report for the active filters
- **THEN** the system starts the report job and shows its progress

#### Scenario: Report download succeeds
- **WHEN** an admin downloads a completed report
- **THEN** the system retrieves the report file for that job

### Requirement: List load failure is reported without crashing
The system SHALL, when the audit trail data fails to load, show an error message on the page and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the audit trail data fails to load
- **THEN** the system shows an error message and lets the admin retry

### Requirement: Audit trail load failure also triggers a notification
The system SHALL, in addition to the inline error message, trigger an error notification when the audit trail data fails to load.

#### Scenario: Initial load fails
- **WHEN** the audit trail data fails to load
- **THEN** the system shows an error message on the page and also triggers an error notification

### Requirement: Sign out ends the session and returns to login
The system SHALL, when "Sign out" is activated, clear the stored auth token and navigate to `/admin/login`.

#### Scenario: Admin signs out
- **WHEN** an admin activates "Sign out"
- **THEN** the auth token is cleared and the system navigates to `/admin/login`
