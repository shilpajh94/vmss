## MODIFIED Requirements

### Requirement: Route navigation is accompanied by a transition animation
The system SHALL play a brief visual transition when the user navigates
from one route to another, instead of replacing the page's content
instantly. Where a route belongs to a section with a shared sidebar (and,
for the admin section, a shared top bar), that transition SHALL be scoped
to the main content region only. The sidebar and top bar SHALL remain
mounted and SHALL NOT re-render or take part in the transition when
navigating between routes in the same section. The incoming page SHALL
render its final layout from the first frame of the transition, using
skeleton placeholders for any data still loading, so that its heading,
controls, and content regions do not change size or position after the
transition ends. On every route change, the main content region SHALL
start scrolled to the top.

#### Scenario: Navigating between two pages
- **WHEN** a user navigates from one route to another within the app
- **THEN** the outgoing view's content transitions out and the incoming
  view's content transitions in, rather than one instantly replacing the
  other

#### Scenario: Reduced motion is requested
- **WHEN** the user's operating system or browser is set to prefer reduced
  motion
- **THEN** the system skips or minimizes the transition instead of playing
  it in full

#### Scenario: Navigating within the admin section
- **WHEN** an authenticated admin user navigates from one admin page to
  another (e.g. from the branches list to the departments list)
- **THEN** the sidebar and top bar remain the same, unchanged elements on
  screen — they do not unmount, flash, or reset — and only the main content
  region plays the transition and shows the new page's content

#### Scenario: Navigating within the staff section
- **WHEN** a staff user navigates from one staff page to another (e.g. from
  the dashboard to the audit trail)
- **THEN** the sidebar remains the same, unchanged element on screen — it
  does not unmount, flash, or reset — while the rest of the page (including
  that page's own header) transitions in as content

#### Scenario: Incoming page does not jump after it enters
- **WHEN** a user navigates to a data-driven page whose data has not loaded
  yet
- **THEN** the page enters showing its heading, controls, and skeleton
  placeholders in their final positions, and when the data arrives only the
  placeholders change; nothing above or around them moves

#### Scenario: Scroll position resets on navigation
- **WHEN** a user scrolls far down one page and then navigates to another
- **THEN** the new page's content region starts at the top

## ADDED Requirements

### Requirement: Content does not shift sideways when a scrollbar appears
The system SHALL reserve space for the main content region's vertical
scrollbar, so that page content does not move horizontally when that region
becomes scrollable or stops being scrollable. This happens, for example,
when a filter shrinks a long page or a re-fetch grows it. A page's inner
data region that scrolls beneath a fixed heading row SHALL NOT reserve its
own scrollbar gutter, because the reserved strip would leave the data
narrower than the heading and filter row above it.

#### Scenario: Filter shrinks a long page
- **WHEN** a page long enough to scroll its main content region is filtered
  down to a few rows, so that region no longer needs a scrollbar
- **THEN** the page heading and the content keep their horizontal positions

#### Scenario: Data region stays aligned with its heading row
- **WHEN** a list page's data region scrolls beneath its fixed heading,
  Filters, and Add row on a system with always-visible scrollbars
- **THEN** the table's left and right edges line up with the heading row
  and filter panel above it
