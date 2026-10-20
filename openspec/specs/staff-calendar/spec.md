# staff-calendar Specification

## Purpose

A calendar page in the staff and admin portals that lays out visits and
invitations by date. Each signed-in user sees exactly the visits their role
entitles them to, as decided by the API's calendar feed.

## Requirements

### Requirement: Calendar page is reachable from every staff role's navigation
The system SHALL provide a Calendar page:
- at `/staff/calendar` inside the staff layout, for host, security and
  reception users;
- at `/admin/calendar` inside the admin layout, for admins.

The staff, reception and admin sidebars SHALL each show a "Calendar" item.
That item SHALL be marked active whenever the current path starts with that
portal's calendar route. An unauthenticated visit SHALL redirect to that
portal's login page, the same as the other pages in that portal.

#### Scenario: Host opens the calendar from the sidebar
- **WHEN** a signed-in host clicks "Calendar" in the staff sidebar
- **THEN** `/staff/calendar` opens and "Calendar" is the active sidebar item

#### Scenario: Reception sees Calendar in the reception sidebar
- **WHEN** a signed-in reception user views any staff page
- **THEN** the reception sidebar shows a "Calendar" item linking to
  `/staff/calendar`

#### Scenario: Admin opens the admin calendar
- **WHEN** a signed-in admin clicks "Calendar" in the admin sidebar
- **THEN** `/admin/calendar` opens inside the admin layout

#### Scenario: Expired session
- **WHEN** the calendar request returns 401
- **THEN** the user is redirected to the portal's login page, as on other
  pages

### Requirement: Calendar shows exactly the visits the API returns for the user
The page SHALL request the calendar feed for the visible date range and
SHALL render exactly the events in the response. It SHALL NOT add, hide or
re-scope events based on the user's role flags.

The page subtitle SHALL state the applied scope from the response:
- "Your visits" for `mine`;
- "All visits at <branch name>", or "All visits at all your branches", for
  `branch`.

#### Scenario: Host sees only their visitors
- **WHEN** a host opens the calendar
- **THEN** the subtitle reads "Your visits" and only the events the API
  returned for the host are shown

#### Scenario: Security sees their branch
- **WHEN** a security user authorized at one branch opens the calendar
- **THEN** the subtitle reads "All visits at <that branch>" and every visit
  at that branch in the range is shown

#### Scenario: No client-side role filtering
- **WHEN** the API returns an event whose host is not the signed-in user
- **THEN** the event is shown

### Requirement: Branch-wide viewers can narrow to one branch
When the response scope is `branch` and the user is authorized at more than
one branch (or company-wide), the page SHALL show a branch selector. It
SHALL list "All branches" plus each authorized branch.

- Choosing a branch SHALL refetch with that branch sent as `X-Branch-ID`.
- "All branches" SHALL send no branch header.
- The selector SHALL NOT appear for `mine` scope or for a single-branch
  user.

#### Scenario: Admin narrows to one branch
- **WHEN** an admin picks branch B in the selector
- **THEN** only branch B's visits are shown and the subtitle names branch B

#### Scenario: Host has no branch selector
- **WHEN** a host opens the calendar
- **THEN** no branch selector is rendered

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

### Requirement: Events show schedule, status and visitor at a glance
Each event SHALL show:
- its scheduled time (or "Any time");
- the primary contact's name, plus "+N" when there are co-visitors;
- a status label and colour: Pending (submitted), Expected (approved),
  Inside (checked in), Visited (checked out), Missed (archived), Denied
  (denied);
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

Status SHALL be conveyed by text as well as colour: a visible label in Week
and Day views, and the accessible name in every view. Event text SHALL meet
4.5:1 contrast against its fill in both the light and dark themes.

#### Scenario: Checked-in visitor
- **WHEN** an event has status `checked_in` with a check-in time of 10:42
- **THEN** it shows "Inside" and Day view shows "Checked in 10:42"

#### Scenario: Group visit
- **WHEN** an event has a visitor count of 4
- **THEN** it shows the primary contact name followed by "+3"

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

### Requirement: Clicking an event opens the invitation detail
Activating an event (by click, or Enter/Space when focused) SHALL navigate
to that portal's invitation board deep link (`?invitationId=<id>`), which
opens the existing invitation detail modal. Returning to the calendar SHALL
restore the previous view and date.

#### Scenario: Opening an event from the staff calendar
- **WHEN** a reception user clicks an event on `/staff/calendar`
- **THEN** `/staff/invitations?invitationId=<id>` opens with that
  invitation's detail modal

#### Scenario: Back returns to the same calendar view
- **WHEN** the user goes back from the detail
- **THEN** the calendar shows the same view and date as before

### Requirement: Status filter, truncation and empty states
The page SHALL provide a status filter. By default it SHALL show every
status except Denied. Changing it SHALL refetch with the chosen statuses and
SHALL reset every column and the day list to their first page. Each week
column and the day list SHALL also return to the top of its scroll, so
the reset list doesn't immediately load past its first page.

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

#### Scenario: Changing the filter after scrolling a column
- **WHEN** the user has scrolled Monday's week column far enough to load
  several pages, then turns a status in the filter on or off
- **THEN** Monday's column shows its top again and holds no more than the
  first page (plus the one preload a tall column makes on open)

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

### Requirement: Calendar refreshes like other operational pages
The calendar SHALL take part in the same automatic and manual refresh
behaviour as the dashboards and invitation boards. That covers periodic
polling while visible, refetch on return to the tab, and refetch on
invitation activity notifications. An automatic refresh SHALL NOT reset
the current view, date, branch or filter.

#### Scenario: Visitor checks in while the calendar is open
- **WHEN** an invitation on the visible day is checked in elsewhere and the
  next refresh runs
- **THEN** its event changes to "Inside" without the view changing

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
