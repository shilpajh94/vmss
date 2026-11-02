## ADDED Requirements

### Requirement: Day view scrolls its timeline inside its own panel
From `lg` (1024px) up, Day view SHALL fill the page height below the
toolbar, as Week view does. It SHALL do so without the page scrolling
vertically because of the visits. The page title, the subtitle and the
toolbar (date navigation, branch selector, view switcher and status
filters) SHALL stay in place, and only the day's timeline SHALL scroll,
inside the Day card.

The Day card SHALL have:
- a fixed header row that shows the day's date and its visit count;
- a scrolling body with the timeline and its sticky hour headings;
- a fixed footer row with the day's paging status (see "Each day's
  paging status stays visible").

The next page of visits SHALL load when the card's body is scrolled near
the last loaded visit. A refresh SHALL NOT move the card's scroll
position.

Below `lg`, Day view SHALL keep scrolling with the page.

#### Scenario: Busy day on a desktop
- **WHEN** Day view shows a day with 40 visits at 1440×900
- **THEN** the page does not scroll, the toolbar stays visible, and the
  visits scroll inside the Day card

#### Scenario: Header and footer stay put
- **WHEN** the user scrolls the Day card's body to its end
- **THEN** the card's header row (date and count) and footer row stay in
  the same place

#### Scenario: Loading more from the panel
- **WHEN** the day has more visits than the first page and the user
  scrolls the Day card's body near the last loaded visit
- **THEN** the next page loads and is added below without the scroll
  position jumping

#### Scenario: Quiet day
- **WHEN** Day view shows a day with no visits at 1440×900
- **THEN** the card shows "No visits" and the working-hours headings
  inside its body, and the page does not scroll

#### Scenario: Phone width
- **WHEN** Day view shows a busy day at 390px wide
- **THEN** the page scrolls as a whole, as before

### Requirement: Each day's paging status stays visible
A day's paging status SHALL be shown in a fixed footer at the bottom of
its scrolling area, outside the list:
- in Week view, at the bottom of each day column, at every width (the
  columns always scroll on their own);
- in Day view from `lg` up, at the bottom of the Day card.

The footer shows:
- `Showing X of Y` while more visits remain;
- `All N visits` once all are loaded;
- a Retry button after a failed load.

The loading row inside the list, right after the last loaded visit,
SHALL remain. It marks where loading continues, and it shows
"Loading more…" while a page loads.

The footer SHALL be visible without scrolling the list. On an empty day,
it SHALL NOT be shown. Below `lg`, Day view's status SHALL follow the
last loaded visit, since the page scrolls as a whole.

#### Scenario: Partly loaded column
- **WHEN** a Week column has loaded 10 of 51 visits
- **THEN** `Showing 10 of 51` is visible at the bottom of the column
  without scrolling it

#### Scenario: Fully loaded day
- **WHEN** every visit of a 6-visit day is loaded in Day view
- **THEN** the Day card's footer reads `All 6 visits`

#### Scenario: Failed page
- **WHEN** loading the next page of a column fails
- **THEN** the column footer shows a Retry button, and pressing it loads
  that page again

#### Scenario: Empty day
- **WHEN** a Week column has no visits
- **THEN** it shows "No visits" in its body and no paging footer

### Requirement: Week board fits short desktop windows
From `lg` up, the Week board SHALL end at the page's bottom gap, with
every column's footer inside the window, whenever at least 240px is
left below the toolbar. It SHALL do so without the page scrolling
vertically.

When less than 240px is left, the board SHALL keep a 240px height. The
page SHALL then scroll, keeping its bottom gap after the board, so the
board's bottom edge and its column footers can be reached.

#### Scenario: Laptop window
- **WHEN** Week view is shown at 1280×720
- **THEN** the board's bottom edge and every visible column's footer
  are inside the window, and the page does not scroll

#### Scenario: Large window
- **WHEN** Week view is shown at 1920×1080
- **THEN** the board ends at the page's bottom gap and the page does not
  scroll

#### Scenario: Very short window
- **WHEN** Week view is shown at a window height that leaves less than
  240px below the toolbar
- **THEN** the board is 240px tall, the page scrolls, and after scrolling
  to the end the board's bottom edge is followed by the page's bottom gap
