## MODIFIED Requirements

### Requirement: Sidebar and top navigation remain fixed while content scrolls independently
The system SHALL render the top navigation bar in a fixed position that does not move when the page's main content is scrolled, and SHALL confine vertical scrolling caused by page content to the main content region only. At viewport widths of 1024px and wider, the sidebar SHALL likewise be permanently visible in a fixed position beside the content. Below 1024px, the sidebar SHALL be hidden by default and SHALL open as an off-canvas drawer over the content, with a dimmed backdrop, from a menu button in the top bar; see "Sidebar collapses into a drawer below desktop width". Within the sidebar itself (docked or drawer), the logo/header area and any footer content SHALL remain pinned in place, and the navigation item list SHALL scroll independently when it is taller than the space available, so no navigation item becomes unreachable. Where the sidebar's navigation list scrolls, its scrollbar SHALL be styled to fit the sidebar's dark theme rather than rendered as the browser's unstyled default.

#### Scenario: Long content scrolls only the content region
- **WHEN** a page's main content is taller than the viewport
- **THEN** the user can scroll to see the rest of the content while the top navigation bar (and, at desktop width, the sidebar) remain visible and stationary

#### Scenario: Short content does not scroll
- **WHEN** a page's main content fits within the viewport
- **THEN** no scrollbar appears in the main content region

#### Scenario: Sidebar navigation list is longer than the viewport
- **WHEN** the sidebar's navigation item list is taller than the vertical space available
- **THEN** the navigation item list scrolls internally to reveal the remaining items, while the sidebar's logo/header and any footer content stay pinned in place

#### Scenario: Sidebar navigation list fits the viewport
- **WHEN** the sidebar's navigation item list fits within the space available
- **THEN** no scrollbar appears within the sidebar

#### Scenario: Sidebar scrollbar matches the dark theme
- **WHEN** the sidebar's navigation item list is scrolled or its scrollbar is otherwise visible
- **THEN** the scrollbar renders as a thin, flat control whose thumb and track colors fit the sidebar's dark background, instead of the browser's default light, bordered scrollbar

## ADDED Requirements

### Requirement: Sidebar collapses into a drawer below desktop width
Below 1024px viewport width, every staff, reception, and admin shell SHALL hide its sidebar and show a menu button at the start of the top bar. Activating the button SHALL slide the full sidebar in from the left as a drawer, at most 85% of the viewport width and never wider than its desktop width, over a dimmed backdrop. The drawer SHALL close when the user taps the backdrop, presses Escape, activates a close button inside the drawer, or navigates to another route. While the drawer is open, the content behind it SHALL NOT scroll, keyboard focus SHALL move into the drawer, and it SHALL return to the menu button on close. The menu button SHALL expose its expanded/collapsed state to assistive technology.

#### Scenario: Opening navigation on a phone
- **WHEN** a signed-in admin at 375px wide taps the menu button in the top bar
- **THEN** the admin sidebar slides in over the content with a backdrop, and every navigation item is reachable

#### Scenario: Navigating closes the drawer
- **WHEN** the drawer is open and the user taps a navigation item
- **THEN** the route changes and the drawer closes

#### Scenario: Resizing to desktop
- **WHEN** the viewport is widened from 800px to 1280px while the drawer is open
- **THEN** the drawer and backdrop disappear and the sidebar renders docked, as on desktop

### Requirement: Top bar compacts on small screens
Below 768px viewport width, the top bar SHALL keep the menu button, the page's breadcrumb or title, which truncates with an ellipsis, and the notification bell and user menu. It SHALL hide the page description text and the last-refreshed label, and the refresh control SHALL remain as an icon button. The top bar SHALL NOT wrap to more than one line.

#### Scenario: Top bar at phone width
- **WHEN** any staff or admin page is viewed at 360px wide
- **THEN** the top bar is a single row with the menu button, a truncated title, and the bell/user controls, and nothing overflows its right edge

### Requirement: The reception dashboard uses the shared responsive shell
The Reception Dashboard SHALL render inside the same shell as the other staff pages, so that it gets the same drawer navigation, fixed top bar, and content-only scrolling behavior. Its content, data, and role gate SHALL be unchanged.

#### Scenario: Reception dashboard on a tablet
- **WHEN** a reception user opens the Reception Dashboard at 768px wide
- **THEN** the reception sidebar is available through the top-bar menu button as a drawer, and the dashboard's KPI row and cards reflow to the tablet width
