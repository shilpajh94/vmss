## ADDED Requirements

### Requirement: Automatic refresh pauses while the page is hidden
The system SHALL NOT run automatic refresh cycles while the browser tab is
hidden. When the tab becomes visible again, or the window regains focus,
the system SHALL re-fetch the page's data immediately, and then resume the
15-second interval. Re-fetches triggered by visibility or focus SHALL run
at most once every 5 seconds.

#### Scenario: Tab in the background
- **WHEN** a dashboard tab stays hidden for two minutes
- **THEN** the system issues no automatic refresh requests for that page
  during that time

#### Scenario: Returning to the tab
- **WHEN** the user switches back to a dashboard tab that was hidden
- **THEN** the page re-fetches its data at once, without waiting for the
  next interval

### Requirement: Dashboards refresh when invitation activity is notified
The system SHALL, when a new in-app notification about an invitation
arrives (for example: submitted, approved, checked in, checked out), make
any open dashboard page re-fetch its data immediately. The re-fetch SHALL
NOT wait for the next 15-second interval, and SHALL respect the
in-progress-action rule.

#### Scenario: Check-in notification updates the dashboard
- **WHEN** a dashboard is open and a "visitor checked in" notification
  arrives
- **THEN** the dashboard re-fetches, and its on-site count and arrivals
  chart reflect the check-in without the user clicking refresh

### Requirement: Background refresh failures are reported once, not every cycle
The system SHALL, when an automatic refresh fails after the page has
loaded, keep the last loaded data on screen and show a single error
notification. The shared refresh control SHALL show that refreshing failed
and is being retried. While refreshes keep failing, the system SHALL NOT
show further error notifications. The first successful refresh after a
failure SHALL clear the failed state and update the last-updated time.

#### Scenario: API outage during a long session
- **WHEN** four consecutive automatic refreshes fail
- **THEN** exactly one error notification is shown, the refresh control
  indicates it is retrying, and the previously loaded data stays visible

#### Scenario: Recovery
- **WHEN** an automatic refresh succeeds after earlier failures
- **THEN** the retrying indication disappears and the data and last-updated
  time update
