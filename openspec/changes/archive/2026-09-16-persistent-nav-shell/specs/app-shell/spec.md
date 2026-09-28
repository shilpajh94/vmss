## MODIFIED Requirements

### Requirement: Route navigation is accompanied by a transition animation
The system SHALL play a brief visual transition when the user navigates from one route to another, instead of replacing the page's content instantaneously. Where a route belongs to a section with a shared sidebar (and, for the admin section, a shared top bar), that transition SHALL be scoped to the main content region only: the sidebar and top bar SHALL remain mounted and SHALL NOT re-render or participate in the transition when navigating between routes within the same section.

#### Scenario: Navigating between two pages
- **WHEN** a user navigates from one route to another within the app
- **THEN** the outgoing view's content transitions out and the incoming view's content transitions in, rather than one instantly replacing the other

#### Scenario: Reduced motion is requested
- **WHEN** the user's operating system or browser is set to prefer reduced motion
- **THEN** the system skips or minimizes the transition instead of playing it in full

#### Scenario: Navigating within the admin section
- **WHEN** an authenticated admin user navigates from one admin page to another (e.g. from the branches list to the departments list)
- **THEN** the sidebar and top bar remain the same, unchanged elements on screen — they do not unmount, flash, or reset — and only the main content region plays the transition and shows the new page's content

#### Scenario: Navigating within the staff section
- **WHEN** a staff user navigates from one staff page to another (e.g. from the dashboard to the audit trail)
- **THEN** the sidebar remains the same, unchanged element on screen — it does not unmount, flash, or reset — while the rest of the page (including that page's own header) transitions in as content
