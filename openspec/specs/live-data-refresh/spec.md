# live-data-refresh Specification

## Purpose

The live-data-refresh capability keeps operational list and dashboard pages showing near-real-time data by polling in the background on a fixed interval, without taking away the user's ability to force an immediate refresh on demand.

## Requirements

### Requirement: Operational list and dashboard pages refresh their data automatically
The system SHALL automatically re-fetch an operational list, board, or dashboard page's data on a fixed 10-second interval while that page remains open, without requiring the user to take any action. This covers every admin and staff page that shows records rather than editing them, including the Admin, Staff, and Reception dashboards, every admin list page, the admin and staff Invitations boards, and the Audit Trail. The re-fetch SHALL be a silent background fetch from the API: data updates in place, with no page reload, loading indicator, or loss of scroll position, filters, or paging. Create and edit form pages, Organisation Configs, and the Register Visitor wizard SHALL NOT refresh automatically, so automatic refresh never replaces what a user is typing.

#### Scenario: Page left open
- **WHEN** an operational list or dashboard page has been open for at least 10 seconds
- **THEN** the system re-fetches that page's data automatically, without the user clicking anything

#### Scenario: New data appears
- **WHEN** an automatic refresh retrieves data that differs from what is currently displayed
- **THEN** the page updates to show the newly fetched data

#### Scenario: Audit Trail refreshes automatically
- **WHEN** an admin has the Audit Trail open for 10 seconds while new
  audited actions occur
- **THEN** the new entries appear without the admin activating anything,
  and the current filters and page are kept

#### Scenario: Form pages never refresh on their own
- **WHEN** an admin has the Edit Building form open for more than 10
  seconds, with or without typing
- **THEN** the form's data is never re-fetched or reset automatically

### Requirement: Automatic refresh does not interrupt an in-progress user action
The system SHALL skip an automatic refresh cycle if the user has a mutation or dialog in progress on that page at the moment the refresh would occur, and SHALL resume automatic refresh on subsequent cycles once that action completes.

#### Scenario: Refresh due during an open dialog or action
- **WHEN** the 10-second automatic refresh interval elapses while the user has a create, edit, or delete action or dialog open on the page
- **THEN** the system skips that refresh cycle instead of replacing the data underneath the in-progress action

#### Scenario: Refresh resumes after the action completes
- **WHEN** the in-progress action or dialog is closed or completed
- **THEN** subsequent automatic refresh cycles proceed normally

### Requirement: A manual refresh control remains available alongside automatic refresh
The system SHALL provide a manual refresh control in the top bar of every
admin page under `AdminLayout` and every staff page under `StaffLayout`,
including form pages and pages that load no data of their own. It lets the
user force an immediate re-fetch independent of the 10-second automatic
interval. On a page that loads no data of its own, the control SHALL
refresh the shell's shared data (the notification feed). On a create or
edit form page, Organisation Configs, or the Register Visitor wizard, the
control SHALL reload the page's data and reset the form to it. If the user
has unsaved changes there, it SHALL first ask them to confirm discarding
those changes, and SHALL leave the form untouched if they decline. Every admin page under `AdminLayout` that
fetches data on mount — including the Dashboard, Form Builder, the Form
Builder step editor, and Organisation Configs — SHALL provide this control
via the one shared `RefreshContext`-backed control in the admin top bar,
not a page-local, independently implemented refresh button. Every staff
page under `StaffLayout` that fetches data on mount, including the staff
Invitations board, SHALL likewise provide it through the same shared
control in the staff top bar.

The control SHALL reflect only refreshes the user starts. Its icon SHALL
spin from the moment the user activates it until that refresh finishes,
and SHALL NOT spin for automatic background refreshes. When the refresh
finishes, the icon SHALL come to rest in its upright, unrotated position
rather than stopping at whatever angle it had reached. The control SHALL
NOT show a last-updated time ("Updated just now", "Updated 2m ago").
When background refreshes keep failing after a successful load, it SHALL
still mark itself and say it is retrying, so a stale page is never
presented as current.

#### Scenario: User forces an immediate refresh
- **WHEN** the user activates the manual refresh control
- **THEN** the system re-fetches the page's data immediately, without
  waiting for the next automatic interval

#### Scenario: Dashboard uses the shared refresh control
- **WHEN** an admin is on the Dashboard page
- **THEN** the manual refresh control shown is the shared admin-top-bar
  control, not a separate button rendered by the Dashboard page itself

#### Scenario: Form Builder and its step editor register for refresh
- **WHEN** an admin is on the Form Builder page or a registration step's
  field editor page
- **THEN** the shared admin-top-bar refresh control re-fetches that page's
  data when activated

#### Scenario: Organisation Configs registers for refresh
- **WHEN** an admin is on the Organisation Configs page
- **THEN** the shared admin-top-bar refresh control re-fetches that page's
  data when activated

#### Scenario: Staff Invitations board uses the shared refresh control
- **WHEN** a staff member is on the staff Invitations page
- **THEN** the manual refresh control shown is the shared staff-top-bar control, not a separate button rendered by the page itself

#### Scenario: Every page shows the control
- **WHEN** an admin opens any admin page, including Reception Desks,
  Security Gates, New Branch, and Edit Role
- **THEN** the shared top-bar refresh control is present

#### Scenario: Refresh on a page with no data of its own
- **WHEN** an admin activates the refresh control on the Security Gates
  page
- **THEN** the notification feed and unread count are re-fetched

#### Scenario: Refresh on a form with unsaved changes
- **WHEN** an admin has typed into the Edit Department form and activates
  the refresh control
- **THEN** a confirmation asks whether to discard unsaved changes; on
  confirm the form reloads the department's saved data, and on cancel
  the typed values stay as they were

#### Scenario: Refresh on an untouched form
- **WHEN** a staff member is on the first step of the Register Visitor
  wizard without having entered anything, and activates the refresh
  control
- **THEN** the wizard's data reloads at once, with no confirmation

#### Scenario: Background refresh leaves the control still
- **WHEN** a list or dashboard page's 10-second automatic refresh runs
- **THEN** the refresh icon does not spin, and no "Updated …" text
  appears or changes

#### Scenario: Manual refresh spins until it finishes
- **WHEN** the user activates the refresh control
- **THEN** the icon spins until the page's re-fetch completes, then comes
  to rest upright, in the same orientation it had before the click

#### Scenario: Refresh finishes partway through a turn
- **WHEN** the page's re-fetch completes while the icon is part of the way
  through a rotation
- **THEN** the icon finishes turning to its upright position instead of
  stopping at the angle it had reached

#### Scenario: No last-updated text
- **WHEN** any admin or staff page is open at 1440px wide
- **THEN** the refresh control shows only its icon, with no "Updated …"
  label beside it

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
