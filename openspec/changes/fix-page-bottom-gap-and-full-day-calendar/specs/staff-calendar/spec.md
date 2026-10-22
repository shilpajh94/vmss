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
- Each column SHALL lay out the full day as a timeline (see "Full-day
  timeline" below).
- The column header SHALL show the day's exact total.
- Each column SHALL show the day's first visits at once: at least 10, or
  all of them when there are fewer.
- Scrolling near the last loaded visit of a column SHALL load the next 10
  visits of that day, without affecting the other columns.
- While a page loads, the column SHALL show a loading row.
- When every visit is loaded, the column SHALL stop loading.
- A footer SHALL show how many of the day's total are loaded, for example
  "Showing 30 of 181".

**Day** SHALL list that day's visits on the same full-day timeline, with
full event details.
- It SHALL load the first 20 at once.
- It SHALL load the next 20 as the user scrolls near the last loaded
  visit, until all are shown.

**Full-day timeline** (Week columns and Day view):
- The timeline SHALL show one heading for every hour of the day, in
  order, from 12:00 AM to 11:00 PM (24 headings), whether or not that
  hour has visits.
- Each visit SHALL appear under the heading of the hour it is scheduled
  in. Visits with no scheduled time SHALL appear in an "Any time" group
  after 11:00 PM.
- An hour with no visits SHALL take only the height of its heading, so a
  quiet day stays short.
- Hour headings SHALL stay pinned to the top of the scroll area while
  their visits scroll beneath them.
- While some of the day's visits are not loaded yet, hours after the last
  loaded visit SHALL still show their headings. They SHALL NOT be marked
  as having no visits, and the "Any time" group SHALL NOT be shown until
  its visits load.
- A day with no visits SHALL show "No visits" above its timeline.
- When a week column or the day list first opens (a new week, day,
  branch or status filter), it SHALL scroll so that the first hour with
  visits is at the top. A day with no timed visits SHALL open at
  12:00 AM.
- Loading more visits or a refresh SHALL NOT change the scroll position.

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
- **THEN** it appears under the "Any time" heading after 11:00 PM in Week
  and Day views

#### Scenario: Reload keeps the view
- **WHEN** the user reloads `/staff/calendar?view=week&date=2026-10-19`
- **THEN** the week of Monday 2026-10-19 is shown in Week view

#### Scenario: Today follows the tenant timezone
- **WHEN** the browser's local date differs from the tenant-local date
- **THEN** the highlighted "today" is the tenant-local date

#### Scenario: Every hour of the day is shown
- **WHEN** a day has visits only at 10:00 AM and 2:00 PM, and all of them
  are loaded
- **THEN** its column shows 24 hour headings from 12:00 AM to 11:00 PM,
  with the visits under "10:00 AM" and "2:00 PM" and the other 22 hours
  as headings only

#### Scenario: Late and early invitations
- **WHEN** a day has a visit at 12:30 AM and one at 11:15 PM
- **THEN** the first appears under "12:00 AM" and the second under
  "11:00 PM"

#### Scenario: Column opens at the first busy hour
- **WHEN** Week view opens and Tuesday's earliest visit is at 9:00 AM
- **THEN** Tuesday's column is scrolled so "9:00 AM" is at its top, and
  scrolling up reveals 12:00 AM to 8:00 AM

#### Scenario: Empty day
- **WHEN** Wednesday has no visits
- **THEN** Wednesday's column shows "No visits" and the 24 hour headings,
  starting at 12:00 AM

#### Scenario: Busy day scrolls inside its column
- **WHEN** Monday has 181 visits and Tuesday has 6, and Week view opens
- **THEN** the page height does not grow with Monday's visits
- **AND** Monday's column shows its first 10 visits and "Showing 10 of 181"
- **AND** Tuesday shows all 6 without a loading row

#### Scenario: Unloaded hours are not shown as empty
- **WHEN** Monday has 181 visits at 10:00 AM and 5 at 3:00 PM, and only
  the first 10 are loaded
- **THEN** the "11:00 AM" to "11:00 PM" headings are shown, no hour after
  10:00 AM is marked as having no visits, and the 3:00 PM visits appear
  under "3:00 PM" once loading reaches them

#### Scenario: Scrolling a column loads more
- **WHEN** the user scrolls Monday's column to near its last loaded visit
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
