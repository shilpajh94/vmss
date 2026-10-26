## Why

The admin, reception and staff dashboards are the portal's landing pages,
but they look unfinished:
- They show four count tiles and two short lists, with no charts.
- "View All" on Recent Check-ins does nothing, and "Help & Support" in the
  staff sidebar does nothing either.
- The admin sidebar shows a hardcoded "v1.2 Active" with a fake health dot.
- The date label is computed once and goes stale after midnight.
- The Reception dashboard never refreshes on its own.
- Host names come from the first 100 employees only.
- "Today's Visitors" counts invitations *created* today, not visits that
  are *happening* today.

The dashboards need to feel like a product: live, accurate figures, a
small set of meaningful charts, every control working, and a layout that
holds up from 360 px phones to wide desktops.

This change is the web half of the change of the same name in VMSS_API.
That change adds the analytics endpoints and new overview fields, and holds
the shared design (`VMSS_API/openspec/changes/archive/2026-10-16-live-dashboards-and-analytics/design.md`,
decisions D6–D12 cover the web).

## What Changes

- **Charts (Recharts).**
  - The admin and reception dashboards show:
    - a visitor-traffic trend (scheduled, checked in, no-shows; 7 or 30
      days);
    - arrivals today by hour;
    - a status breakdown (one labeled bar per status);
    - top purposes and departments.
  - The staff dashboard shows "My visits" as a trend and as a status
    breakdown.
  - Every chart has a text summary for screen readers and its own empty
    state.
- **Meaningful KPI tiles.**
  - The tiles are: "Expected today" (with "N checked in so far"), "On-site
    now", "Pending approval" (with how long the oldest has waited) and
    "Upcoming".
  - Each tile is a link to the invitations board, filtered to that status.
  - "Today" comes from the server, in the tenant's timezone, and stays
    correct past midnight.
- **Every control works.**
  - "View all" on Recent Check-ins and on Upcoming visitors opens the board
    filtered to that status.
  - Rows open the invitation.
  - Status bars deep-link to their status.
  - The invitations board (admin and staff) honours a `?status=` deep link.
  - "Help & Support" is removed.
  - "v1.2 Active" is replaced by the real build identifier.
- **Live data.**
  - Dashboards keep the 15 s refresh. Polling pauses while the tab is
    hidden, and the page refetches as soon as you return to the tab.
  - A new invitation notification triggers an immediate refetch.
  - A failed background refresh shows one toast and a "retrying" state,
    instead of a toast every 15 s.
  - Dashboards stop re-fetching `/auth/me` and the employee list on every
    tick.
- **Reception parity.**
  - `/reception/dashboard` moves under the shared staff layout. It gains
    the top-bar refresh control, auto-refresh, charts and working buttons.
  - Admin and reception share one branch-dashboard component.
- **Responsive.**
  - A 12-column dashboard grid that stacks to one column on phones and two
    columns on tablets.
  - Chart heights are set per breakpoint, and the trend's x-axis ticks thin
    out on phones.
  - Rows truncate long names.
  - No horizontal page scroll at 360 px.
- **Dependency:** add `recharts`, loaded only with the dashboard routes.

None of this is **BREAKING** for users. The `/reception/dashboard` URL and
its role gate are unchanged.

## Capabilities

### New Capabilities
- `dashboard-insights`: the shared live KPI tiles, charts, range toggle,
  deep links, accessibility and responsive grid used by every dashboard.
- `staff-home-dashboard`: the personal staff dashboard at
  `/staff/dashboard`. It was built in `staff-lifecycle-emails-and-dashboard-landing`
  but never specified on the web side.

### Modified Capabilities
- `admin-dashboard`:
  - The KPI tiles and their sources change.
  - Recent check-ins and upcoming rows become actionable, and "View All"
    becomes functional (the "not yet functional" requirement is removed).
  - Background-refresh failures are reported quietly.
- `reception-dashboard`: the same changes as `admin-dashboard`, plus
  rendering inside the shared staff layout with its refresh control.
- `staff-dashboard`: "Help & Support" is removed, and the board honours a
  `?status=` deep link.
- `admin-invitations`: the board honours a `?status=` deep link.
- `live-data-refresh`:
  - Polling pauses on hidden tabs and refetches when the tab is shown or
    focused, and when an invitation notification arrives.
  - Background failures do not repeat toasts.
- `app-shell`: the sidebar footer shows the real build identifier instead
  of a static label.

## Impact

- **Code:**
  - `App.tsx` (the reception route moves under `StaffLayout`; lazy dashboard
    routes);
  - `AdminLayout` and `StaffLayout` (current-user context);
  - `use-polling.ts`, `notification-center-context.tsx` and
    `refresh-context.tsx`;
  - `AppTopBar` (the retrying state);
  - the admin, reception and staff dashboard pages and hooks;
  - `components/dashboard/*` (new chart cards and the shared
    `BranchDashboard`);
  - `use-invitations-board.ts` (`?status=`);
  - `DashboardSidebar` and `AdminSidebar`;
  - the dashboard domain schemas, use cases and repository;
  - `api-endpoints.ts`;
  - `vite.config.ts` (`define` for the build id).
- **Removed:** `ReceptionTopBar` (if unused), and the dashboards'
  `listHostEmployees` dependency.
- **Dependencies:** `recharts`.
- **Tests:** Playwright e2e under `e2e/`. It covers dead-control sweeps,
  deep links, and no horizontal scroll at 360, 768 and 1440 px for every
  dashboard.
- **Ordering:** the VMSS_API change must be deployed first.
