## ADDED Requirements

### Requirement: Sidebar and top navigation remain fixed while content scrolls independently
The system SHALL render the sidebar and top navigation bar in a fixed position that does not move when the page's main content is scrolled, and SHALL confine vertical scrolling caused by page content to the main content region only.

#### Scenario: Long content scrolls only the content region
- **WHEN** a page's main content is taller than the viewport
- **THEN** the user can scroll to see the rest of the content while the sidebar and top navigation bar remain visible and stationary

#### Scenario: Short content does not scroll
- **WHEN** a page's main content fits within the viewport
- **THEN** no scrollbar appears in the main content region

### Requirement: No page triggers horizontal scrolling of the overall page
The system SHALL prevent any page's content from causing the outer page (document body/viewport) to scroll horizontally. Content that is intrinsically wider than the viewport (for example, a data table with many columns) SHALL scroll within its own contained region instead of widening the page.

#### Scenario: A wide table is rendered
- **WHEN** a page renders a table or other content wider than the viewport
- **THEN** that content scrolls horizontally within its own container and the outer page does not gain a horizontal scrollbar

#### Scenario: Normal page content
- **WHEN** a page's content fits within the viewport width
- **THEN** no horizontal scrollbar appears anywhere on the page

### Requirement: Route navigation is accompanied by a transition animation
The system SHALL play a brief visual transition when the user navigates from one route to another, instead of replacing the page's content instantaneously.

#### Scenario: Navigating between two pages
- **WHEN** a user navigates from one route to another within the app
- **THEN** the outgoing view's content transitions out and the incoming view's content transitions in, rather than one instantly replacing the other

#### Scenario: Reduced motion is requested
- **WHEN** the user's operating system or browser is set to prefer reduced motion
- **THEN** the system skips or minimizes the transition instead of playing it in full

### Requirement: Drill-down pages provide a way back to their parent page
The system SHALL show a back-navigation control on any page that is reached by navigating from another in-app page rather than directly from the sidebar (for example, a create/edit form reached from a list page's "Add" or "Edit" action). Activating that control SHALL return the user to the parent page they navigated from.

#### Scenario: Viewing a nested drill-down page
- **WHEN** a user is on a page reached by drilling down from a parent page, rather than a top-level sidebar destination
- **THEN** a back-navigation control is visible on that page

#### Scenario: Activating the back control
- **WHEN** the user activates the back-navigation control
- **THEN** the user is returned to the parent page they drilled down from

#### Scenario: Top-level sidebar destination
- **WHEN** a user is on a page reached directly from the sidebar
- **THEN** the page is not required to show a back-navigation control, since the sidebar itself is the primary means of navigating to it
