## Context

The full design is shared with the API half of this change:
`VMSS_API/openspec/changes/archive/2026-10-19-add-staff-calendar/design.md`.
- D1–D5 are the API contract: endpoint, scope resolution, event-date rule,
  response shape and default statuses.
- D6–D8 are the web decisions: hand-built views, routes and navigation,
  and visual encoding.

Read that file first. This one records only what is specific to how
VMMS_WEB builds it.

Web state that shapes the build:

- **Layered structure:**
  - `domain/entities` (zod schemas);
  - `data/repositories` (interfaces) and `data/use-cases`;
  - `infrastructure/*-repository.ts`;
  - wiring in `composition-root.ts`;
  - pages under `presentation/pages/<page>/` with a `hooks/` folder.
- **Branch options.** `use-branch-dashboard.ts` already derives branch
  options from `StaffUser.branchRoles` filtered by
  `BRANCH_WIDE_ROLES = {admin, reception, security}`, and loads branch
  names via `listBranchesUseCase`.
- **Refresh.** `usePolling` handles visibility, focus and the `refetchOn`
  subscription. `notification-center-context` exposes
  `onInvitationActivity`.
- **Deep links.** `buildInvitationPath(id)` already picks `/admin` vs
  `/staff` from the current path, and the board opens `VisitorInfoModal`
  from `?invitationId=`.
- **Testing.** There is no unit-test runner. Verification is `tsc -b`,
  `npm run lint`, and Playwright e2e in `e2e/` (pytest, using tokens minted
  by the API QA scripts).

## Goals / Non-Goals

**Goals:**
- One `CalendarPage` component used by both portals.
- No new npm dependency.
- The URL is the source of truth for the view and date.

**Non-Goals:**
- An in-page detail modal (D7 of the shared design: reuse the board deep
  link).
- A "Mine / Branch" toggle.
- Drag and drop.

## Decisions

### W1. Branch selector options reuse the dashboard's derivation; the API stays authoritative

Extract `authorizedBranchIds` and the branch-option loading from
`use-branch-dashboard.ts` into a shared `use-branch-options.ts`. Use it in
both the dashboard and the calendar.

The selector only renders when the response `scope === 'branch'`. If the
role-name heuristic ever disagrees with real permissions (for example, a
custom role that holds `view-all`), the worst case is a missing or extra
option. The API still 403s an unauthorized `X-Branch-ID`, and the page
shows the error state.

*Alternative:* add an API endpoint listing the caller's authorized
branches. Deferred: the heuristic is already what the dashboard ships.

### W2. URL-driven state

`useCalendarState()` reads and writes `view` (`month`|`week`|`day`),
`date` (`YYYY-MM-DD`), `branch` and `status` (repeatable) via
`useSearchParams`.

- With no `view`, the default is `day` below the desktop breakpoint
  (`use-media-query`) and `month` otherwise.
- With no `date`, the default is the tenant-local today. That is the
  browser date until the first response arrives; after that, `today` comes
  from the response's `timezone`.
- Back navigation from the deep link restores the view for free, because
  the URL is the state.

### W3. Range computation

`calendar-dates.ts` (pure, string dates) provides:

- `monthGridRange(date)`: Monday on or before the 1st, to +41 days;
- `weekRange(date)`: Monday to Sunday;
- `dayRange(date)`.

Every range is ≤ 42 days, matching the API cap. `todayIn(timezone)` uses
`Intl.DateTimeFormat('en-CA', { timeZone })` to get the local `YYYY-MM-DD`.

### W4. Data hook and refresh

`useCalendarFeed({ from, to, branchId, statuses, loginPath })` calls
`getCalendarFeedUseCase`. It:

- keeps the last good response while refetching, with no skeleton flash on
  polling;
- uses `usePolling` (same interval as the boards) with `refetchOn:
  onInvitationActivity`;
- redirects on 401 like the board hooks.

A request-sequence guard drops stale responses when the user navigates
quickly.

### W5. Component split

`pages/calendar/`:
- `calendar-page.tsx`: header, toolbar, view switch;
- `CalendarToolbar`: prev/next/today, view tabs, branch selector, status
  filter;
- `MonthGrid`, `WeekView` and `DayAgenda`;
- `CalendarEventChip`;
- `calendar-status.ts`: status → label and colour token map (shared design
  D8).

Admin and staff routes render `<CalendarPage loginPath=… />`, lazy-loaded
in `App.tsx` like the dashboards.

## Risks / Trade-offs

- **The role-name branch heuristic drifts from permissions.** → The API is
  authoritative (W1). The selector is only a narrowing aid.
- **Month cells overflow on busy days.** → A fixed chip count per cell plus
  "+N more" from the exact `days[].total`.
- **No unit tests for the date math.** → The e2e test covers month
  boundaries (Oct→Nov, a 31st, a Monday-start week that spans months) and
  the timezone "today".

## Migration Plan

Ship after the API change is deployed. Rollback: remove the three nav items
and two routes.
