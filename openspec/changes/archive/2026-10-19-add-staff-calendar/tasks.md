Depends on the VMSS_API change `add-staff-calendar`. Implement and deploy
that change first, because these tasks consume `GET /invitations/calendar`.

## 1. Data layer

- [x] 1.1 Add `CALENDAR_FEED: '/invitations/calendar'` to
  `data/api/api-endpoints.ts`.
- [x] 1.2 `domain/entities/calendar-feed-schema.ts`: zod schemas for
  `CalendarFeed` (`scope`, `timezone`, `from`, `to`, `generatedAt`, `days`,
  `events`, `truncated`) and `CalendarEvent`, matching the API's camelCase
  fields. Nullable fields: `time`, `checkedInAt`, `checkedOutAt`, `hostId`,
  `hostFullName`, `buildingName`, the category fields and
  `expectedDuration`.
- [x] 1.3 Add a `data/repositories/calendar-repository.ts` interface and an
  `infrastructure/calendar-repository.ts` implementation:
  - `getFeed({ from, to, branchId?, statuses? })`;
  - send repeatable `status` params;
  - send `X-Branch-ID` via the `headers` option only when `branchId` is
    set;
  - validate the response with the zod schema.
- [x] 1.4 Add the `data/use-cases/get-calendar-feed.ts` use case and wire
  it in `composition-root.ts` / the app-dependencies context.

## 2. Shared utilities

- [x] 2.1 `presentation/utils/calendar-dates.ts` (pure, `YYYY-MM-DD`
  strings): `addDays`, `startOfWeek` (Monday), `monthGridRange`,
  `weekRange`, `dayRange`, `todayIn(timezone)`, `isSameMonth`, and label
  formatters via `Intl.DateTimeFormat` (design.md W3).
- [x] 2.2 Extract the branch-option derivation (`authorizedBranchIds` and
  the branch-name loading) from `use-branch-dashboard.ts` into
  `hooks/use-branch-options.ts`. Switch the dashboard to it with no
  behaviour change (W1).
- [x] 2.3 Add `pages/calendar/calendar-status.ts`, mapping status → label
  (Pending, Expected, Inside, Visited, Missed, Denied) and design-theme
  colour tokens with light and dark parity.

## 3. Page state and data hooks

- [x] 3.1 `pages/calendar/hooks/use-calendar-state.ts`: URL-synced `view`,
  `date`, `branch` and `status`, with phone and desktop default views
  (W2).
- [x] 3.2 `pages/calendar/hooks/use-calendar-feed.ts`:
  - fetch for the computed range;
  - keep the last good data while refetching;
  - add a stale-response guard;
  - `usePolling` with `refetchOn: onInvitationActivity`;
  - redirect to `loginPath` on 401 (W4).

  *Implemented with* the existing `useLiveResource`/`useLiveDashboard`
  hooks, which already provide last-good data, superseded-response
  dropping, polling, `onInvitationActivity` and the top-bar refresh
  control. Each response is tagged with the query it answers, so data for an
  older range, branch or filter is shown as stale, never as current.

## 4. Components

- [x] 4.1 `CalendarToolbar`:
  - prev/next/today;
  - Month/Week/Day tabs;
  - a branch selector shown only when `scope === 'branch'` and there is
    more than one option;
  - a status multi-select (default: all but Denied);
  - the refresh control.

  *Deviation:* the refresh control is the layout's shared top-bar one,
  which the page registers with through `useLiveDashboard`. No second
  button was added to the toolbar.
- [x] 4.2 `CalendarEventChip`:
  - time or "Any time", name with "+N", status label and colour, category
    accent;
  - keyboard-activatable;
  - navigates via `buildInvitationPath(id)`.

  *Implemented with* `dashboard-format.ts::boardInvitationPath(boardBasePath, id)`.
  It builds the same deep link, but from the portal the page was rendered
  for rather than from `window.location`.
- [x] 4.3 `MonthGrid`:
  - a 6×7 grid with the exact `days[].total`;
  - a chip limit per cell, with "+N more" switching to Day view;
  - tenant-today highlight and out-of-month dimming.
- [x] 4.4 `WeekView`: seven columns with an "Any time" row and hour rows,
  scrolling horizontally inside its own container on narrow screens.
- [x] 4.5 `DayAgenda`:
  - "Any time" and hour groups;
  - full details: purpose, actual check-in and check-out in the tenant
    timezone;
  - for `branch` scope, host ("Unassigned" when null) and branch.
- [x] 4.6 `calendar-page.tsx`:
  - a header with the scope subtitle ("Your visits" or "All visits at
    …");
  - a truncation banner;
  - the empty state;
  - the standard error state with retry;
  - `LoadingState` on first load.

## 5. Routing and navigation

- [x] 5.1 Add lazy routes in `App.tsx`: `/staff/calendar` in the
  `StaffLayout` group and `/admin/calendar` in the `AdminLayout` group,
  both rendering `CalendarPage` with the right `loginPath`.
- [x] 5.2 Add a "Calendar" item (calendar icon) to the nav:
  - `DashboardSidebar` and `ReceptionSidebar`: after "Invitations",
    routing to `/staff/calendar`, plus the `/staff/calendar` prefix in
    their active-item maps and the `staffNavLabelFor` label;
  - `AdminSidebar`: after "Invitations", routing to `/admin/calendar`,
    plus the active map and `adminNavLabelFor`.

## 6. Verification

- [x] 6.1 Run `tsc -b`, `npm run lint` (oxlint plus the brand and grid
  checks) and `npm run build`. Do not run prettier.
- [x] 6.2 Add `e2e/test_staff_calendar.py`, using the API QA tokens.
  Never run it alongside the API's pytest.
  - **Navigation:** admin, reception, security and host each reach
    Calendar from their sidebar, with the active item and subtitle
    correct.
  - **Host scope:** a host sees only events that are also in their
    `relevantToMe` board.
  - **Security scope:** a security user sees branch-wide events.
  - **Branch B:** the branchb user never sees branch A visits.
  - **Navigation and URL:**
    - Month→Next spans Oct→Nov correctly;
    - "+N more" opens Day view;
    - a reload keeps `view` and `date`.
  - **Interaction:**
    - clicking an event opens the detail modal, and Back restores the
      view;
    - the Denied filter adds denied events.
  - **Responsive:** at 390px the page opens in Day view with no
    horizontal page scroll.
- [x] 6.3 Manually check light and dark themes and the collapsed icon-rail
  sidebar.

  *Result:* screenshots were checked of admin month (1440), reception week,
  host day and security phone (390).
  - The phone check found the day title truncated; it now wraps to its own
    line.
  - *Deviation:* VMMS_WEB has a single light theme (`styles/theme.css`, no
    dark tokens), so dark-mode parity doesn't apply. The status colours
    reuse the board's existing light-theme tones.
  - The collapsed icon rail was not screenshotted. The Calendar item uses
    the same `SidebarNavItem` as every other entry, so it gets the rail's
    icon-only rendering.
