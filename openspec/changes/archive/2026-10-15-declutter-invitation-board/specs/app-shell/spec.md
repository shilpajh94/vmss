## MODIFIED Requirements

### Requirement: Sidebar and top navigation remain fixed while content scrolls independently
The system SHALL render the top navigation bar in a fixed position that does not move when the page's main content is scrolled, and SHALL confine vertical scrolling caused by page content to the main content region only. At viewport widths of 1024px and wider, the sidebar SHALL likewise be permanently visible in a fixed position beside the content, either expanded or collapsed to an icon rail; see "Desktop sidebar can be collapsed to an icon rail". Below 1024px, the sidebar SHALL be hidden by default and SHALL open as an off-canvas drawer over the content, with a dimmed backdrop, from a menu button in the top bar; see "Sidebar collapses into a drawer below desktop width". Within the sidebar itself (docked or drawer), the logo/header area and any footer content SHALL remain pinned in place, and the navigation item list SHALL scroll independently when it is taller than the space available, so no navigation item becomes unreachable. Where the sidebar's navigation list scrolls, its scrollbar SHALL be styled to fit the sidebar's dark theme rather than rendered as the browser's unstyled default.

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

#### Scenario: Collapsed sidebar stays fixed too
- **WHEN** the desktop sidebar is collapsed to its icon rail and the user scrolls a long page
- **THEN** the icon rail stays visible and stationary beside the content, exactly as the expanded sidebar does

## ADDED Requirements

### Requirement: Desktop sidebar can be collapsed to an icon rail
At viewport widths of 1024px and wider, the Admin, Staff, and Reception sidebars SHALL each offer a collapse toggle in the sidebar header. Activating it SHALL collapse the sidebar to an icon rail no wider than 80px. The rail SHALL show the compact brand mark, every navigation item as its icon only, and any footer content in icon-only form. The content region SHALL widen to use the freed space. While collapsed, every navigation item SHALL remain operable and SHALL keep its current-page highlight. Each item SHALL expose its full label as its accessible name and SHALL show that label as a tooltip on hover and keyboard focus. Activating the toggle again SHALL restore the full sidebar. The toggle SHALL be labelled "Collapse sidebar" or "Expand sidebar" according to its state and SHALL expose its expanded/collapsed state to assistive technology.

The collapsed/expanded choice SHALL be remembered in the current browser across route changes, page reloads, and new sessions, and SHALL be shared by the admin and staff shells. When no choice has been stored, or stored preferences cannot be read, the sidebar SHALL start expanded. Below 1024px the toggle SHALL NOT be shown, and the off-canvas drawer SHALL always open with the full, expanded sidebar regardless of the stored choice.

#### Scenario: Collapsing the sidebar on the Invitations board
- **WHEN** a reception user at 1536px wide activates "Collapse sidebar" on the Invitations page
- **THEN** the sidebar shrinks to an icon rail showing the brand mark and the Dashboard, Invitations, and My actions icons, with Invitations highlighted, and the board widens into the freed space

#### Scenario: Navigating from the icon rail
- **WHEN** the sidebar is collapsed and an admin hovers over the Branches icon and then activates it
- **THEN** a "Branches" tooltip appears, the Branches page opens, and the sidebar stays collapsed

#### Scenario: Choice survives a reload
- **WHEN** a staff member collapses the sidebar and then reloads the page
- **THEN** the page renders with the sidebar already collapsed and no visible expand-then-collapse flicker

#### Scenario: Storage unavailable
- **WHEN** the browser blocks site storage and a user opens any staff or admin page at desktop width
- **THEN** the sidebar renders expanded and the collapse toggle still works for the current page view

#### Scenario: Drawer ignores the collapsed choice
- **WHEN** a user who collapsed the sidebar at 1440px narrows the window to 800px and opens the menu
- **THEN** the drawer shows the full sidebar with labels, and widening back to 1440px shows the icon rail again
