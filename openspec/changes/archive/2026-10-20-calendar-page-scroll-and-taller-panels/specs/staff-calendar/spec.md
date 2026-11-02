## MODIFIED Requirements

### Requirement: Day view scrolls its timeline inside its own panel
From `lg` (1024px) up, the Day card SHALL be as tall as the visible page
area (see "Week board and Day card are as tall as the visible page"), and
only the day's timeline SHALL scroll inside it. The page SHALL scroll to
bring the whole card into view. The page title, subtitle and toolbar
scroll away with the page and come back when the page is scrolled to
the top.

The Day card SHALL have:
- a fixed header row that shows the day's date and its visit count;
- a scrolling body with the timeline and its sticky hour headings;
- a fixed footer row with the day's paging status (see "Each day's
  paging status stays visible").

The next page of visits SHALL load when the card's body is scrolled near
the last loaded visit. A refresh SHALL NOT move the card's scroll
position or the page's scroll position.

Below `lg`, Day view SHALL keep growing with its content and scrolling
with the page.

#### Scenario: Busy day on a desktop
- **WHEN** Day view shows a day with 40 visits at 1440×900
- **THEN** the Day card is as tall as the visible page area, the visits
  scroll inside the card, and the page can be scrolled until the card
  fills the visible area

#### Scenario: Header and footer stay put
- **WHEN** the user scrolls the Day card's body to its end
- **THEN** the card's header row (date and count) and footer row stay in
  the same place within the card

#### Scenario: Loading more from the panel
- **WHEN** the day has more visits than the first page and the user
  scrolls the Day card's body near the last loaded visit
- **THEN** the next page loads and is added below without the scroll
  position jumping

#### Scenario: Toolbar comes back
- **WHEN** the page has been scrolled so the card fills the visible area
  and the user scrolls the page back to the top
- **THEN** the page title and toolbar are fully visible again above the
  card

#### Scenario: Phone width
- **WHEN** Day view shows a busy day at 390px wide
- **THEN** the page scrolls as a whole, as before

## REMOVED Requirements

### Requirement: Week board fits short desktop windows
**Reason**: Fitting the board under the toolbar without page scroll left
it about 360px tall on a 720px window, which staff found cramped. The
page now scrolls, and the board is as tall as the visible page.
**Migration**: Replaced by "Week board and Day card are as tall as the
visible page".

## ADDED Requirements

### Requirement: Week board and Day card are as tall as the visible page
The Week board (at every width) and the Day card (from `lg` up) SHALL be
as tall as the visible page area: the height of the scrolling page
region under the top bar, less the page's top padding and its bottom
gap. They SHALL NOT be shorter than 420px. Their height SHALL follow
window resizes and rotation. It SHALL NOT depend on the height of the
title and toolbar above them.

The page SHALL scroll vertically by the height of the content above the
panel, and the page's bottom gap SHALL follow the panel when the page is
scrolled to the end.

A day column body and the Day card body SHALL hand vertical scrolling over
to the page: when a body is at its top or bottom, a further scroll in that
direction SHALL scroll the page. Sideways scrolling of the Week board
SHALL NOT be handed over to the page or the browser.

#### Scenario: Laptop window
- **WHEN** Week view is shown at 1280×720
- **THEN** the board is as tall as the visible page area (about 590px,
  not about 360px), and scrolling the page to the end shows the whole
  board with the bottom gap below it

#### Scenario: Large window
- **WHEN** Week view is shown at 1920×1080
- **THEN** the board is as tall as the visible page area, and the page
  scrolls by the height of the title and toolbar

#### Scenario: Short window
- **WHEN** the visible page area is less than 420px tall
- **THEN** the board is 420px tall and the page scrolls to reach its
  bottom edge and the bottom gap

#### Scenario: Scrolling past the end of a column
- **WHEN** the page is at its top, a Week column is scrolled to its end,
  and the user scrolls down again over that column
- **THEN** the page scrolls down

#### Scenario: Scrolling back up over the panel
- **WHEN** the page is scrolled to its end, the Day card's body is at its
  top, and the user scrolls up over the card
- **THEN** the page scrolls up and the toolbar comes back into view

#### Scenario: Toolbar wraps
- **WHEN** the branch selector appears or the sidebar collapses and the
  toolbar becomes taller or shorter
- **THEN** the board's height stays the same and only the page's scroll
  length changes
