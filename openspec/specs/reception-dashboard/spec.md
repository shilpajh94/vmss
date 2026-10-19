# reception-dashboard Specification

## Purpose

The reception-dashboard capability gives an authenticated user with the Reception role an at-a-glance overview of today's visitor activity — the same KPI, recent check-ins, and upcoming-visitors overview the Admin Dashboard shows — restricted to the Reception role.

## Requirements

### Requirement: Reception Dashboard requires an authenticated session
The system SHALL check for a staff auth token before rendering the Reception Dashboard page, and SHALL redirect to `/staff/login` instead of rendering the page when no token is present.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token navigates to `/reception/dashboard`
- **THEN** the system redirects to `/staff/login` and does not render the page

#### Scenario: Token present
- **WHEN** a browser with a staff auth token navigates to `/reception/dashboard`
- **THEN** the system renders the Reception Dashboard page

### Requirement: Reception Dashboard is restricted to the Reception role
The system SHALL, once the current-staff-user response has loaded, check whether the signed-in user has the Reception role, and SHALL redirect a user who does not have that role to `/staff/dashboard` instead of rendering the Reception Dashboard or fetching its data.

#### Scenario: Reception user views the page
- **WHEN** an authenticated user whose current-staff-user response indicates they have the Reception role navigates to `/reception/dashboard`
- **THEN** the system renders the Reception Dashboard page

#### Scenario: Non-Reception user is redirected
- **WHEN** an authenticated user whose current-staff-user response indicates they do not have the Reception role navigates to `/reception/dashboard`
- **THEN** the system redirects to `/staff/dashboard` and does not render the Reception Dashboard or fetch its data

### Requirement: Page renders the Reception sidebar and top bar
The system SHALL render, for an authenticated Reception session, a sidebar with three navigation items — "Dashboard", "Invitations", and "My actions" — and a top bar showing the signed-in user's name and role. On the Reception Dashboard page, "Dashboard" SHALL be marked active.

#### Scenario: Reception user views the Dashboard page
- **WHEN** an authenticated Reception user's Dashboard page finishes loading
- **THEN** the sidebar (with "Dashboard" marked active, alongside "Invitations" and "My actions") and the top bar are visible

### Requirement: The Reception sidebar follows the user to the Visits and Register Visitor pages
The system SHALL, when a Reception user activates "Invitations" or "My actions" in the Reception sidebar, navigate to the staff Invitations board (`/staff/dashboard`) or Register Visitor wizard (`/staff/visitors/new`) respectively, and SHALL render the same Reception sidebar (not the plain staff sidebar) on those pages for a Reception-role session, with the matching item marked active.

#### Scenario: Reception user opens Visits
- **WHEN** a Reception user activates "Invitations" in the Reception sidebar
- **THEN** the system navigates to `/staff/dashboard` and renders the Reception sidebar there, with "Invitations" marked active

#### Scenario: Reception user opens My actions
- **WHEN** a Reception user activates "My actions" in the Reception sidebar
- **THEN** the system navigates to `/staff/visitors/new` and renders the Reception sidebar there, with "My actions" marked active

### Requirement: Dashboard overview data loads on page entry
The system SHALL, when the Reception Dashboard page loads, fetch the dashboard overview data (today's visit count, currently-checked-in count, pending-approval count, upcoming-visitor count, and the list of upcoming pre-registered visitors) together with the recent check-ins list, and render the page once both fetches succeed.

#### Scenario: Overview loads successfully
- **WHEN** the Reception Dashboard page loads and both the overview and recent-check-ins fetches succeed
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
The system SHALL show the shared empty-state component in place of the Recent Check-ins rows when the data loads successfully with zero recent check-ins.

#### Scenario: No recent check-ins
- **WHEN** the recent-check-ins data loads successfully with zero entries
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

### Requirement: Sign out ends the session and returns to login
The system SHALL, when "Sign out" is activated, clear the stored auth token and navigate to `/staff/login`.

#### Scenario: Reception user signs out
- **WHEN** a Reception user activates "Sign out"
- **THEN** the auth token is cleared and the system navigates to `/staff/login`

### Requirement: Overview load failure is reported without crashing
The system SHALL, when the dashboard overview data fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the dashboard overview fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the user retry
