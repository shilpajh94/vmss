## 1. Domain schema

- [x] 1.1 Add `src/domain/entities/dashboard-overview-schema.ts` with `DashboardOverviewSchema` (`kpis`: array of `{ key, label, value, trendCaption, trendDirection: 'up' | 'down' }`; `trafficSeries`: array of `{ day, count }`; `recentCheckins`: array of `{ id, visitorName, hostName, time, badgeNumber, status: 'checked-in' | 'checked-out' }`; `departmentBreakdown`: array of `{ name, count, percentage }` plus `activeDepartmentCount`; `upcomingVisitors`: array of `{ id, time, visitorName, company, hostName, purpose }`) and its `z.infer` type

## 2. API endpoints

- [x] 2.1 Add `GET_ADMIN_DASHBOARD_OVERVIEW` (`GET /admin/dashboard/overview`, `hasToken: true`) to `src/data/api/api-endpoints.ts`
- [x] 2.2 Add `CHECK_IN_UPCOMING_VISITOR` (`PATCH /admin/dashboard/upcoming-visitors`, `hasToken: true`, id passed via query param) to `src/data/api/api-endpoints.ts`

## 3. Repository port, adapter, use cases

- [x] 3.1 Add `src/data/repositories/dashboard-repository.ts` with `DashboardRepository` interface: `getOverview(): Promise<DashboardOverview>`, `checkInUpcomingVisitor(id: string): Promise<void>`
- [x] 3.2 Add `src/infrastructure/dashboard-repository.ts` implementing `DashboardRepository` via `ApiClient.makeRequest` against the new endpoints and `DashboardOverviewSchema`
- [x] 3.3 Add `src/data/use-cases/get-dashboard-overview.ts` (`GetDashboardOverviewUseCase`)
- [x] 3.4 Add `src/data/use-cases/check-in-upcoming-visitor.ts` (`CheckInUpcomingVisitorUseCase`)

## 4. Composition root

- [x] 4.1 Wire `resolveDashboardRepository`, `resolveGetDashboardOverviewUseCase`, `resolveCheckInUpcomingVisitorUseCase` in `src/composition-root.ts` and expose the two use cases on `AppDependencies`

## 5. Shared icons

- [x] 5.1 Add `TrendingUpIcon`, `TrendingDownIcon`, and `CalendarCheckIcon` to `src/presentation/components/icons.tsx`

## 6. Sidebar wiring

- [x] 6.1 In `src/presentation/components/AdminSidebar.tsx`, add a `'dashboard'` case to `handleActivate` that navigates to `/admin/dashboard`

## 7. Page: hook and data flow

- [x] 7.1 Add `src/presentation/pages/admin-dashboard/hooks/use-admin-dashboard.ts`: checks `sessionStorage` token on mount (redirect to `/staff/login` if missing), loads current staff user + dashboard overview, exposes loading/error/retry, and `checkInVisitor(id)` (calls the use case, removes the visitor from local `upcomingVisitors` state on success, toasts success/failure)
- [x] 7.2 Keep overview data and per-row check-in-in-flight state separate so one row's Check In action doesn't block others

## 8. Page: components

- [x] 8.1 Add `src/presentation/pages/admin-dashboard/Components/KpiRow.tsx`: renders the four KPI cards (icon, label, value, trend caption with up/down icon per `trendDirection`)
- [x] 8.2 Add `src/presentation/pages/admin-dashboard/Components/VisitorTrafficChart.tsx`: plain in-repo SVG line/area chart plotting `trafficSeries`, with day labels on the x-axis and gridlines/labels on the y-axis (no charting library, no hover tooltip)
- [x] 8.3 Add `src/presentation/pages/admin-dashboard/Components/RecentCheckinsCard.tsx`: header with inert "View All", table (Name, Host, Time, Badge #, Status) with a Checked In / Checked Out badge, and the shared `EmptyState` when `recentCheckins` is empty
- [x] 8.4 Add `src/presentation/pages/admin-dashboard/Components/DepartmentBreakdownCard.tsx`: per-department label, progress bar (color cycled by index through existing theme tokens), count, and percentage, plus the active-department total footer
- [x] 8.5 Add `src/presentation/pages/admin-dashboard/Components/UpcomingVisitorsCard.tsx`: header with "Pre-Register Visitor" button, list rows (time, visitor name + company, host, purpose, inert "Print Pass", working "Check In"), and the shared `EmptyState` when `upcomingVisitors` is empty

## 9. Page: layout

- [x] 9.1 Add `src/presentation/pages/admin-dashboard/admin-dashboard.tsx`: renders `AdminSidebar` (`activeItem="dashboard"`), `AdminTopBar` (Dashboard description), welcome banner (admin's first name + current date), then `LoadingState`/inline-error-with-retry or the KPI row, traffic chart, `RecentCheckinsCard` + `DepartmentBreakdownCard` side by side, and `UpcomingVisitorsCard`, depending on load state
- [x] 9.2 Wire "Pre-Register Visitor" to navigate to `/staff/visitors/new`

## 10. Routing

- [x] 10.1 Add the `/admin/dashboard` route to `src/App.tsx` rendering the new page

## 11. Verification

- [x] 11.1 Run the dev server and visually compare `/admin/dashboard` against the Figma design (node `253:215`) for layout, spacing, and color fidelity
- [x] 11.2 Manually verify: auth redirect, overview load/error/retry, empty states for Recent Check-ins and Upcoming Visitors, Check In success/failure, inert Print Pass/View All, Pre-Register Visitor navigation, sidebar "Dashboard" navigation from other admin pages
- [x] 11.3 Run lint/type-check and any existing test suite
