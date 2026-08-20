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
The system SHALL, when the Dashboard page loads, fetch the dashboard overview data (KPI metrics, 7-day visitor traffic series, recent check-ins, department breakdown, and upcoming pre-registered visitors) and render the page once the fetch succeeds.

#### Scenario: Overview loads successfully
- **WHEN** the Dashboard page loads and the overview fetch succeeds
- **THEN** the KPI row, traffic chart, recent check-ins, department breakdown, and upcoming visitors all render with the fetched data

### Requirement: KPI row shows four visitor metrics with trend captions
The system SHALL render four KPI cards — Today's Visitors, Currently On-Site, Pre-Registered, Average Visit Duration — each showing its current value and a trend caption describing the change.

#### Scenario: KPI row renders
- **WHEN** the overview data loads successfully
- **THEN** each of the four KPI cards shows its value and trend caption from the fetched data

### Requirement: Visitor Traffic chart shows the past 7 days of daily visitor counts
The system SHALL render a chart plotting one data point per day for the past 7 days, each point labeled with its day and visitor count.

#### Scenario: Traffic chart renders
- **WHEN** the overview data loads successfully
- **THEN** the traffic chart shows one point per day for the 7 returned days, each labeled with its day and count

### Requirement: Recent Check-ins list shows identifying details per visitor
The system SHALL render, for each recent check-in entry returned by the overview data, the visitor's name, host name, check-in time, badge number, and status (Checked In or Checked Out).

#### Scenario: Recent check-ins render
- **WHEN** the overview data loads successfully with at least one recent check-in
- **THEN** each entry's name, host, time, badge number, and status are shown

### Requirement: Empty Recent Check-ins shows the shared empty state
The system SHALL show the shared empty-state component in place of the Recent Check-ins rows when the overview data loads successfully with zero recent check-ins.

#### Scenario: No recent check-ins
- **WHEN** the overview data loads successfully with zero recent check-ins
- **THEN** the system shows the shared empty-state component instead of any rows

### Requirement: Visitors by Department shows per-department distribution
The system SHALL render, for each department returned by the overview data, its name, visitor count, and percentage share of today's visitors, alongside the total number of active departments.

#### Scenario: Department breakdown renders
- **WHEN** the overview data loads successfully with at least one department entry
- **THEN** each department's name, count, and percentage are shown, and the active-department total is shown

### Requirement: Upcoming Pre-Registered Visitors shows scheduled visit details
The system SHALL render, for each upcoming pre-registered visitor returned by the overview data, the scheduled time, visitor name and company, host name, and visit purpose.

#### Scenario: Upcoming visitors render
- **WHEN** the overview data loads successfully with at least one upcoming visitor
- **THEN** each entry's scheduled time, visitor name and company, host name, and purpose are shown

### Requirement: Empty Upcoming Pre-Registered Visitors shows the shared empty state
The system SHALL show the shared empty-state component in place of the Upcoming Pre-Registered Visitors rows when the overview data loads successfully with zero upcoming visitors.

#### Scenario: No upcoming visitors
- **WHEN** the overview data loads successfully with zero upcoming visitors
- **THEN** the system shows the shared empty-state component instead of any rows

### Requirement: Check In on an upcoming visitor checks them in
The system SHALL, when an admin activates "Check In" on an upcoming visitor row, check that visitor in, remove them from the visible Upcoming Pre-Registered Visitors list, and trigger a success notification; on failure it SHALL trigger an error notification and leave the visitor in the upcoming list.

#### Scenario: Check In succeeds
- **WHEN** an admin activates "Check In" on an upcoming visitor and the check-in succeeds
- **THEN** the system removes that visitor from the upcoming list and triggers a success notification

#### Scenario: Check In fails
- **WHEN** an admin activates "Check In" on an upcoming visitor and the check-in fails
- **THEN** the system triggers an error notification and the visitor remains in the upcoming list

### Requirement: Pre-Register Visitor opens the Register Visitor wizard
The system SHALL, when "Pre-Register Visitor" is activated, navigate to the Register Visitor wizard's first step.

#### Scenario: Pre-Register Visitor activated
- **WHEN** an admin activates "Pre-Register Visitor"
- **THEN** the system navigates to the Register Visitor wizard, showing the Visitor Info step

### Requirement: Print Pass and View All are presented but not yet functional
The system SHALL display "Print Pass" on each upcoming visitor row and "View All" on Recent Check-ins per the design, but SHALL NOT perform any action when either is activated.

#### Scenario: Print Pass activated
- **WHEN** an admin activates "Print Pass" on an upcoming visitor row
- **THEN** no printing or navigation occurs and the row is unchanged

#### Scenario: View All activated
- **WHEN** an admin activates "View All" on Recent Check-ins
- **THEN** the visible Recent Check-ins entries do not change

### Requirement: Overview load failure is reported without crashing
The system SHALL, when the dashboard overview data fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the dashboard overview fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry
