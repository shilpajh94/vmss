## MODIFIED Requirements

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
