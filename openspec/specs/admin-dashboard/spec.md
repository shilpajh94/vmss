# admin-dashboard Specification

## Purpose

The admin-dashboard capability is the Super Admin's landing screen at `/admin/dashboard`: it renders the Admin section shell with "Dashboard" active and gives an at-a-glance overview of today's visitor activity — KPIs, a 7-day traffic trend, recent check-ins, department distribution, and upcoming pre-registered visitors.

## Requirements

### Requirement: Dashboard requires an authenticated session
The system SHALL check for a staff auth token before rendering the Dashboard page, and SHALL redirect to `/staff/login` instead of rendering the page when no token is present.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token navigates to `/admin/dashboard`
- **THEN** the system redirects to `/staff/login` and does not render the page

#### Scenario: Token present
- **WHEN** a browser with a staff auth token navigates to `/admin/dashboard`
- **THEN** the system renders the Dashboard page

### Requirement: Admin sidebar and top bar render with "Dashboard" active
The system SHALL render, for an authenticated session, the Admin sidebar with "Dashboard" shown as the active item, and the Admin top bar showing "Organization Admin" with a Dashboard-specific description and the signed-in staff member's name and role.

#### Scenario: Admin views the Dashboard page
- **WHEN** an authenticated admin's Dashboard page finishes loading
- **THEN** the sidebar shows "Dashboard" marked active and the top bar shows the signed-in staff member's name and role

### Requirement: Dashboard overview data loads on page entry
The system SHALL, when the Dashboard page loads, fetch three things in
parallel:
- the dashboard overview: the expected-today, checked-in-today, on-site,
  pending-approval (with the oldest pending time) and upcoming counts, plus
  the upcoming pre-registered visitors;
- the branch-wide analytics for the selected range;
- the most recent check-ins.

The page SHALL render once all three succeed. It SHALL use the signed-in
user already loaded by the admin layout, rather than fetching it again, and
SHALL NOT fetch the employee directory to resolve host names.

#### Scenario: Overview loads successfully
- **WHEN** the Dashboard page loads and the overview, analytics and
  recent-check-ins fetches succeed
- **THEN** the KPI row, the four charts, recent check-ins, and upcoming
  visitors all render with the fetched data

#### Scenario: No redundant requests
- **WHEN** the Dashboard page loads or refreshes
- **THEN** it issues no request for the current user or for the employee
  directory of its own

### Requirement: KPI row shows four visitor count metrics
The system SHALL render four KPI tiles, as defined in `dashboard-insights`:
- **Expected Today**: visits scheduled for today, with "N checked in so far";
- **On-Site Now**;
- **Pending Approval**: with the oldest-waiting detail;
- **Upcoming Visitors**.

Each tile SHALL show its current count and link to the admin invitations
board, filtered to its status.

#### Scenario: KPI row renders
- **WHEN** the overview data loads successfully
- **THEN** each of the four KPI tiles shows its count from the fetched data,
  and "Expected Today" counts visits scheduled for today rather than
  requests created today

#### Scenario: Tile opens the board
- **WHEN** an admin activates the "On-Site Now" tile
- **THEN** the system navigates to `/admin/invitations?status=checked_in`

### Requirement: Recent Check-ins list shows identifying details per visitor
The system SHALL render, for each recent check-in entry:
- the visitor's name;
- the host's name, as returned by the API, or "Unassigned" when no host is
  resolved;
- the check-in time;
- the status: Checked In or Checked Out, taken from the entry's status.

Activating an entry SHALL open that visit on the admin invitations board.

#### Scenario: Recent check-ins render
- **WHEN** the recent-check-ins data loads successfully with at least one entry
- **THEN** each entry's name, host, time, and status are shown

#### Scenario: Host beyond the first hundred employees
- **WHEN** a check-in's host is the tenant's 150th employee
- **THEN** the entry shows that host's name, not "Unassigned"

#### Scenario: Open a check-in
- **WHEN** an admin activates a recent check-in entry
- **THEN** the system navigates to `/admin/invitations?invitationId=<id>`
  and that visit's details open

### Requirement: Empty Recent Check-ins shows the shared empty state
The system SHALL show the shared empty-state component in place of the Recent Check-ins rows when the overview data loads successfully with zero recent check-ins.

#### Scenario: No recent check-ins
- **WHEN** the overview data loads successfully with zero recent check-ins
- **THEN** the system shows the shared empty-state component instead of any rows

### Requirement: Upcoming Pre-Registered Visitors shows scheduled visit details
The system SHALL render, for each upcoming pre-registered visitor returned
by the overview data:
- the visitor's name;
- the host's name, or "Unassigned" when no host is resolved;
- the visit purpose (when provided);
- the scheduled visit date and time. When no visit date is set, the
  invitation's expiry date SHALL be shown instead.

Activating a row SHALL open that visit on the admin invitations board. The
card SHALL offer a "View all" link to `/admin/invitations?status=approved`.

#### Scenario: Upcoming visitors render
- **WHEN** the overview data loads successfully with at least one upcoming visitor
- **THEN** each entry's visitor name, host, purpose, and scheduled date and
  time are shown

#### Scenario: View all upcoming
- **WHEN** an admin activates "View all" on Upcoming Pre-Registered Visitors
- **THEN** the system navigates to `/admin/invitations?status=approved`

### Requirement: Empty Upcoming Pre-Registered Visitors shows the shared empty state
The system SHALL show the shared empty-state component in place of the Upcoming Pre-Registered Visitors rows when the overview data loads successfully with zero upcoming visitors.

#### Scenario: No upcoming visitors
- **WHEN** the overview data loads successfully with zero upcoming visitors
- **THEN** the system shows the shared empty-state component instead of any rows

### Requirement: Overview load failure is reported without crashing
The system SHALL, when the dashboard data fails to load on page entry, show
an error message on the page, trigger an error notification, and allow
retrying without reloading the page. When a background refresh fails after
a successful load, the page SHALL keep showing the last loaded data and
report the failure as defined in `live-data-refresh`.

#### Scenario: Initial load fails
- **WHEN** the dashboard overview fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

#### Scenario: Background refresh fails
- **WHEN** an automatic refresh fails after the dashboard has loaded
- **THEN** the KPI tiles, charts and lists keep their last values, and no
  full-page error replaces them

### Requirement: View All on Recent Check-ins opens the checked-in board
The system SHALL, when "View All" on Recent Check-ins is activated,
navigate to the admin invitations board filtered to checked-in visitors
(`/admin/invitations?status=checked_in`).

#### Scenario: View All activated
- **WHEN** an admin activates "View All" on Recent Check-ins
- **THEN** the system navigates to `/admin/invitations?status=checked_in`
  and the board shows the Checked-in invitations
