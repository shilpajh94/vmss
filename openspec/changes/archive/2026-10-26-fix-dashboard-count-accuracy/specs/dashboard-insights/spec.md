## MODIFIED Requirements

### Requirement: KPI Tiles Link to the Matching Invitations
Each KPI tile SHALL be a single link that opens the invitations board,
filtered to exactly the invitations the tile counts:
- Pending/Awaiting approval → status `submitted`, excluding expired
  requests (`excludeExpired=true`);
- On-site/Inside now → status `checked_in`;
- Upcoming → upcoming invitations only (`upcoming=true`);
- Expected/Visits today → statuses `approved`, `checked_in` and
  `checked_out`, with a visit date from and to the dashboard's `today`.

On a branch dashboard with a branch selected, every tile link SHALL also
carry that branch (`branchId`). Dates SHALL come from the API response,
never the browser's clock.

Admins SHALL be taken to the admin board, and every other role to the staff
board. Each tile SHALL be keyboard-focusable and SHALL have an accessible
name that includes its label and value.

#### Scenario: Admin opens pending approvals from the tile
- **WHEN** an admin activates the "Pending approval" tile
- **THEN** the system navigates to
  `/admin/invitations?status=submitted&excludeExpired=true` and the board
  shows only submitted invitations whose visit window is still open

#### Scenario: Staff opens their on-site visitors
- **WHEN** a staff member activates the "Inside now" tile
- **THEN** the system navigates to `/staff/invitations?status=checked_in`

#### Scenario: Expected today opens today's visits in every state
- **WHEN** an admin whose dashboard reports `today` as 2026-10-26 activates
  "Expected Today"
- **THEN** the board opens with statuses Approved, Checked-in and
  Checked-out and a visit date of 26 Oct, and its column totals add up to
  the tile's value

#### Scenario: Selected branch is carried through
- **WHEN** an admin selects Branch A on the dashboard and activates
  "Upcoming Visitors"
- **THEN** the board opens with `upcoming=true` and `branchId` set to
  Branch A, and shows only Branch A's upcoming invitations

### Requirement: KPI Tiles Carry a Live Secondary Detail
Where the API provides it, a tile SHALL show one secondary line under its
value:
- The "Expected today" tile on branch dashboards SHALL show how many of
  today's expected visitors have checked in so far, from
  `scheduledTodayCheckedInCount`. That number SHALL never exceed the tile's
  value.
- The "Pending approval" tile SHALL show how long the oldest pending
  request whose visit window is still open has been waiting (for example
  "Oldest waiting 2 h"), from `oldestOpenPendingSubmittedAt`, and SHALL
  omit that line when nothing is pending.

#### Scenario: Oldest pending wait is shown
- **WHEN** the oldest open submitted request was submitted 2 hours ago
- **THEN** the "Pending approval" tile reads "Oldest waiting 2 h" beneath
  its count

#### Scenario: Expired requests don't set the wait
- **WHEN** an open request was submitted 2 hours ago and an expired one was
  submitted 5 days ago
- **THEN** the tile counts only the open request and reads "Oldest waiting
  2 h"

#### Scenario: Nothing pending
- **WHEN** the pending count is 0
- **THEN** the tile shows 0 and no waiting-time line

#### Scenario: Visitors for other days don't inflate the detail
- **WHEN** 2 visits are expected today, 1 of them has checked in, and a
  visitor scheduled for tomorrow also checked in today
- **THEN** the tile shows 2 with "1 checked in so far"

### Requirement: Branch Dashboards Show Four Analytics Charts
The admin and reception dashboards SHALL show these four charts, built from
the branch-wide analytics response:
- **Visitor traffic**: scheduled, checked-in and no-show visits per day over
  the selected range.
- **Arrivals today**: check-ins per hour of today, with the current hour
  visually highlighted.
- **Visits by status**: one labeled horizontal bar per status, in
  lifecycle order. Each bar shows the status name and count, in its board
  status colour. Each bar SHALL link to the board filtered to that status
  and to visit dates from the first day of the selected range to `today`,
  plus the selected branch, so the board's total equals the bar's count.
- **Top purposes / departments**: ranked bars with a toggle between
  purposes and departments.

Each chart SHALL show the exact value of a data point on hover, on keyboard
focus, and on tap.

#### Scenario: Charts render with data
- **WHEN** a branch with visits in the last 7 days opens the admin dashboard
- **THEN** all four charts render, and hovering or tapping a trend day shows
  that day's scheduled, checked-in and no-show counts

#### Scenario: Status bar opens its status
- **WHEN** an admin, on the 7-day range ending 2026-10-26, activates the
  "Denied" bar of the status breakdown
- **THEN** the system navigates to the invitations board filtered to
  `denied` with visit dates 20 Oct to 26 Oct, and the board's total equals
  the bar's count

## ADDED Requirements

### Requirement: Every Dashboard Figure Matches the List It Opens
On the admin, reception and staff dashboards, every element that shows a
count and links to the board SHALL open a board whose column totals add up
to that count, for the same user, the same branch selection and the same
moment. This covers the KPI tiles, the status bars, the Upcoming card's
"View all" (`upcoming=true`), and Recent Check-ins "View all" (statuses
`checked_in` and `checked_out`). The staff dashboard's links open the staff
board, which stays limited to the user's own visits, as its counts are.

#### Scenario: Staff counts match their board
- **WHEN** a host's dashboard shows "Visits Today" 3 and "Awaiting
  Approval" 2, and the host activates each tile in turn
- **THEN** the staff board shows 3 and 2 invitations respectively

#### Scenario: Upcoming card View all
- **WHEN** a user activates "View all" on the Upcoming Visitors card
- **THEN** the board opens with `upcoming=true` and its total equals the
  "Upcoming" tile's value

#### Scenario: Reception counts match the reception board
- **WHEN** a reception user selects Branch A on the reception dashboard and
  activates "On-Site Now"
- **THEN** the staff board opens with `status=checked_in` and `branchId`
  set to Branch A, and its total equals the tile's value
