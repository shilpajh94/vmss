## MODIFIED Requirements

### Requirement: Events show schedule, status and visitor at a glance
Each event SHALL show:
- its scheduled time (or "Any time");
- the primary contact's name, plus "+N" when there are co-visitors;
- a status colour: Pending (submitted), Expected (approved), Inside
  (checked in), Visited (checked out), Missed (archived), Denied (denied);
- a visitor-category colour accent.

Every event, in Month, Week and Day views, SHALL be drawn filled with its
status colour: a tinted background with text in that status colour. The
colours SHALL be:

| Status | Colour |
|---|---|
| Pending | info |
| Expected | success |
| Inside | secondary accent |
| Visited | neutral |
| Missed | warning |
| Denied | danger |

The visitor-category colour SHALL remain visible as a solid left accent on
each event. A plain white or uncoloured event row SHALL NOT be used.

The status filter chips SHALL use the same fills, so they also act as the
colour legend.

In Week view, each event SHALL take at most two lines:
- the visitor name;
- the scheduled time, followed by the host for `branch` scope.

A status dot SHALL lead the second line.

In Month view, each day's visit count SHALL be shown with a tint whose
strength steps up with the day's total:
- none at 0;
- light at 1–4;
- medium at 5–14;
- strong at 15 or more.

Busier days are therefore distinguishable at a glance, on phones as well.

Day view and the event's hover or focus detail SHALL also show the
purpose, the actual check-in and check-out times when present (in the
tenant timezone), and, for `branch` scope, the host name ("Unassigned" when
null) and the branch.

Status SHALL be conveyed by text as well as colour: a visible label in Day
view, and in every view the hover detail and the accessible name. Event
text SHALL meet 4.5:1 contrast against its fill in both the light and
dark themes.

#### Scenario: Checked-in visitor
- **WHEN** an event has status `checked_in` with a check-in time of 10:42
- **THEN** Day view shows "Inside" and "Checked in 10:42", and in Week
  view its accessible name and hover detail include "Inside"

#### Scenario: Group visit
- **WHEN** an event has a visitor count of 4
- **THEN** it shows the primary contact name followed by "+3"

#### Scenario: Two-line week card
- **WHEN** a reception user views a pending 10:30 AM visit with no host in
  Week view
- **THEN** its card shows the visitor name on the first line and a status
  dot, "10:30 AM · Unassigned" on the second, with no third line and no
  visible "Pending" text

#### Scenario: Month cell shows status fills
- **WHEN** a month cell contains one pending, one missed and one checked-out
  visit
- **THEN** the three events are filled blue, amber and grey respectively,
  each with its category accent on the left

#### Scenario: Filter chips double as the legend
- **WHEN** the calendar toolbar is shown
- **THEN** each enabled status chip is filled with the same colour its
  events use

#### Scenario: Busy day stands out
- **WHEN** one day has 20 visits and the next has 2
- **THEN** the first day's count shows the strong tint and the second shows
  the light tint

#### Scenario: Readable in dark mode
- **WHEN** the dark theme is active
- **THEN** every status-filled event's text meets 4.5:1 contrast against
  its fill

### Requirement: Calendar is usable on small screens
Below desktop width, the page SHALL default to Day view and keep Month and
Week available. It SHALL NOT cause horizontal page scrolling.

In Week view, the day columns SHALL scroll sideways inside the board with
snap points:
- one column per screen below 640px;
- two from 640px;
- three from 768px;
- five from 1280px;
- all seven from 1536px.

When fewer than seven columns fit and the shown week contains today, the
board SHALL open scrolled so today's column is visible. It SHALL be the
first visible column, unless the week's end makes that impossible.
Otherwise the board SHALL open at Monday.

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

#### Scenario: Week on a laptop
- **WHEN** Week view of the current week is shown at 1440px and today is
  Tuesday
- **THEN** five day columns are visible, starting with Tuesday, and Monday
  is reachable by scrolling the board sideways

#### Scenario: Week on a wide screen
- **WHEN** Week view is shown at 1920px
- **THEN** all seven day columns are visible without sideways scrolling

## ADDED Requirements

### Requirement: Month, week and day views with a working-hours timeline
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
- Each column SHALL lay out its day as a working-hours timeline (see
  "Working-hours timeline" below).
- The column header SHALL show the day's exact total.
- Each column SHALL show the day's first visits at once: at least 10, or
  all of them when there are fewer.
- Scrolling near the last loaded visit of a column SHALL load the next 10
  visits of that day, without affecting the other columns.
- While a page loads, the column SHALL show a loading row.
- When every visit is loaded, the column SHALL stop loading.
- A footer SHALL show how many of the day's total are loaded, for example
  "Showing 30 of 181".

**Day** SHALL list that day's visits on the same working-hours timeline,
with full event details.
- It SHALL load the first 20 at once.
- It SHALL load the next 20 as the user scrolls near the last loaded
  visit, until all are shown.

**Working-hours timeline** (Week columns and Day view):
- The timeline SHALL always show one heading for each hour from 9:00 AM
  to 6:00 PM, in order (10 headings), whether or not that hour has
  visits.
- An hour before 9:00 AM or after 6:00 PM SHALL be shown only when it
  has at least one loaded visit, in its place in the hour order.
- Each visit SHALL appear under the heading of the hour it is scheduled
  in. Visits with no scheduled time SHALL appear in an "Any time" group
  after the last hour shown.
- An hour with no visits SHALL take only the height of its heading.
- Hour headings SHALL stay pinned to the top of the scroll area while
  their visits scroll beneath them.
- While some of the day's visits are not loaded yet, working hours after
  the last loaded visit SHALL still show their headings. They SHALL NOT be
  marked as having no visits. Later out-of-hours visits and the "Any time"
  group SHALL appear when they load.
- A day with no visits SHALL show "No visits" above its timeline.
- A week column or the day list SHALL open at its top. Loading more visits
  or a refresh SHALL NOT change the scroll position.

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
- **THEN** it appears under the "Any time" heading after the last hour
  shown, in Week and Day views

#### Scenario: Reload keeps the view
- **WHEN** the user reloads `/staff/calendar?view=week&date=2026-10-19`
- **THEN** the week of Monday 2026-10-19 is shown in Week view

#### Scenario: Today follows the tenant timezone
- **WHEN** the browser's local date differs from the tenant-local date
- **THEN** the highlighted "today" is the tenant-local date

#### Scenario: Working hours are always shown
- **WHEN** a day has visits only at 10:00 AM and 2:00 PM, and all of them
  are loaded
- **THEN** its column shows exactly 10 hour headings, from 9:00 AM to
  6:00 PM, with the visits under "10:00 AM" and "2:00 PM"

#### Scenario: Late and early invitations
- **WHEN** a day has a visit at 12:30 AM, one at 11:00 AM and one at
  11:15 PM
- **THEN** its column shows "12:00 AM", then 9:00 AM to 6:00 PM, then
  "11:00 PM", with each visit under its hour, and no other hour headings

#### Scenario: Empty day
- **WHEN** Wednesday has no visits
- **THEN** Wednesday's column shows "No visits" and the headings from
  9:00 AM to 6:00 PM

#### Scenario: Column opens at its top
- **WHEN** Week view opens and Tuesday's earliest visit is at 2:00 PM
- **THEN** Tuesday's column is scrolled to its top, with "9:00 AM" as the
  first heading

#### Scenario: Busy day scrolls inside its column
- **WHEN** Monday has 181 visits and Tuesday has 6, and Week view opens
- **THEN** the page height does not grow with Monday's visits
- **AND** Monday's column shows its first 10 visits and "Showing 10 of 181"
- **AND** Tuesday shows all 6 without a loading row

#### Scenario: Unloaded hours are not shown as empty
- **WHEN** Monday has 181 visits at 10:00 AM and 5 at 3:00 PM, and only
  the first 10 are loaded
- **THEN** the "11:00 AM" to "6:00 PM" headings are shown below the
  progress row, none is marked as having no visits, and the 3:00 PM
  visits appear under "3:00 PM" once loading reaches them

#### Scenario: Late visit appears once loaded
- **WHEN** a day's only out-of-hours visit is at 8:00 PM and it is not
  loaded yet
- **THEN** no "8:00 PM" heading is shown until that visit loads, and
  then it appears after "6:00 PM"

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

## REMOVED Requirements

### Requirement: Month, week and day views with date navigation
**Reason**: Replaced by "Month, week and day views with a working-hours
timeline". The full 12:00 AM–11:00 PM timeline left most of each column
to empty night hours, and opening at the first busy hour is no longer
needed once the day starts at 9:00 AM.
**Migration**: Everything else in the old requirement carries over
unchanged into the new one: views, navigation, paging, refresh and today.
The timeline shows 9:00 AM–6:00 PM always, other hours only when they
have visits, and columns open at their top.
