## MODIFIED Requirements

### Requirement: Page renders the sidebar, workspace header, and audit trail content
The system SHALL render, for an authenticated session, the shared staff sidebar with "Audit trail" selected, a workspace header showing the "Audit Trail" title and a description of its scope, and the audit trail content (filters, activity log, pagination).

#### Scenario: Authenticated staff views the Audit Trail page
- **WHEN** an authenticated staff member's Audit Trail page finishes loading
- **THEN** the sidebar (with "Audit trail" selected), the "Audit Trail" header, the filter bar, and the activity log are all visible

### Requirement: Activity-type filter narrows the activity log
The system SHALL let the staff member filter the activity log to a specific activity type from a curated set of visitor/invitation-related activities (Invitation Created, Walk-in Registered, Invitation Approved, Approval Step Approved, Checked In, Rescheduled), defaulting to "All Activities". Entries whose activity type is outside the curated set SHALL still appear when "All Activities" is selected.

#### Scenario: Staff narrows by activity type
- **WHEN** a staff member selects a specific activity type from the curated set
- **THEN** the activity log shows only entries of that activity type

#### Scenario: Staff clears the activity type filter
- **WHEN** a staff member selects "All Activities"
- **THEN** the activity log shows entries of every activity type, including ones outside the curated set, subject to the other active filters

### Requirement: Activity log entries show identifying and contextual details
The system SHALL render, for each activity log entry, its timestamp, a human-readable label for the action performed, the actor who performed it (or "System" when the action was not performed by a staff member), and the type of record affected.

#### Scenario: Entry renders its details
- **WHEN** an activity log entry is displayed
- **THEN** its row shows the timestamp, a human-readable action label, the actor (or "System"), and the affected record's type

#### Scenario: Unrecognized action still renders legibly
- **WHEN** an activity log entry's action is not one of the explicitly curated labels
- **THEN** the system derives a readable label from it rather than showing the raw machine value or omitting the row

## ADDED Requirements

### Requirement: Staff can download the filtered activity log as a report
The system SHALL let the staff member request a downloadable report of the activity log (as CSV or PDF) using the currently selected date-range and activity-type filters, and SHALL, once the report is ready, offer it for download. While a report is being generated, the requested format's control SHALL show a preparing state and SHALL NOT accept another request until it resolves.

#### Scenario: Report generation succeeds
- **WHEN** a staff member requests a CSV or PDF report and the backend reports the report as ready with a download link
- **THEN** the system opens the download link

#### Scenario: Report generation fails
- **WHEN** a staff member requests a report and the backend reports the report as failed
- **THEN** the system shows an error notification describing the failure and does not attempt a download

#### Scenario: Report generation times out
- **WHEN** a staff member requests a report and it does not reach a ready or failed state within a reasonable polling window
- **THEN** the system shows an error notification and does not attempt a download

## REMOVED Requirements

### Requirement: Summary stats reflect the signed-in staff member's hosted visitors
**Reason**: The real audit trail is a system-wide record-change log with no concept of "hosted visitors" and no check-in/denial/overstay aggregate; there is no backend data to compute these stats from.
**Migration**: None — the summary stats section is removed from the page.

The system SHALL show three summary stats — Total Check-ins, Denied Entries, and Overstayed Visits — counted only from activity for visit requests where the signed-in staff member is the host.

#### Scenario: Stats load successfully
- **WHEN** the audit trail data loads successfully
- **THEN** each stat shows the count of matching activity for the signed-in staff member's hosted visitors

### Requirement: Search filters the activity log by visitor name
**Reason**: The real audit trail resource has no visitor-name field (it records actor/action/entity/timestamp, not visitor identity); there is nothing to search against.
**Migration**: None — the visitor-name search field is removed from the filter bar.

The system SHALL, as the staff member types in the visitor-name search field, show only activity log entries whose visitor name contains the entered text (case-insensitive), subject to the other active filters.

#### Scenario: Search narrows the activity log
- **WHEN** a staff member enters text in the visitor-name search field
- **THEN** only activity log entries whose visitor name contains that text remain visible

#### Scenario: Search is cleared
- **WHEN** a staff member clears the visitor-name search field
- **THEN** the activity log returns to reflecting only the other active filters

### Requirement: Status is shown as a labeled pill
**Reason**: The real audit trail resource has no discrete status field (Approved/Rejected/Completed/Modified/Flagged); the human-readable action label already communicates what happened (see "Activity log entries show identifying and contextual details").
**Migration**: None — no replacement status pill; the action label serves this purpose.

The system SHALL render each activity log entry's status as a labeled pill (e.g. Approved, Rejected, Completed, Modified, Flagged) styled to visually distinguish status categories.

#### Scenario: Entry status renders as a pill
- **WHEN** an activity log entry is displayed
- **THEN** its status appears as a labeled pill
