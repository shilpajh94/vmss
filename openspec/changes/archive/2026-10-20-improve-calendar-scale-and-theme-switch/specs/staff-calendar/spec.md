## MODIFIED Requirements

### Requirement: Month, week and day views with date navigation
The page SHALL offer Month, Week and Day views and Previous, Next and Today
controls. The selected view and anchor date SHALL be kept in the URL query
(`view`, `date`), so a reload or shared link reopens the same view.
Week views SHALL start on Monday.

**Month** SHALL show a six-week grid.
- It SHALL request at most 3 visits per day.
- Each day cell SHALL show its exact total from the response, up to 3
  event chips, and a "+N more" control that opens that day in Day view.

**Week** SHALL show seven day columns inside a board sized to the
viewport.
- The page itself SHALL NOT grow with the number of visits.
- Each column SHALL scroll vertically on its own.
- Visits SHALL be grouped under sticky headings for "Any time" and each
  scheduled hour.
- The column header SHALL show the day's exact total.
- Each column SHALL show the day's first visits at once: at least 10, or
  all of them when there are fewer.
- Scrolling near the end of a column SHALL load the next 10 visits of that
  day, without affecting the other columns.
- While a page loads, the column SHALL show a loading row.
- When every visit is loaded, the column SHALL stop loading.
- A footer SHALL show how many of the day's total are loaded, for example
  "Showing 30 of 181".

**Day** SHALL list that day's visits in an "Any time" group and hour
groups, with full event details.
- It SHALL load the first 20 at once.
- It SHALL load the next 20 as the user scrolls near the end of the list,
  until all are shown.

Loaded visits SHALL appear in the standard event order, with no visit shown
twice.

An automatic or manual refresh SHALL update the loaded visits and totals
without collapsing a column back to its first page and without resetting
its scroll position.

"Today" SHALL be the tenant-local date implied by the response's timezone,
not the browser's date. It SHALL be visibly highlighted.

#### Scenario: Navigating months
- **WHEN** the user is in Month view for October 2026 and clicks Next
- **THEN** November 2026 is shown, the URL updates to the new date, and the
  feed is requested for November's six-week grid

#### Scenario: Day overflow opens Day view
- **WHEN** a month cell has more events than fit and the user clicks
  "+N more"
- **THEN** Day view opens for that date and its visits load page by page
  as the user scrolls

#### Scenario: Visit with no scheduled time
- **WHEN** an event has no scheduled time
- **THEN** it appears under the "Any time" heading in Week and Day views

#### Scenario: Reload keeps the view
- **WHEN** the user reloads `/staff/calendar?view=week&date=2026-10-19`
- **THEN** the week of Monday 2026-10-19 is shown in Week view

#### Scenario: Today follows the tenant timezone
- **WHEN** the browser's local date differs from the tenant-local date
- **THEN** the highlighted "today" is the tenant-local date

#### Scenario: Busy day scrolls inside its column
- **WHEN** Monday has 181 visits and Tuesday has 6, and Week view opens
- **THEN** the page height does not grow with Monday's visits
- **AND** Monday's column shows its first 10 visits and "Showing 10 of 181"
- **AND** Tuesday shows all 6 without a loading row

#### Scenario: Scrolling a column loads more
- **WHEN** the user scrolls Monday's column to near its end
- **THEN** visits 11–20 are appended to Monday's column only, and the
  footer reads "Showing 20 of 181"

#### Scenario: Whole day reachable
- **WHEN** the user keeps scrolling Monday's column
- **THEN** all 181 visits are eventually shown, each exactly once, and
  loading stops

#### Scenario: Refresh keeps loaded visits
- **WHEN** 40 of Monday's visits are loaded and an automatic refresh runs
- **THEN** Monday's column still shows 40 visits at the same scroll
  position, updated to their latest status

### Requirement: Status filter, truncation and empty states
The page SHALL provide a status filter. By default it SHALL show every
status except Denied. Changing it SHALL refetch with the chosen statuses and
SHALL reset every column and the day list to their first page.

No view SHALL drop visits: every visit of every day SHALL be reachable by
scrolling a week column or the day list. The page SHALL NOT show a "not
every visit is listed" banner.

A range with no events SHALL show an empty-state message rather than a
blank grid area. A day column with no visits SHALL show "No visits". A
failed request SHALL show the standard error state with a retry action. A
failed "load more" SHALL show a retry control inside that column or list
only.

#### Scenario: Showing denied visits
- **WHEN** the user adds "Denied" in the status filter
- **THEN** the feed is refetched including denied invitations, and they are
  shown with the "Denied" label

#### Scenario: Truncated month
- **WHEN** a month has days with more visits than a month cell shows
- **THEN** no "not every visit is listed" banner appears, and each month
  cell's count still equals that day's `total`, with "+N more" opening the
  full, paged day

#### Scenario: Empty week
- **WHEN** the week has no visits
- **THEN** the week board shows an empty-state message

#### Scenario: Load-more failure is local
- **WHEN** loading the next page of Monday's column fails
- **THEN** Monday's column shows a retry control, and the other columns
  and the toolbar keep working

### Requirement: Calendar is usable on small screens
Below desktop width, the page SHALL default to Day view and keep Month and
Week available. It SHALL NOT cause horizontal page scrolling.

In Week view, the day columns SHALL scroll sideways inside the board with
snap points:
- one column per screen below 640px;
- two from 640px;
- three from 768px;
- all seven from 1280px.

Each column SHALL keep its own vertical scroll and lazy loading. The board
SHALL fill the space below the toolbar without the page scrolling
vertically on account of the visits.

#### Scenario: Phone width
- **WHEN** the calendar opens at a 390px-wide viewport without a `view`
  query parameter
- **THEN** Day view is shown and the page has no horizontal scrollbar

#### Scenario: Week on a phone
- **WHEN** Week view is shown at 390px
- **THEN** one day column fills the board width, swiping sideways snaps to
  the next day, and the page has no horizontal scrollbar

#### Scenario: Week on a tablet
- **WHEN** Week view is shown at 820px
- **THEN** three day columns are visible side by side, and the rest are
  reachable by scrolling the board sideways
