## MODIFIED Requirements

### Requirement: Sidebar and top navigation remain fixed while content scrolls independently
The system SHALL render the sidebar and top navigation bar in a fixed position that does not move when the page's main content is scrolled, and SHALL confine vertical scrolling caused by page content to the main content region only. Within the sidebar itself, the logo/header area and any footer content SHALL remain pinned in place, and the navigation item list SHALL scroll independently when it is taller than the space available, so no navigation item becomes unreachable.

#### Scenario: Long content scrolls only the content region
- **WHEN** a page's main content is taller than the viewport
- **THEN** the user can scroll to see the rest of the content while the sidebar and top navigation bar remain visible and stationary

#### Scenario: Short content does not scroll
- **WHEN** a page's main content fits within the viewport
- **THEN** no scrollbar appears in the main content region

#### Scenario: Sidebar navigation list is longer than the viewport
- **WHEN** the sidebar's navigation item list is taller than the vertical space available
- **THEN** the navigation item list scrolls internally to reveal the remaining items, while the sidebar's logo/header and any footer content stay pinned in place

#### Scenario: Sidebar navigation list fits the viewport
- **WHEN** the sidebar's navigation item list fits within the space available
- **THEN** no scrollbar appears within the sidebar
