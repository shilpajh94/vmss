## ADDED Requirements

### Requirement: Page content keeps a bottom gap
Every staff and admin page SHALL leave a gap below its last element equal
to the page's own content padding at that width: 16px below 768px, 24px
from 768px and 32px from 1024px.

- When the page is taller than the content region and scrolls, the gap
  SHALL appear after the last element once the region is scrolled to the
  end. The last element SHALL NOT touch the region's bottom edge.
- A layout that fills the content region's height (a fixed header with a
  scrolling data region, or the calendar week board) SHALL end the same
  gap above the region's bottom edge. It SHALL NOT make the content
  region scroll, so the page heading stays in view.

This SHALL hold at every supported device width, in both themes.

#### Scenario: Long page scrolled to the end
- **WHEN** a page taller than the screen is scrolled to the bottom at
  1440px
- **THEN** there is 32px of empty space between the last card's bottom
  edge and the bottom of the content region

#### Scenario: Long page on a phone
- **WHEN** the same page is scrolled to the bottom at 390px
- **THEN** there is 16px of empty space below the last card

#### Scenario: Calendar week board fits without scrolling the page
- **WHEN** `/staff/calendar?view=week` is open at 1920×1080 with a day of
  181 visits
- **THEN** the week board ends 32px above the bottom of the content
  region, the content region itself does not scroll, and the "Calendar"
  heading is fully visible

#### Scenario: Fixed-header list page
- **WHEN** a page with a fixed heading and a scrolling data region is
  open at 1280px
- **THEN** the data region ends 32px above the bottom of the content
  region and the content region itself does not scroll

#### Scenario: Device matrix checks the bottom gap
- **WHEN** every staff and admin route is opened at each supported width
  in both themes and its content region is scrolled to the end
- **THEN** none shows its last element closer to the bottom edge than the
  page padding for that width
