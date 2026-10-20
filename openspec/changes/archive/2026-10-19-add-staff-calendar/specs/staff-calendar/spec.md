## Purpose

A calendar page in the staff and admin portals that lays out visits and
invitations by date. Each signed-in user sees exactly the visits their role
entitles them to, as decided by the API's calendar feed.

## ADDED Requirements

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

- **Month** SHALL show a six-week grid. Each day cell SHALL show its exact
  total from the response and as many event chips as fit, followed by a
  "+N more" control that opens that day in Day view.
- **Week** SHALL show seven day columns. Each column SHALL have an
  "Any time" row and hour rows; events are placed by scheduled time.
- **Day** SHALL list that day's events in an "Any time" group and hour
  groups, with full event details.

"Today" SHALL be the tenant-local date implied by the response's timezone,
not the browser's date. It SHALL be visibly highlighted.

#### Scenario: Navigating months
- **WHEN** the user is in Month view for October 2026 and clicks Next
- **THEN** November 2026 is shown, the URL updates to the new date, and the
  feed is requested for November's six-week grid

#### Scenario: Day overflow opens Day view
- **WHEN** a month cell has more events than fit and the user clicks
  "+N more"
- **THEN** Day view opens for that date showing all of its events

#### Scenario: Visit with no scheduled time
- **WHEN** an event has no scheduled time
- **THEN** it appears in the "Any time" row in Week and Day views

#### Scenario: Reload keeps the view
- **WHEN** the user reloads `/staff/calendar?view=week&date=2026-10-19`
- **THEN** the week of Monday 2026-10-19 is shown in Week view

#### Scenario: Today follows the tenant timezone
- **WHEN** the browser's local date differs from the tenant-local date
- **THEN** the highlighted "today" is the tenant-local date

### Requirement: Events show schedule, status and visitor at a glance
Each event SHALL show:
- its scheduled time (or "Any time");
- the primary contact's name, plus "+N" when there are co-visitors;
- a status label and colour: Pending (submitted), Expected (approved),
  Inside (checked in), Visited (checked out), Missed (archived), Denied
  (denied);
- a visitor-category colour accent.

Day view and the event's hover or focus detail SHALL also show the
purpose, the actual check-in and check-out times when present (in the
tenant timezone), and, for `branch` scope, the host name ("Unassigned" when
null) and the branch.

Status SHALL be conveyed by text as well as colour. Colours SHALL meet
contrast in both light and dark themes.

#### Scenario: Checked-in visitor
- **WHEN** an event has status `checked_in` with a check-in time of 10:42
- **THEN** it shows "Inside" and Day view shows "Checked in 10:42"

#### Scenario: Group visit
- **WHEN** an event has a visitor count of 4
- **THEN** it shows the primary contact name followed by "+3"

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
status except Denied. Changing it SHALL refetch with the chosen statuses.

When the response is `truncated`, the page SHALL show a banner saying not
every visit is listed, and SHALL suggest Week or Day view. Day totals SHALL
still show the response's exact counts.

A range with no events SHALL show an empty-state message rather than a
blank grid area. A failed request SHALL show the standard error state with
a retry action.

#### Scenario: Showing denied visits
- **WHEN** the user adds "Denied" in the status filter
- **THEN** the feed is refetched including denied invitations and they are
  shown with the "Denied" label

#### Scenario: Truncated month
- **WHEN** the response has `truncated: true`
- **THEN** a banner explains that only the first visits are listed, and
  each month cell's count still equals that day's `total`

#### Scenario: Empty week
- **WHEN** the week has no visits
- **THEN** the week grid shows an empty-state message

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
Week available. It SHALL NOT cause horizontal page scrolling. Week view
MAY scroll horizontally within its own container.

#### Scenario: Phone width
- **WHEN** the calendar opens at a 390px-wide viewport without a `view`
  query parameter
- **THEN** Day view is shown and the page has no horizontal scrollbar
