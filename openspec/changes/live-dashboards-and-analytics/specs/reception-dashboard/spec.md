## MODIFIED Requirements

### Requirement: Page renders the Reception sidebar and top bar
The system SHALL render, for an authenticated Reception session, a sidebar
with three navigation items: "Dashboard", "Invitations" and "My actions". It
SHALL also render the shared staff top bar, showing:
- the "Reception Desk" title;
- the shared refresh control with its last-updated time;
- the notification bell;
- the signed-in user's name and role;
- "Sign out".

On the Reception Dashboard page, "Dashboard" SHALL be marked active.

#### Scenario: Reception user views the Dashboard page
- **WHEN** an authenticated Reception user's Dashboard page finishes loading
- **THEN** the sidebar (with "Dashboard" marked active, alongside
  "Invitations" and "My actions") and the top bar with its refresh control
  are visible

#### Scenario: Manual refresh
- **WHEN** a Reception user activates the top-bar refresh control
- **THEN** the dashboard re-fetches its data immediately

### Requirement: Dashboard overview data loads on page entry
The system SHALL, when the Reception Dashboard page loads, fetch three
things in parallel:
- the dashboard overview: the expected-today, checked-in-today, on-site,
  pending-approval (with the oldest pending time) and upcoming counts, plus
  the upcoming pre-registered visitors;
- the branch-wide analytics for the selected range;
- the most recent check-ins.

The page SHALL render once all three succeed, showing the same KPI tiles,
four charts and lists as the admin dashboard. Every tile, row and "View
all" link SHALL navigate to the staff invitations board. The page SHALL
refresh automatically as defined in `live-data-refresh`.

#### Scenario: Overview loads successfully
- **WHEN** the Reception Dashboard page loads and the overview, analytics
  and recent-check-ins fetches succeed
- **THEN** the KPI row, the four charts, recent check-ins, and upcoming
  visitors all render with the fetched data

#### Scenario: Reception dashboard refreshes on its own
- **WHEN** the Reception Dashboard has been open and visible for 15 seconds
- **THEN** the system re-fetches its data without any user action

### Requirement: KPI row shows four visitor count metrics
The system SHALL render four KPI tiles, as defined in `dashboard-insights`:
"Expected Today", "On-Site Now", "Pending Approval" and "Upcoming
Visitors". Each SHALL show its current count and link to the staff
invitations board, filtered to its status.

#### Scenario: KPI row renders
- **WHEN** the overview data loads successfully
- **THEN** each of the four KPI tiles shows its count from the fetched data

#### Scenario: Tile opens the board
- **WHEN** a Reception user activates the "Pending Approval" tile
- **THEN** the system navigates to `/staff/invitations?status=submitted`

### Requirement: Recent Check-ins list shows identifying details per visitor
The system SHALL render, for each recent check-in entry:
- the visitor's name;
- the host's name, as returned by the API, or "Unassigned" when no host is
  resolved;
- the check-in time;
- the status: Checked In or Checked Out, taken from the entry's status.

Activating an entry SHALL open that visit on the staff invitations board.
"View All" SHALL navigate to `/staff/invitations?status=checked_in`.

#### Scenario: Recent check-ins render
- **WHEN** the recent-check-ins data loads successfully with at least one entry
- **THEN** each entry's name, host, time, and status are shown

#### Scenario: View All activated
- **WHEN** a Reception user activates "View All" on Recent Check-ins
- **THEN** the system navigates to `/staff/invitations?status=checked_in`

### Requirement: Upcoming Pre-Registered Visitors shows scheduled visit details
The system SHALL render, for each upcoming pre-registered visitor returned
by the overview data:
- the visitor's name;
- the host's name, or "Unassigned" when no host is resolved;
- the visit purpose (when provided);
- the scheduled visit date and time. When no visit date is set, the
  invitation's expiry date SHALL be shown instead.

Activating a row SHALL open that visit on the staff invitations board, and
the card SHALL offer a "View all" link to
`/staff/invitations?status=approved`.

#### Scenario: Upcoming visitors render
- **WHEN** the overview data loads successfully with at least one upcoming visitor
- **THEN** each entry's visitor name, host, purpose, and scheduled date and
  time are shown

#### Scenario: Open an upcoming visit
- **WHEN** a Reception user activates an upcoming-visitor row
- **THEN** the system navigates to `/staff/invitations?invitationId=<id>`

### Requirement: Overview load failure is reported without crashing
The system SHALL, when the dashboard data fails to load on page entry, show
an error message on the page, trigger an error notification, and allow
retrying without reloading the page. When a background refresh fails after
a successful load, the page SHALL keep showing the last loaded data and
report the failure as defined in `live-data-refresh`.

#### Scenario: Initial load fails
- **WHEN** the dashboard overview fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the user retry

#### Scenario: Background refresh fails
- **WHEN** an automatic refresh fails after the dashboard has loaded
- **THEN** the dashboard keeps its last values and shows no full-page error
