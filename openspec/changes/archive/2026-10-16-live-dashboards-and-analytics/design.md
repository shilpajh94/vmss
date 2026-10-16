## Context

See proposal.md for the gap analysis. This design covers both halves of the
change: this API change and its VMMS_WEB companion of the same name. The
facts that shape the approach:

- **Data source.** `invitations` is the only source. There is no check-in
  events table: `checked_in_at` and `checked_out_at` hold the **most recent**
  entry only, even though re-entry is allowed (`allow-multiple-checkins`).
  `archived` is reached only through the no-show sweep (`approved`, never
  admitted, past `expires_at`), so `archived` reliably means "no-show".
- **Existing queries.** `dashboard/repository.py` already issues one count
  per KPI tile. `my-overview` already uses one `COUNT(*) FILTER (...)`
  statement over `relevant_to_me_clause`. Neither `preferred_visit_date`
  nor `checked_in_at` is indexed.
- **Realtime today.** No SSE or websocket transport exists. The web portal
  polls each dashboard every 15 s (`use-polling.ts`):
  - It keeps polling while the tab is hidden.
  - A failing poll fires an error toast on every tick.
  - It refetches `/auth/me` on every tick, although the layout has already
    loaded the current user.

  The notification center polls the in-app feed every 60 s and pauses while
  the tab is hidden.
- **Web stack.** React 19 and Tailwind v4, with no component or chart
  library. Breakpoints and page tokens come from `responsive-layout` and
  `styles/theme.css`. VMMS_WEB has no unit-test runner. Behaviour is
  verified through the Python Playwright suite in `e2e/` (`npm run e2e`).
- **Reception.** `/reception/dashboard` is a standalone route that wraps its
  own `AppShell` and `ReceptionTopBar`. It has no refresh control and no
  polling. `StaffLayout` already renders `ReceptionSidebar` and the title
  "Reception Desk" for reception users.

## Goals / Non-Goals

**Goals:**
- Every number and chart on a dashboard comes from one live API response.
  The client hardcodes no figures and works out no dates itself; the
  "today" label is the server's `today`.
- Every visible control on the dashboards and their shell does something:
  it navigates, filters, opens a record or refreshes.
- Dashboards feel live without a new transport. They refresh within about
  15 s of a change, and immediately after an invitation notification
  arrives or the tab regains focus.
- Analytics queries stay a bounded number of indexed scans, independent of
  the range length.

**Non-Goals:**
- **A push transport (SSE or websockets).** It is out of scope; polling plus
  event-triggered refetch is enough at current tenant sizes. See Risks.
- **Per-entry re-entry history.** Charts count visitors (one per
  invitation), not every entry. Recording each entry needs a check-in events
  table, which belongs in its own change.
- **Custom date ranges, CSV export of charts, or a separate reports page.**
  Export already exists on the invitations board.
- **Security-gate or kiosk-level breakdowns.**
- **Changing who can see what.** RBAC is unchanged.

## Decisions

### D1. Separate analytics endpoints instead of a fatter overview
`GET /admin/dashboard/analytics` and `/my-analytics` are new endpoints.
Charts change range (7 or 30 days) independently of the KPI tiles, and the
overview stays cheap for the reception desk.

The web fetches the overview and the analytics in parallel on every refresh
tick, so the two cannot drift by more than one tick.

*Alternative considered:* add the series to `overview`. Rejected because a
range switch would refetch the KPIs and preview for no reason, and the
payload would grow on the endpoint other clients (Flutter) poll.

### D2. Additive fields and a deprecation, not a v2
`visitsTodayCount` has the wrong semantics for a dashboard tile: it counts
invitations created today. Changing its meaning is breaking under
api-conventions.md §2. Instead:
- add `scheduledTodayCount`;
- switch the web to it;
- document `visitsTodayCount` as deprecated in `docs/features/dashboard.md`,
  with a removal date 90 days out, and send a `Deprecation` header on
  `overview`.

The `upcomingVisitorCount` fix is not treated as breaking. The spec already
said "not yet checked in"; the count query simply omitted the filter that
the preview applies. Both now share `_upcoming_filters`.

### D3. Aggregation in SQL, zero-filling in Python
Each series is one grouped query:
- `dailyTrend`: group by `preferred_visit_date`, using `COUNT FILTER` for
  checked-in and no-show;
- `hourlyCheckInsToday`: group by
  `extract(hour from checked_in_at AT TIME ZONE :tz)`, limited to today's
  UTC bounds from `_today_bounds_utc`;
- `statusBreakdown`: group by `status`, dated by
  `coalesce(preferred_visit_date, (created_at AT TIME ZONE :tz)::date)`;
- `topPurposes` and `topDepartments`: group by the resolved label.

The service then zero-fills the days, hours and statuses that are missing,
so the client always gets fixed-length arrays and never has to fill gaps.

Labels are resolved with a `LEFT JOIN` to `visit_purposes` and
`departments`, then `coalesce(name, lower(trim(free_text)), 'Not
specified')`. The top 5 and the "Other" row are computed in Python from the
full grouped list, which is small (one row per label).

Five queries per request, each limited by `branch_id` and the range.
*Alternative considered:* `generate_series` joined in SQL. It is equivalent,
but harder to read and test, and gains nothing at a maximum of 30 rows.

The personal endpoint reuses `relevant_to_me_clause` in place of the branch
filter, so it cannot drift from `my-overview` or the `relevantToMe` board.

### D4. Two composite indexes
A tenant migration adds two indexes on `invitations`:
- `ix_invitations_branch_visit_date` on `(branch_id, preferred_visit_date)`;
- `ix_invitations_branch_checked_in_at` on `(branch_id, checked_in_at)`.

Both are `postgresql_where deleted_at IS NULL`. The personal query filters on
`host_id` and `poc_user_id`, which are already indexed.

Use a generated revision id, and confirm `alembic -c alembic_tenant.ini
heads` shows one head before the PR. Both of these failure modes have bitten
this repo before.

### D5. Host names on the server
`hostFullName` comes from a `LEFT JOIN users` (or `joinedload` on the host
relationship, if one exists) in the upcoming and check-ins queries. That
removes the web's `GET /auth/employees?pageSize=100` call from all three
dashboards, along with its silent wrong result past 100 hosts.

### D6. "Realtime" = visibility-aware polling plus event-triggered refetch (web)
`usePolling` gains three behaviours:
- It pauses while `document.visibilityState === 'hidden'`.
- It refetches immediately on `visibilitychange` to visible and on window
  `focus`, throttled to at most once per 5 s.
- It exposes a `refreshNow` that the notification center can call.

`NotificationCenterProvider` already sees each new feed item. When an item
references an invitation, it emits a lightweight "invitation activity"
event, and the mounted dashboard refetches on that event.

The 15 s interval stays, per `live-data-refresh`.

*Alternative considered:* SSE from FastAPI with Redis pub/sub. It is the
better long-term transport. It is rejected for now because it adds
infrastructure (long-lived connections through an undecided deployment
target) for a gain of under 15 s.

### D7. Silent-refresh failures degrade quietly
- On the first failed silent poll, show one toast. While polls keep failing,
  mark the top-bar refresh control "Couldn't refresh · retrying". The last
  good data stays on screen.
- On the first success afterwards, clear that state.
- Only the initial load shows the full-page error with "Try again".

This replaces a toast every 15 s during an outage.

### D8. The current user comes from the layout, not each poll
`AdminLayout` and `StaffLayout` already fetch `/auth/me`. They expose the
result through a `CurrentUserContext`, which the dashboard hooks read. The
dashboard's own refresh then fetches only dashboard data: two requests
(overview and analytics), plus the check-ins page on branch-wide
dashboards. This replaces the current four or five.

### D9. Reception moves under `StaffLayout`
`/reception/dashboard` becomes a child of `<Route element={<StaffLayout/>}>`.
It then inherits:
- the shared top bar with its refresh control and "Reception Desk" title;
- `RefreshProvider`;
- the current-user context.

Its role guard stays in the page hook. `ReceptionTopBar` is deleted if
nothing else uses it.

Admin and reception render one shared `BranchDashboard` component, because
they show the same branch-wide data. Staff renders `PersonalDashboard`.

### D10. Recharts, lazy-loaded, themed from tokens (web)
Add `recharts`, imported only by the chart components. The dashboard routes
are already lazy-loaded through the router; confirm this, and if they are
not, wrap the chart cards in `React.lazy` so the library stays out of the
public-portal bundle.

Chart rules:
- **Colours** come from `theme.css` tokens, read once through
  `getComputedStyle`, so a brand change flows through. Status colours reuse
  the status-pill palette, so "Checked in" is the same colour on the board
  and in the status breakdown.
- **Size.** Each chart sits in a `ResponsiveContainer` with a fixed height
  per breakpoint: 220 px on phone, 260 px at `md`, 280 px at `lg`.
- **Phones.** Below `sm`, the 30-day trend thins its x-axis ticks and hides
  the legend in favour of a single summary line.
- **Accessibility.** Every chart has an `aria-label` summary, such as
  "Last 7 days: 42 scheduled, 37 checked in, 5 no-shows", and a visually
  hidden `<table>` with the same rows.
- **Empty data.** All-zero data renders the shared empty state, not an
  empty axis.
- **Tooltips** work on tap as well as hover.

*Alternative considered:* hand-built SVG. The user chose Recharts.

### D11. Dashboard layout (web)
The order and column spans at `lg`, on a 12-column grid. Phones get one
column, and `md` gets two columns where noted.

**Branch dashboard** (admin and reception):
1. Greeting row: the server's `today`, a range toggle (7d / 30d) and, for
   admins with more than one branch, a branch selector that sets `branchId`.
2. KPI row (4 tiles). Each tile is a link, and each carries one live
   secondary line:
   - **Expected today**: `scheduledTodayCount`, plus "N checked in so far".
   - **On-site now**: `checkedInCount`.
   - **Pending approval**: the count, plus "oldest waiting 2 h", taken from
     `oldestPendingSubmittedAt`.
   - **Upcoming**: the count.
3. Visitor traffic trend (area chart, span 8) and status breakdown (bars,
   span 4).
4. Arrivals today by hour (bars, span 6; the current hour is highlighted)
   and top purposes and departments (span 6, with a two-tab ranked-bar
   card).
5. Recent check-ins (span 7) and upcoming visitors (span 5). Rows open the
   record. Each card has a working "View all".

**Personal dashboard** (staff):
1. Greeting row.
2. Four KPI tiles, each a link.
3. "My visits" trend (span 8) and "My visits by status" (span 4).
4. My upcoming visitors (full width), with a "View all" link.

### D12. Every control has a destination (web)
- **KPI tiles and "View all" links** go to the invitations board with a
  `?status=` deep link:
  - "Pending" → `submitted`
  - "On-site" → `checked_in`
  - "Upcoming" → `approved`
  - "Expected today" → `approved` (plus `visitDate=today`, if the board's
    filter supports it; otherwise `approved`)
  - "View all" on recent check-ins → `checked_in`

  Admins go to `/admin/invitations` and staff and reception go to
  `/staff/invitations`. The board hook reads `status` from the URL into its
  existing `statusFilter` once on mount, the same way as `?invitationId=`.
- **Rows and chart elements:**
  - Upcoming and check-in rows open the invitation through
    `?invitationId=`.
  - Clicking a status bar deep-links to its status. (The breakdown was
    planned as a donut; the VMMS_WEB design.md W7 explains the switch.)
  - Clicking a trend point does nothing. Its tooltip is the interaction, so
    it is not presented as a button.
- **Removed:** "Help & Support" (the user chose removal).
- **Sidebar footer:** the "v1.2 Active" label and its green dot imply a
  health check that does not exist. They are replaced by the build
  identifier, `v{package.json version} · {VITE_BUILD_SHA}`, which Vite
  injects through `define`. When neither is available the footer is hidden.

Done means every `<button>` and `<a>` rendered on the three dashboards and
in their shell has a handler or a route that exists in `App.tsx`. A
Playwright test clicks each one and asserts that the URL or the page state
changed.

## Risks / Trade-offs

- **[Re-entries are invisible to the charts]** The arrivals and trend charts
  count one arrival per invitation, at the most recent check-in time. →
  Document this in the chart's tooltip footnote and in `dashboard.md`. A
  check-in events table is the follow-up if accurate per-entry counts are
  needed.
- **[Polling load]** Each open dashboard sends 2–3 requests every 15 s, and
  analytics runs five grouped queries. → D4's indexes keep these as index
  range scans. Hidden tabs stop polling (D6). If load still matters, add a
  10 s Redis cache keyed `vmss:{tenant_id}:dashboard:analytics:{scope-hash}:{range}`.
  This is not built up front.
- **[Free-text purpose labels fragment]** "Meeting" and "meeting " are
  merged by `lower(trim())`, but synonyms are not. → This is acceptable: the
  configured picklist is the primary source, and free text is the fallback.
- **[Deprecated field lingers]** Flutter may read `visitsTodayCount`. → The
  field stays for at least the 90-day window in D2, and the `Deprecation`
  header advertises the change.
- **[Bundle size]** Recharts adds about 100 KB gzipped. → It is loaded only
  with the dashboard routes (D10).
- **[Stale test DB]** The new indexes don't affect conftest's `create_all`
  on columns, but drop `vmss_test` if tests disagree with the migration.

## Migration Plan

1. API: run the migration with `alembic_tenant upgrade` for every tenant
   (locally only `tenant_default`). Deploy the API. Every change is
   additive, so the old web keeps working.
2. Web: deploy after the API. It reads the new fields and endpoints.
3. Rollback: revert the web first, then the API. The index migration's
   `downgrade` drops both indexes.

## Open Questions

- The `package.json` version is `0.0.0`. The footer shows whatever it is set
  to. Bumping it to a real release number is a release-process decision and
  can happen independently.
