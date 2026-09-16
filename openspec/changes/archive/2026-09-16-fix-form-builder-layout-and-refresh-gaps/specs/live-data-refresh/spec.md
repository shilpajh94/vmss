## MODIFIED Requirements

### Requirement: A manual refresh control remains available alongside automatic refresh
The system SHALL provide a manual refresh control on every page that fetches
data on mount, letting the user force an immediate re-fetch independent of
the 15-second automatic interval. Every admin page under `AdminLayout` that
fetches data on mount — including the Dashboard, Form Builder, the Form
Builder step editor, and Organisation Configs — SHALL provide this control
via the one shared `RefreshContext`-backed control in the admin top bar,
not a page-local, independently implemented refresh button.

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
  data when activated, and shows that page's last-updated time

#### Scenario: Organisation Configs registers for refresh
- **WHEN** an admin is on the Organisation Configs page
- **THEN** the shared admin-top-bar refresh control re-fetches that page's
  data when activated, and shows that page's last-updated time
