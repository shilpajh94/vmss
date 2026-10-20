## Why

Staff cannot see visits laid out by date. Hosts, reception and security only
have the invitation board, which is sorted by status change, so "who is
visiting on Thursday?" or "how busy is next week?" means paging through a
list.

Each role needs a calendar that shows exactly the visits that role should
see:

- a host sees their own visitors;
- reception and security see every visit at the branches they work at;
- admins see every branch.

This change has a companion change of the same name in VMSS_API. That change
holds the `GET /invitations/calendar` contract and the shared design
(`VMSS_API/openspec/changes/archive/2026-10-19-add-staff-calendar/design.md`). This one holds
the web specs and tasks.

## What Changes

- **New Calendar page**:
  - in the staff portal at `/staff/calendar`, for host, security and
    reception;
  - in the admin portal at `/admin/calendar`.
- **Month, week and day views**, with previous / next / today navigation.
  The view and date are kept in the URL so a link reopens the same view.
- **Visibility comes from the API only.**
  - The page renders what the calendar endpoint returns for the signed-in
    user. It never filters by role itself.
  - The subtitle states the applied scope ("Your visits" or "All visits at
    <branch>").
  - A branch selector appears only for branch-wide viewers with more than
    one branch.
- **Events show:**
  - scheduled time;
  - visitor name with co-visitor count;
  - a status colour (Pending, Expected, Inside, Visited, Missed);
  - a visitor-category colour;
  - for branch-wide viewers, host and branch.
- **Status filter**: a denied visit can be shown on request. Day totals
  stay exact, and the page shows a truncation banner when the API caps the
  list.
- **Clicking an event** opens the existing invitation detail modal through
  the board's `?invitationId=` deep link.
- **Navigation**: a "Calendar" nav item in the staff, reception and admin
  sidebars.
- **Behaviour**: the page joins the existing auto-refresh and manual
  refresh behaviour, and is usable on phone widths.

## Capabilities

### New Capabilities
- `staff-calendar`: the role-scoped visit calendar page (month, week and
  day views, navigation, event display, filters and deep links) in the
  staff and admin portals.

### Modified Capabilities
<!-- None. Sidebar entries and refresh participation for the new page are specified inside `staff-calendar`; existing pages' requirements are unchanged. -->

## Impact

- **New code:**
  - `presentation/pages/calendar/` (page, hooks, MonthGrid, WeekView,
    DayAgenda);
  - `presentation/utils/calendar-dates.ts`;
  - `domain/entities/calendar-feed-schema.ts` (zod);
  - a repository, use case and endpoint constant in the
    data/infrastructure layers.
- **Changed:**
  - `App.tsx` (two lazy routes);
  - `DashboardSidebar`, `ReceptionSidebar` and `AdminSidebar` (nav item
    and active-prefix maps);
  - `composition-root.ts`.
- **Dependencies:** none added.
- **Depends on:** VMSS_API `add-staff-calendar` deployed first.
