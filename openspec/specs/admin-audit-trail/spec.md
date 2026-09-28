# admin-audit-trail Specification

## Purpose

The admin-audit-trail capability gives an authenticated admin a complete, filterable, organisation-wide history of check-in, check-out, and review activity across all hosts and visitors, restricted to admins only.

## Requirements

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
The system SHALL render, for an authenticated admin session, the Admin sidebar with "Audit Trail" shown as the active item, the Admin top bar showing the signed-in admin's name and role, and the audit trail content (filters, activity log, pagination).

#### Scenario: Admin views the Audit Trail page
- **WHEN** an authenticated admin's Audit Trail page finishes loading
- **THEN** the sidebar (with "Audit Trail" marked active), the top bar, the filter bar, and the activity log are all visible

### Requirement: Date-range filter narrows the activity log
The system SHALL let the admin choose a date range for the activity log, defaulting to "Last 30 days", and SHALL show only activity within the selected range.

#### Scenario: Admin narrows by date range
- **WHEN** an admin selects a different date range
- **THEN** the activity log shows only entries whose timestamp falls within that range

### Requirement: Activity-type filter narrows the activity log
The system SHALL let the admin filter the activity log to a specific activity type from a curated set of visitor/invitation-related activities (Invitation Created, Walk-in Registered, Invitation Approved, Approval Step Approved, Checked In, Rescheduled), defaulting to "All Activities". Entries whose activity type is outside the curated set SHALL still appear when "All Activities" is selected.

#### Scenario: Admin narrows by activity type
- **WHEN** an admin selects a specific activity type from the curated set
- **THEN** the activity log shows only entries of that activity type

#### Scenario: Admin clears the activity type filter
- **WHEN** an admin selects "All Activities"
- **THEN** the activity log shows entries of every activity type, including ones outside the curated set, subject to the other active filters

### Requirement: Activity log entries show identifying and contextual details
The system SHALL render, for each activity log entry, its timestamp, a human-readable label for the action performed, the actor who performed it (or "System" when the action was not performed by a staff member), and the type of record affected.

#### Scenario: Entry renders its details
- **WHEN** an activity log entry is displayed
- **THEN** its row shows the timestamp, a human-readable action label, the actor (or "System"), and the affected record's type

#### Scenario: Unrecognized action still renders legibly
- **WHEN** an activity log entry's action is not one of the explicitly curated labels
- **THEN** the system derives a readable label from it rather than showing the raw machine value or omitting the row

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

### Requirement: Admin can download the filtered activity log as a report
The system SHALL let the admin request a downloadable report of the activity log (as CSV or PDF) using the currently selected date-range and activity-type filters, and SHALL, once the report is ready, offer it for download. While a report is being generated, the requested format's control SHALL show a preparing state and SHALL NOT accept another request until it resolves.

#### Scenario: Report generation succeeds
- **WHEN** an admin requests a CSV or PDF report and the backend reports the report as ready with a download link
- **THEN** the system opens the download link

#### Scenario: Report generation fails
- **WHEN** an admin requests a report and the backend reports the report as failed
- **THEN** the system shows an error notification describing the failure and does not attempt a download

#### Scenario: Report generation times out
- **WHEN** an admin requests a report and it does not reach a ready or failed state within a reasonable polling window
- **THEN** the system shows an error notification and does not attempt a download

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
