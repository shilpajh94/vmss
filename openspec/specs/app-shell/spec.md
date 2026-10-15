# app-shell Specification

## Purpose

The app-shell capability is the bootstrapped application surface: the routed shell that renders on load, the dependency-injection contract pages use to reach use cases, and the base HTTP client contract every future feature builds on.

## Requirements

### Requirement: Application renders a routed shell on load
The system SHALL render a root layout at the application's base route when loaded in a browser, with no unhandled errors.

#### Scenario: App loads at root route
- **WHEN** a user navigates to the application's base URL
- **THEN** the visitor portal landing page renders inside the root layout

### Requirement: Dependencies are available to presentation only through a provider
The system SHALL expose application dependencies (use cases) to React components exclusively through a dependency-injection provider and its accompanying hook.

#### Scenario: Component reads dependencies via hook
- **WHEN** a page component calls the dependencies hook
- **THEN** it receives the dependencies object without importing infrastructure or composition-root code directly

#### Scenario: Hook used outside provider
- **WHEN** the dependencies hook is called from a component not wrapped by the provider
- **THEN** the system throws a descriptive error instead of returning undefined

### Requirement: HTTP client enforces token presence for authenticated endpoints
The system SHALL refuse to send a request to an endpoint marked as requiring a token when no token is present, without making a network call.

#### Scenario: Authenticated endpoint called without a stored token
- **WHEN** a request is made to an endpoint configured with `hasToken: true` and no token exists in session storage
- **THEN** the system throws an error before issuing the network request

#### Scenario: Authenticated endpoint called with a stored token
- **WHEN** a request is made to an endpoint configured with `hasToken: true` and a token exists in session storage
- **THEN** the system attaches the token as an `Authorization: Bearer` header on the outgoing request

### Requirement: HTTP client validates response shape
The system SHALL validate every successful HTTP response against a schema before returning data to the caller.

#### Scenario: Response matches expected shape
- **WHEN** a request succeeds and the response body matches the provided schema
- **THEN** the caller receives the parsed, validated data

#### Scenario: Response does not match expected shape
- **WHEN** a request succeeds but the response body does not match the provided schema
- **THEN** the system raises a validation error instead of returning unvalidated data

### Requirement: API base URL is configured from environment
The system SHALL derive the API base URL from the `VITE_API_BASE_URL` environment variable at startup, with no trailing slash.

#### Scenario: Base URL is read at composition time
- **WHEN** the application composition root resolves the HTTP client
- **THEN** it uses the value of `VITE_API_BASE_URL` with any trailing slash removed

### Requirement: An expired or invalid session is handled gracefully, not as a generic error
The system SHALL, when a request to an authenticated endpoint receives a 401 or 403 response, clear the stored session token instead of attempting to parse the response body as a successful result, and SHALL, from anywhere in the app, show the user a message indicating their session has expired and redirect them to the appropriate sign-in page (`/admin/login` or `/staff/login`), rather than surfacing a generic or technical error message.

#### Scenario: Authenticated request receives a 401 or 403
- **WHEN** any request to an endpoint configured with `hasToken: true` receives a 401 or 403 response
- **THEN** the system clears the stored session token and does not treat the response body as valid data

#### Scenario: User is redirected with a clear message
- **WHEN** the system detects a 401 or 403 on an authenticated request
- **THEN** the user sees a message indicating their session has expired and is redirected to the sign-in page appropriate to the area of the app they were in

#### Scenario: Redirect works regardless of which page triggered the expiry
- **WHEN** the 401 or 403 occurs on a request made from any authenticated admin or staff page, not only the page that first loaded the token
- **THEN** the same session-expired message and redirect occur without requiring that page's own code to detect it individually

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

### Requirement: No page triggers horizontal scrolling of the overall page
The system SHALL prevent any page's content from causing the outer page (document body/viewport) to scroll horizontally. Content that is intrinsically wider than the viewport (for example, a data table with many columns) SHALL scroll within its own contained region instead of widening the page.

#### Scenario: A wide table is rendered
- **WHEN** a page renders a table or other content wider than the viewport
- **THEN** that content scrolls horizontally within its own container and the outer page does not gain a horizontal scrollbar

#### Scenario: Normal page content
- **WHEN** a page's content fits within the viewport width
- **THEN** no horizontal scrollbar appears anywhere on the page

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
