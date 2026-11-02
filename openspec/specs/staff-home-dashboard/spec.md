# staff-home-dashboard Specification

## Purpose
The personal landing dashboard at `/staff/dashboard` for hosts and other
non-admin, non-reception staff. It shows live counts, a trend and an upcoming
list, computed only over the visits relevant to the signed-in user.

## Requirements

### Requirement: Staff Dashboard Requires an Authenticated Session
The system SHALL redirect to `/staff/login` instead of rendering
`/staff/dashboard` when no staff auth token is present.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token opens `/staff/dashboard`
- **THEN** the system redirects to `/staff/login` and does not render the page

### Requirement: Staff Dashboard Shows the User's Own Visit Figures
The staff dashboard SHALL render inside the staff layout, with "Dashboard"
marked active in the sidebar. It SHALL show:
- a greeting with the user's first name and the server-provided date;
- four KPI tiles: "Visits today", "Inside now", "Awaiting approval" and
  "Upcoming", each from the personal overview;
- a "My visits" trend chart and a "My visits by status" chart, from the
  personal analytics.

Every figure SHALL cover only visits relevant to the signed-in user.

#### Scenario: Host views their dashboard
- **WHEN** a host with 3 relevant visits today opens `/staff/dashboard`
- **THEN** "Visits today" shows 3, and the charts reflect only that host's
  relevant visits

### Requirement: My Upcoming Visitors Lists the Next Scheduled Visits
The staff dashboard SHALL list up to 5 upcoming visitors, soonest first.
Each row SHALL show the visitor's name, scheduled date and time, and
purpose (or "Not specified"). Activating a row SHALL open that visit on the
staff invitations board. The card SHALL have a "View all" link to
`/staff/invitations?status=approved`. With no upcoming visits, the card
SHALL show the shared empty state.

#### Scenario: Open an upcoming visit
- **WHEN** a host activates an upcoming-visitor row
- **THEN** the system navigates to `/staff/invitations?invitationId=<id>`
  and that visit's details open

#### Scenario: View all upcoming
- **WHEN** a host activates "View all" on My upcoming visitors
- **THEN** the system navigates to `/staff/invitations?status=approved`

### Requirement: Staff Dashboard Load Failure Is Reported Without Crashing
When the initial load fails, the staff dashboard SHALL show an error
message, trigger an error notification, and offer a "Try again" control
that retries without reloading the page. Failures of background refreshes
SHALL follow `live-data-refresh`.

#### Scenario: Initial load fails
- **WHEN** the personal overview request fails on page entry
- **THEN** the page shows an error message with "Try again", and activating
  it re-requests the data
