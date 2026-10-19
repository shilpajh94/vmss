## Context

The full design is shared with the API half of this change:
`VMSS_API/openspec/changes/archive/2026-10-16-live-dashboards-and-analytics/design.md`.
- D1–D5 are the API contract: analytics endpoints, additive fields,
  aggregation and host names.
- D6–D12 are the web decisions summarised below. Read that file first; this
  one only records what is specific to how VMMS_WEB is built.

The current web state, from an audit of the code on 2026-10-16:
- **Dead controls:** "View All" on `RecentCheckinsCard` has no `onClick`
  (shared by admin and reception). "Help & Support" in `DashboardSidebar`
  has no handler.
- **Static content:**
  - `AdminSidebar` footer: a hardcoded "v1.2 Active".
  - `TODAY_LABEL`: computed at module load in all three dashboard pages.
- **Wrong date:** `UpcomingVisitorsCard` shows `expiresAt` as the visit
  date.
- **Host names:** resolved from `GET /auth/employees?pageSize=100`.
- **Refresh:**
  - `use-polling.ts` is a bare `setInterval` with no visibility handling.
  - The Reception dashboard has no polling and no refresh control.
  - A failing silent poll fires a toast every 15 s.
- **Board filter:** the invitations board reads `?invitationId=` once on
  mount, but keeps `statusFilter` in local state only.
- **Charts and routes:** there is no chart library. Routes in `App.tsx` are
  not lazy-loaded.

## Goals / Non-Goals

See the shared design. Web-specific non-goals:
- **No unit-test runner.** VMMS_WEB has none, and adding vitest is out of
  scope. Behaviour is verified with the Playwright suite in `e2e/`, plus
  `tsc -b` and `npm run lint`.
- **No restyle beyond the dashboards.** Other pages keep their layout.
  Shared components that change (KPI tile, cards) are only used by
  dashboards.

## Decisions

### W1. Component structure
- `components/dashboard/` gains `KpiTile` and the reworked `KpiRow`, plus:
  - `ChartCard` (title, actions slot, loading/empty/error states,
    `aria-label` summary, sr-only table);
  - `TrafficTrendChart`;
  - `HourlyArrivalsChart`;
  - `StatusBarsChart` (labeled horizontal bars, not a donut: see the
    dataviz note below);
  - `TopLabelsChart`;
  - `RangeToggle`;
  - `BranchSelect`;
  - `DashboardGrid` (the 12-column grid wrapper; spans are checked by the
    existing `check-grid-spans.mjs` lint).
- `BranchDashboard` renders the admin and reception layout. It takes a
  `boardBasePath` prop: `/admin/invitations` or `/staff/invitations`.
- `PersonalDashboard` renders the staff layout.
- The page components become thin wrappers that pick the variant and the
  base path.

### W2. Data hooks
- `useBranchDashboard({ branchId, range })` replaces `use-admin-dashboard`
  and `use-reception-dashboard`.
- `usePersonalDashboard({ range })` replaces `use-staff-dashboard`.

Each hook:
- reads the current user from `CurrentUserContext` (shared design D8);
- fetches the overview, analytics and (for branch dashboards) check-ins
  with `Promise.all`;
- registers with `usePageRefresh`;
- uses the extended `usePolling` (shared design D6).

A range or branch change re-fetches only the analytics, or everything
respectively, and keeps the other data on screen while loading.

The domain zod schemas (`dashboard-overview-schema.ts`,
`my-dashboard-overview-schema.ts`, `dashboard-checkin-schema.ts`, plus a new
`dashboard-analytics-schema.ts`) are updated so that:
- new fields are required when the API guarantees them;
- `hostFullName` and the visit date and time are nullable.

### W3. Event-triggered refetch
`NotificationCenterProvider` exposes `onInvitationActivity(callback)`. It
fires once per poll that brings in new items carrying an `invitationId`.
`usePolling` subscribes to it through an optional `refetchOn` option, so
board and list pages can opt in later without further changes.

### W4. Board deep link
`use-invitations-board.ts` reads `status` from `useSearchParams` once on
mount, using the same `hasOpened…Ref` pattern as `invitationId`. It
validates the value against the known API statuses before calling
`setStatusFilter`.

### W5. Lazy loading
The three dashboard page components are wrapped in `React.lazy` in
`App.tsx`, and the routes are wrapped in `Suspense` with the existing
`LoadingState` as the fallback. That keeps Recharts out of the public-portal
and login bundle. `npm run build` output is checked to confirm Recharts
lands in a dashboard chunk.

### W6. Build identifier
`vite.config.ts` uses `define` to set:
- `__APP_VERSION__` from `package.json`;
- `__BUILD_SHA__` from `process.env.VITE_BUILD_SHA`, falling back to
  `git rev-parse --short HEAD` when available, else empty.

Both are declared in `vite-env.d.ts`. The Dockerfiles and CI-CD pass
`VITE_BUILD_SHA`.

### W7. Status breakdown is bars, not a donut
The shared design (D10–D12) planned a donut. Running the dataviz palette
validator on the board's six status colours ruled it out. A donut wraps,
so every ordering leaves at least one weak neighbouring pair (checked-out
gray beside checked-in cyan scored a colour-blind ΔE of 4.6 and a
normal-vision ΔE of 10.2), and six slices are past what a donut reads
well. Part-to-whole across six named classes reads best as horizontal
bars. Each bar carries its status name and count, so identity never rests
on colour alone. The bars keep the board's status colours, so a status
looks the same on the dashboard and the board.

The traffic trend uses three categorical hues: blue (scheduled), aqua
(checked in) and orange (no-show). They passed the validator on the white
surface with `--pairs all`. Aqua is below 3:1 contrast against the
surface; the legend, the tooltips and the hidden data table cover that.
Hourly arrivals and top labels are single-series charts in the admin
accent colour.

## Risks / Trade-offs

- **[Recharts and React 19]** Use a Recharts release that supports React 19
  (2.15+ or 3.x). → Pin the exact version that `npm install` resolves, and
  check that `tsc -b` passes before building the charts.
- **[Theme tokens in SVG]** Recharts needs concrete colours, not Tailwind
  classes. → Resolve the CSS variables once with `getComputedStyle` in a
  small `useChartTheme` hook. The brand lint (`check-brand.mjs`) keeps hex
  literals out of the components.
- **[e2e needs data]** Chart and deep-link tests need invitations in several
  states. → Reuse the QA harness seed (`VMSS_API` scripts). Never run it
  alongside API pytest, because they share Redis rate limits.
