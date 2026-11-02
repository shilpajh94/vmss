## ADDED Requirements

### Requirement: Paged List Pagination Stays Visible Below the Data
On every paged staff or admin list page (a table with a
`Showing A-B of N` footer and Previous/Next controls), from `lg` (1024px)
up:
- the pagination footer SHALL sit directly below the scrolling data
  region, outside it;
- the footer SHALL stay visible without scrolling, whatever the number
  of rows;
- only the rows SHALL scroll;
- when the rows are scrolled to the end, the last row and the data
  container's bottom edge SHALL sit fully above the footer;
- the page itself SHALL NOT scroll vertically because of the rows.

Below `lg`, the whole page SHALL scroll as one, and the pagination footer
SHALL follow the last row.

While the list is loading for the first time, has failed, or is empty,
the footer SHALL NOT be shown.

#### Scenario: Full page of rows on a laptop screen
- **WHEN** the employees list shows 20 rows at 1280×720
- **THEN** the `Showing 1-20 of N` text and the Previous/Next buttons
  are fully inside the window without scrolling, and the page itself
  does not scroll

#### Scenario: Scrolling the rows keeps the footer in place
- **WHEN** the user scrolls the rows of a paged list to the end at
  1440×900
- **THEN** the pagination footer stays in the same position and the last
  row ends above it

#### Scenario: Short list
- **WHEN** a paged list has three rows at 1440×900
- **THEN** the pagination footer is directly below the third row, not
  pushed to the bottom of the window

#### Scenario: Phone width
- **WHEN** a paged list with 20 rows is viewed at 390px wide
- **THEN** the page scrolls as a whole and the pagination footer follows
  the last row

#### Scenario: Workflows list
- **WHEN** the approval workflows list shows a full page at 1280×720
- **THEN** its `Showing A-B of N workflows` footer and Previous/Next
  buttons are visible without scrolling
