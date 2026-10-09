## MODIFIED Requirements

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

### Requirement: Upcoming Pre-Registered Visitors shows scheduled visit details
The system SHALL render, for each upcoming pre-registered visitor returned by the overview data, the visitor's name, host (or "Unassigned" when no host is resolved), visit purpose (when provided), and the invitation's expiry date. The list is informational only — it SHALL NOT present any row-level actions.

#### Scenario: Upcoming visitors render
- **WHEN** the overview data loads successfully with at least one upcoming visitor
- **THEN** each entry's visitor name, host, purpose, and expiry date are shown, with no action buttons on the row

## REMOVED Requirements

### Requirement: Visitor Traffic chart shows the past 7 days of daily visitor counts
**Reason**: The backend has no endpoint or field providing a historical daily-traffic series; there is no data to render this chart from.
**Migration**: None — the chart is removed from the Dashboard page.

The system SHALL render a chart plotting one data point per day for the past 7 days, each point labeled with its day and visitor count.

#### Scenario: Traffic chart renders
- **WHEN** the overview data loads successfully
- **THEN** the traffic chart shows one point per day for the 7 returned days, each labeled with its day and count

### Requirement: Visitors by Department shows per-department distribution
**Reason**: The backend has no endpoint or field providing a department-level visitor breakdown; there is no data to render this card from.
**Migration**: None — the card is removed from the Dashboard page.

The system SHALL render, for each department returned by the overview data, its name, visitor count, and percentage share of today's visitors, alongside the total number of active departments.

#### Scenario: Department breakdown renders
- **WHEN** the overview data loads successfully with at least one department entry
- **THEN** each department's name, count, and percentage are shown, and the active-department total is shown

### Requirement: Check In on an upcoming visitor checks them in
**Reason**: Product decision to make the Upcoming Pre-Registered Visitors list informational only, with no in-row actions.
**Migration**: None — there is currently no other check-in entry point in this app; checking a visitor in from the dashboard is no longer possible.

The system SHALL, when an admin activates "Check In" on an upcoming visitor row, check that visitor in, remove them from the visible Upcoming Pre-Registered Visitors list, and trigger a success notification; on failure it SHALL trigger an error notification and leave the visitor in the upcoming list.

#### Scenario: Check In succeeds
- **WHEN** an admin activates "Check In" on an upcoming visitor and the check-in succeeds
- **THEN** the system removes that visitor from the upcoming list and triggers a success notification

#### Scenario: Check In fails
- **WHEN** an admin activates "Check In" on an upcoming visitor and the check-in fails
- **THEN** the system triggers an error notification and the visitor remains in the upcoming list

### Requirement: Pre-Register Visitor opens the Register Visitor wizard
**Reason**: Product decision to make the Upcoming Pre-Registered Visitors card informational only, with no actions in its header either.
**Migration**: None — the Register Visitor wizard remains reachable from other entry points in the app (e.g. the staff visitor-registration flow); this card no longer links to it.

The system SHALL, when "Pre-Register Visitor" is activated, navigate to the Register Visitor wizard's first step.

#### Scenario: Pre-Register Visitor activated
- **WHEN** an admin activates "Pre-Register Visitor"
- **THEN** the system navigates to the Register Visitor wizard, showing the Visitor Info step

### Requirement: Print Pass and View All are presented but not yet functional
**Reason**: "Print Pass" is removed from the Upcoming Pre-Registered Visitors row entirely (superseded by making the row informational-only); "View All" on Recent Check-ins is unaffected by this change and needs no delta.
**Migration**: None — there is no "Print Pass" control anywhere on the Dashboard page anymore.

The system SHALL display "Print Pass" on each upcoming visitor row and "View All" on Recent Check-ins per the design, but SHALL NOT perform any action when either is activated.

#### Scenario: Print Pass activated
- **WHEN** an admin activates "Print Pass" on an upcoming visitor row
- **THEN** no printing or navigation occurs and the row is unchanged

#### Scenario: View All activated
- **WHEN** an admin activates "View All" on Recent Check-ins
- **THEN** the visible Recent Check-ins entries do not change

## ADDED Requirements

### Requirement: View All remains presented but not yet functional
The system SHALL display "View All" on Recent Check-ins per the design, but SHALL NOT perform any action when it is activated.

#### Scenario: View All activated
- **WHEN** an admin activates "View All" on Recent Check-ins
- **THEN** the visible Recent Check-ins entries do not change
