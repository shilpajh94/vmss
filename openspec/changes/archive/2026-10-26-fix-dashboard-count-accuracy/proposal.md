## Why

The dashboard numbers look wrong, because the list a number opens almost
never shows that number:

- "Expected Today" and "Visits Today" open every approved invitation, of
  any date, and leave out the checked-in and checked-out visits they
  counted.
- "Upcoming" opens the same list, which includes expired passes.
- "Pending Approval" counts requests whose visit is long over. Locally, 174
  of 192 were expired, so "Oldest waiting" read in days.
- "N checked in so far" counts check-ins for any day, so it can exceed
  "Expected Today".
- Recent Check-ins "View all" opens checked-in visitors only, but the card
  also lists checked-out ones.
- Status chart bars count the last 7 or 30 days, but open that status for
  all time.
- A branch picked on the admin or reception dashboard is dropped when you
  click through.
- The dashboard's "today" and hourly chart use a different timezone from
  the rest of the system (fixed in the API).

This change is the web half of the VMSS_API change of the same name. That
change adds the corrected count fields and the list filters a link needs,
and it holds the shared design. Decision D7 there defines every
drill-down link:
`VMSS_API/openspec/changes/fix-dashboard-count-accuracy/design.md`.

## What Changes

- **Tiles use the corrected fields.**
  - "Pending Approval" shows `openPendingApprovalCount` and "Oldest
    waiting" uses `oldestOpenPendingSubmittedAt`.
  - Staff "Awaiting Approval" shows `openAwaitingApproval`.
  - The "checked in so far" line under "Expected Today" uses
    `scheduledTodayCheckedInCount`.
- **Every dashboard link opens exactly the counted invitations.** That
  covers the tiles, the Upcoming card's "View all", Recent Check-ins "View
  all", and the status bars, on the admin, reception and staff dashboards.
  Each link carries the matching status, visit-date range, `upcoming`,
  `excludeExpired` and selected `branchId`, using the API's `today` and
  range dates, never the browser clock.
- **The admin and staff boards read those parameters from the URL.**
  - `status` can now be repeated.
  - The boards apply the parameters to every column and to export.
  - They show the non-status ones as a removable "From dashboard" chip
    row, which "Clear filters" also clears.
  - The sum of the column totals then equals the number that was clicked.
- No layout, chart or styling changes beyond the chip row.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `dashboard-insights`: tile links, the tile detail line and status-bar
  links now open exactly the counted set; adds a requirement that every
  dashboard figure matches the list it opens.
- `admin-dashboard`: Recent Check-ins "View all" opens checked-in and
  checked-out visits.
- `admin-invitations`: the admin board's deep link accepts the drill-down
  parameters and shows them as chips.
- `staff-dashboard`: the staff board's deep link does the same.

These capabilities' current text comes from the still-open
`live-dashboards-and-analytics` change. **That change must be archived
first**, so these MODIFIED deltas have a main spec to apply to.

## Impact

- Code:
  - `presentation/components/dashboard/`: `BranchDashboard`,
    `PersonalDashboard`, `RecentCheckinsCard`, `UpcomingVisitorsCard`,
    `StatusBarsChart` and `dashboard-format`;
  - `presentation/hooks/use-invitations-board.ts`, plus the board filter
    bar and chip row;
  - `data/repositories/visit-request-summary-repository.ts` (new list and
    export params);
  - the dashboard overview Zod schemas.
- Depends on the API change shipping first. The new fields are required
  in the Zod schemas, so a missing field fails loudly instead of showing a
  wrong number.
- Tests: one e2e module for dashboard-to-board parity (targeted run only).
