## Why

Admins have no landing page: `/admin` routes currently jump straight into individual registers (Branches, Departments, Buildings, Floors, Organisation Configs) with no single place to see today's visitor activity at a glance. The Figma design (node `253:215`) defines an Admin Dashboard overview screen; building it gives admins the same kind of "walk in and see what's happening" home screen that `staff-dashboard` already gives staff, and finally activates the `'dashboard'` entry that `AdminSidebar` already reserves but never wires to a route.

## What Changes

- Add a new `/admin/dashboard` page rendering the Admin shell (`AdminSidebar` with `activeItem="dashboard"`, `AdminTopBar`) plus:
  - A welcome banner with the signed-in admin's first name and the current date
  - A KPI row: Today's Visitors, Currently On-Site, Pre-Registered, Average Visit Duration (each with a trend caption)
  - A 7-day Visitor Traffic chart (daily check-in counts), built with a plain in-repo SVG component — no charting library is added
  - A Recent Check-ins table (name, host, time, badge #, status)
  - A Visitors by Department breakdown (progress bars with count + percentage)
  - An Upcoming Pre-Registered Visitors list, each row with a functional "Check In" action that checks the visitor in and moves them out of the upcoming list
- Wire `AdminSidebar`'s existing `'dashboard'` key to navigate to `/admin/dashboard`
- Add a new composed dashboard-overview endpoint and domain schema backing all of the above in one fetch
- Per the design's own limited scope, the topbar search field, branch selector, notification bell, "View All" (Recent Check-ins), and "Print Pass" stay visually present but inert, matching the project's existing pattern for not-yet-functional affordances (e.g. `admin-branches`' "Filters")

## Capabilities

### New Capabilities
- `admin-dashboard`: the Super Admin's dashboard overview screen at `/admin/dashboard` — KPIs, visitor traffic chart, recent check-ins, department breakdown, and upcoming pre-registered visitors with a working Check In action.

### Modified Capabilities
(none — `AdminSidebar`'s dashboard-key wiring is an internal implementation detail of the new page, not a change to any other capability's documented requirements)

## Impact

- New page: `src/presentation/pages/admin-dashboard/`
- New route: `/admin/dashboard` in `src/App.tsx`
- Modified: `src/presentation/components/AdminSidebar.tsx` (wire the `'dashboard'` nav item)
- New domain schema, API endpoint, repository port/adapter, and use case for the dashboard-overview data and the check-in action
- New shared icons (trend-up/trend-down, calendar-check) added to `src/presentation/components/icons.tsx`
