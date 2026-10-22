Depends on the VMSS_API change `live-dashboards-and-analytics`. Implement
and deploy that change first, because these tasks consume its new fields
and endpoints.

## 1. Foundations

- [x] 1.1 `npm install recharts` (a React 19-compatible release, exact
  version pinned). Confirm `tsc -b` is clean (design.md risk).
- [x] 1.2 Build identifier (design.md W6):
  - add the `__APP_VERSION__` and `__BUILD_SHA__` `define`s in
    `vite.config.ts`, with typings in `vite-env.d.ts`;
  - pass `VITE_BUILD_SHA` in both Dockerfiles and the CI-CD pipeline.
- [x] 1.3 Lazy-load the admin, reception and staff dashboard pages in
  `App.tsx` with `React.lazy` and `Suspense`, using `LoadingState` as the
  fallback (W5).
- [x] 1.4 Add a `CurrentUserContext` provided by `AdminLayout` and
  `StaffLayout` from their existing `/auth/me` load (shared design D8).
- [x] 1.5 Move `/reception/dashboard` under the `StaffLayout` route group.
  Keep the role guard in the page. Delete `ReceptionTopBar` if nothing else
  imports it (D9).

## 2. Live refresh

- [x] 2.1 Extend `use-polling.ts` (D6, `live-data-refresh` spec):
  - pause while the tab is hidden;
  - refetch immediately on `visibilitychange` to visible and on `focus`,
    throttled to at most once per 5 s;
  - add an optional `refetchOn` subscription;
  - keep the `isBusy` skip.
- [x] 2.2 Add `onInvitationActivity` to `notification-center-context.tsx`.
  It fires once per poll that brings in new items with an `invitationId`
  (W3).
- [x] 2.3 Add a failure state to `refresh-context.tsx` and the
  `AppTopBar` refresh control: "Couldn't refresh · retrying", one toast per
  outage, cleared on the next success (D7).

## 3. Data layer

- [x] 3.1 Add the analytics and my-analytics endpoints to
  `api-endpoints.ts`. Add a new `dashboard-analytics-schema.ts`. Update the
  overview, my-overview and check-in zod schemas with the new fields
  (W2).
- [x] 3.2 Add the repository methods and the use cases `getDashboardAnalytics`
  and `getMyDashboardAnalytics`, and wire them in `composition-root.ts`.
  Request recent check-ins with an explicit `pageSize` of 8.
- [x] 3.3 Write the `useBranchDashboard({ branchId, range })` and
  `usePersonalDashboard({ range })` hooks:
  - read the user from `CurrentUserContext`;
  - fetch in parallel with `Promise.all`;
  - register with `usePageRefresh`;
  - use the extended polling with the invitation-activity refetch;
  - drop the `listHostEmployees` dependency.

  Remove the old admin, reception and staff dashboard hooks once their
  pages use these.

## 4. Dashboard components

- [x] 4.1 Add a `useChartTheme` hook that resolves `theme.css` tokens
  (including the status-pill colours) through `getComputedStyle`. Before
  writing any chart code, load the `dataviz` skill and follow it for
  palette and mark choices.
- [x] 4.2 `KpiTile` and `KpiRow`:
  - each tile is a link with an accessible name of label plus value;
  - each shows its optional secondary line ("N checked in so far", "Oldest
    waiting 2 h");
  - the grid is 1 column on phones, 2 at `sm` and 4 at `lg`.
- [x] 4.3 `ChartCard` provides the title, an actions slot, loading/empty
  states, an `aria-label` summary and an sr-only table. `DashboardGrid`
  provides the 12-column responsive wrapper (spans must pass
  `check-grid-spans.mjs`).
- [x] 4.4 Build the charts:
  - `TrafficTrendChart`: an area chart of scheduled, checked-in and no-show
    visits. Ticks thin out below `sm`.
  - `HourlyArrivalsChart`: bars, with the current hour highlighted.
  - `StatusBarsChart`: one labeled horizontal bar per status, in lifecycle
    order and board status colours; each bar deep-links to its status.
  - `TopLabelsChart`: ranked bars with a purposes/departments toggle.

  Every chart has tap tooltips, the per-breakpoint heights from D10, and an
  empty state when all values are zero.
- [x] 4.5 Add `RangeToggle` (7d/30d) and `BranchSelect`. The branch
  selector is shown only when the user is authorized at more than one
  branch, and offers "All branches".
- [x] 4.6 Rework `RecentCheckinsCard` and `UpcomingVisitorsCard`:
  - use the API's `hostFullName`;
  - take the status from the row's `status`;
  - show the scheduled date and time, falling back to expiry;
  - make rows open `?invitationId=`;
  - give each card a working "View all" with a `?status=` link;
  - truncate long names.
- [x] 4.7 Rework `MyUpcomingVisitorsCard` and add its "View all" to
  `/staff/invitations?status=approved`.
- [x] 4.8 Compose `BranchDashboard`, which takes `boardBasePath`, and
  `PersonalDashboard` in the D11 layout. The greeting and date label come
  from the API's `today`; delete every `TODAY_LABEL` constant.
- [x] 4.9 Make the admin, reception and staff pages thin wrappers around
  these components.

## 5. Board deep link and shell cleanup

- [x] 5.1 Make `use-invitations-board.ts` read and validate `?status=` once
  on mount, so it works together with `?invitationId=` (W4). This serves
  both the admin and staff boards.
- [x] 5.2 Remove "Help & Support" from `DashboardSidebar`.
- [x] 5.3 Replace the `AdminSidebar` footer's "v1.2 Active" with the build
  identifier. Hide the line when it is empty or the rail is collapsed.

## 6. Verification

- [x] 6.1 Add Playwright e2e tests under `e2e/` (seeded through the QA
  harness; never run concurrently with API pytest):
  - **Control sweep:** every interactive control on the admin, reception and
    staff dashboards changes the URL or the page state.
  - **Deep links:** each KPI tile and each "View all" opens the right
    `?status=` board, with the filter applied.
  - **Layout:** no horizontal document scroll at 360×740, 768×1024 and
    1440×900 on all three dashboards.
  - **Range:** the toggle switches the trend to 30 points.
  - **Personal scope:** a host sees only their own figures.
- [ ] 6.2 Manual QA at 360, 390, 768, 1024 and 1440 px, in portrait and
  landscape. Check:
  - the charts are readable and tooltips work on tap;
  - leaving a tab hidden stops requests (devtools network), and refocusing
    refetches;
  - a check-in on another device shows up within one refresh;
  - stopping the API gives one toast and the retrying state;
  - restarting the API recovers.
- [x] 6.3 Run `tsc -b`, `npm run lint` and `npm run build` (confirm Recharts
  is only in the dashboard chunks). Do not run prettier.
  *Result (2026-10-16):* `tsc -b` is clean. `npm run lint` shows only the
  2 warnings already in `use-visitor-request-wizard.ts`. Recharts ships
  only in the lazily loaded dashboard chunks (about 111 kB gzipped). For the
  e2e results: `test_live_dashboards.py` and `test_auth_and_dashboards.py`
  pass (31 passed, plus 2 strict xfails for the existing F7). In the full
  e2e run, `test_staff_invitation_lifecycle` failed once and then passed
  3/3 on rerun. It asserts the status straight after the approve click,
  without waiting, so this is an existing race and not caused by this
  change.

**6.2 status (partial):** done so far:
- screenshots at 360, 768 and 1440 px of the admin and staff dashboards,
  which caught a clipped trend label and crowded hourly ticks (both fixed);
- the e2e no-horizontal-scroll check, which caught the sr-only table
  widening the page (fixed by anchoring and wrapping it).

Still to do by hand:
- 390 and 1024 px, and landscape;
- tap tooltips on a real touch device;
- devtools network checks that requests stop on a hidden tab;
- a check-in from another device;
- the API-outage toast and recovery.
