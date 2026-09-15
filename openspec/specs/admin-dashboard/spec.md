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
The system SHALL, when the Dashboard page loads, fetch the dashboard overview data (today's visit count, currently-checked-in count, pending-approval count, upcoming-visitor count, and the list of upcoming pre-registered visitors) together with the recent check-ins list, and render the page once both fetches succeed.

#### Scenario: Overview loads successfully
- **WHEN** the Dashboard page loads and both the overview and recent-check-ins fetches succeed
- **THEN** the KPI row, recent check-ins, and upcoming visitors all render with the fetched data

### Requirement: KPI row shows four visitor count metrics
The system SHALL render four KPI cards — Today's Visitors, Currently On-Site, Pending Approval, Upcoming Visitors — each showing its current count.

#### Scenario: KPI row renders
- **WHEN** the overview data loads successfully
- **THEN** each of the four KPI cards shows its count from the fetched data

### Requirement: Recent Check-ins list shows identifying details per visitor
The system SHALL render, for each recent check-in entry, the visitor's name, host (or "Unassigned" when no host is resolved), check-in time, and status (Checked In or Checked Out, determined by whether a check-out time is present).

#### Scenario: Recent check-ins render
- **WHEN** the recent-check-ins data loads successfully with at least one entry
- **THEN** each entry's name, host, time, and status are shown

### Requirement: Empty Recent Check-ins shows the shared empty state
The system SHALL show the shared empty-state component in place of the Recent Check-ins rows when the overview data loads successfully with zero recent check-ins.

#### Scenario: No recent check-ins
- **WHEN** the overview data loads successfully with zero recent check-ins
- **THEN** the system shows the shared empty-state component instead of any rows

### Requirement: Upcoming Pre-Registered Visitors shows scheduled visit details
The system SHALL render, for each upcoming pre-registered visitor returned by the overview data, the visitor's name, host (or "Unassigned" when no host is resolved), visit purpose (when provided), and the invitation's expiry date. The list is informational only — it SHALL NOT present any row-level actions.

#### Scenario: Upcoming visitors render
- **WHEN** the overview data loads successfully with at least one upcoming visitor
- **THEN** each entry's visitor name, host, purpose, and expiry date are shown, with no action buttons on the row

### Requirement: Empty Upcoming Pre-Registered Visitors shows the shared empty state
The system SHALL show the shared empty-state component in place of the Upcoming Pre-Registered Visitors rows when the overview data loads successfully with zero upcoming visitors.

#### Scenario: No upcoming visitors
- **WHEN** the overview data loads successfully with zero upcoming visitors
- **THEN** the system shows the shared empty-state component instead of any rows

### Requirement: View All remains presented but not yet functional
The system SHALL display "View All" on Recent Check-ins per the design, but SHALL NOT perform any action when it is activated.

#### Scenario: View All activated
- **WHEN** an admin activates "View All" on Recent Check-ins
- **THEN** the visible Recent Check-ins entries do not change

### Requirement: Overview load failure is reported without crashing
The system SHALL, when the dashboard overview data fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the dashboard overview fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry
