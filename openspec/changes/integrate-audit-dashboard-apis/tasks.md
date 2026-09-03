## 1. Endpoints

- [x] 1.1 Change `LIST_AUDIT_TRAIL` in `src/data/api/api-endpoints.ts` to `{ endpoint: '/audit-trail', method: 'GET', hasToken: true }`
- [x] 1.2 Add `LIST_DASHBOARD_CHECKINS: { endpoint: '/admin/dashboard/checkins', method: 'GET', hasToken: true }` to `API_ENDPOINTS`

## 2. Dashboard overview schema and adapter

- [x] 2.1 Rewrite `src/domain/entities/dashboard-overview-schema.ts`: `DashboardKpiSchema` becomes `{ key, label, value }` (no trend fields); `DashboardUpcomingVisitorSchema` becomes `{ id, trackingId, visitorName, hostId (nullable), purpose (nullable), expiresAt }`; `DashboardOverviewSchema` becomes `{ visitsTodayCount, checkedInCount, pendingApprovalCount, upcomingVisitorCount, upcomingVisitors }`; remove `DashboardTrafficPointSchema`, `DashboardDepartmentBreakdownSchema`, and the `trafficSeries`/`departmentBreakdown`/`activeDepartmentCount`/`recentCheckins` fields; add `DashboardOverviewResponseSchema = { success, message, data: DashboardOverviewSchema }`
- [x] 2.2 Rewrite `DashboardRecentCheckinSchema` (in the same file or a new `dashboard-checkin-schema.ts`) as `{ id, visitorName, hostId (nullable), checkedInAt (nullable), checkedOutAt (nullable) }`; add a paginated response schema `{ success, message, data: DashboardRecentCheckinSchema[], pagination: { page, pageSize, total, totalPages } }`
- [x] 2.3 Update `src/data/repositories/dashboard-repository.ts`: `getOverview(): Promise<DashboardOverview>` stays; add `listRecentCheckins(): Promise<DashboardRecentCheckin[]>`; change `checkInUpcomingVisitor(invitationId: string): Promise<void>`
- [x] 2.4 Update `src/infrastructure/dashboard-repository.ts`: `getOverview` parses `DashboardOverviewResponseSchema` and returns `.data`; add `listRecentCheckins` calling `LIST_DASHBOARD_CHECKINS`, parsing the paginated envelope, returning `.data`; `checkInUpcomingVisitor` sends `body: { invitationId }` (drop `queryParams`)

## 3. Dashboard hook and UI

- [x] 3.1 In `src/presentation/pages/admin-dashboard/hooks/use-admin-dashboard.ts`: fetch `getDashboardOverviewUseCase.execute()`, a new `listRecentCheckinsUseCase` (or call the repository method directly via a new use case — follow the existing use-case-per-operation pattern), and `listHostEmployeesUseCase.execute()` together (`Promise.all`); build `employeeNameById` the same way `use-invitations-board.ts` does; build the four `DashboardKpi` entries from the raw counts; store recent check-ins and upcoming visitors alongside the resolved host map
- [x] 3.2 Add `ListRecentCheckinsUseCase` in `src/data/use-cases/` (constructor-injected `DashboardRepository`, `execute()` delegates to `listRecentCheckins()`) and wire it in `composition-root.ts` (`AppDependencies` + resolver), following the existing pattern for `getDashboardOverviewUseCase`
- [x] 3.3 Update `checkInVisitor` to call `checkInUpcomingVisitorUseCase.execute(invitationId)` (parameter renamed for clarity, same use case)
- [x] 3.4 Update `KpiRow.tsx`: drop trend-arrow rendering and `trendCaption`; keep the icon-per-key mapping for the four new keys
- [x] 3.5 Update `RecentCheckinsCard.tsx`: columns become NAME, HOST, TIME, STATUS (drop BADGE #); resolve host name from `employeeNameById` (fallback "Unassigned"); derive Checked In/Checked Out from `checkedOutAt`; format `checkedInAt` for display
- [x] 3.6 Update `UpcomingVisitorsCard.tsx`: use `visitorName`/`hostId` (resolved via `employeeNameById`, fallback "Unassigned")/`purpose` (fallback when null)/`expiresAt` (formatted, labeled as expiry not a scheduled time); drop `company`
- [x] 3.7 Delete `VisitorTrafficChart.tsx` and `DepartmentBreakdownCard.tsx` and remove their usage from `admin-dashboard.tsx`
- [x] 3.8 Add a small shared time-formatting helper (e.g. `src/presentation/utils/format-time.ts`) used by both `RecentCheckinsCard` and `UpcomingVisitorsCard`

## 4. Audit trail schema and adapter

- [x] 4.1 Rewrite `src/domain/entities/audit-log-entry-schema.ts`: `AuditLogEntrySchema = { id, actorUserId (nullable), action, entityType, entityId (nullable), createdAt }`
- [x] 4.2 Rewrite `src/domain/entities/audit-trail-response-schema.ts`: drop `AuditTrailStatsSchema`/`stats`; `AuditTrailResponseSchema = { items: AuditLogEntrySchema[], total: number }` (payload-only, as consumed by the hook); add `AuditTrailPaginatedResponseSchema = { success, message, data: AuditLogEntrySchema[], pagination: { page, pageSize, total, totalPages } }` for the adapter to parse
- [x] 4.3 Update `src/data/repositories/audit-trail-repository.ts`: `AuditTrailFilters` drops `search`
- [x] 4.4 Update `src/infrastructure/audit-trail-repository.ts`: `list()` sends `createdAfter` (derived from `dateRange`) and `action` (derived from `activityType`, omitted when "all") as query params instead of `dateRange`/`activityType`/`search`; parses `AuditTrailPaginatedResponseSchema` and returns `{ items: data, total: pagination.total }`

## 5. Audit trail hook and UI

- [x] 5.1 In `src/presentation/pages/staff-audit-trail/types.ts`: replace `ACTIVITY_TYPE_OPTIONS` with the curated real action values (`invitation_created`, `walk_in_registration_created`, `invitation_approved`, `invitation_approval_step_approved`, `invitation_checked_in_public`, `invitation_rescheduled`) and matching labels; keep `DATE_RANGE_OPTIONS` as-is
- [x] 5.2 In `use-staff-audit-trail.ts`: remove `stats`/`AuditTrailStats` state and the `search`/`debouncedSearch`/`changeSearch` handling; add `listHostEmployeesUseCase.execute()` alongside the existing loads to build `employeeNameById`; pass filters as `{ dateRange, activityType, page, pageSize }`
- [x] 5.3 Add an action→label humanizer (explicit map for the curated actions plus a snake_case→Title Case fallback) and an actor-resolution helper (via `employeeNameById`, falling back to "System" when `actorUserId` is null); place in `ActivityTable.tsx` or a small co-located util
- [x] 5.4 Rewrite `ActivityTable.tsx`: columns become Timestamp | Action | Actor | Entity Type, using the humanizer/resolver from 5.3
- [x] 5.5 Delete `StatusPill.tsx` and `SummaryStatCard.tsx`; remove the stats row and search input from `staff-audit-trail.tsx` and `AuditFilterBar.tsx`

## 6. Dummy-overview cleanup (already done)

- [x] 6.1 `DUMMY_OVERVIEW` fallback removed from `use-admin-dashboard.ts`
- [x] 6.2 Overview-fetch failure now sets `errorMessage` + fires `toast.error`

## 7. Verification

- [x] 7.1 `npx tsc --noEmit` passes with no errors
- [x] 7.2 Manually load `/admin/dashboard` against the live backend and confirm the KPI row, recent check-ins, and upcoming visitors render real data with resolved host names
- [x] 7.3 ~~Manually confirm "Check In" on an upcoming visitor succeeds end-to-end~~ — superseded by task 8 (Check In removed from the page entirely as a product decision)
- [x] 7.4 Manually load the Audit Trail page and confirm the activity log renders real entries with humanized actions and resolved/"System" actors, that the curated activity-type filter narrows correctly, and that "All Activities" still shows uncurated actions
- [x] 7.5 Confirm pagination ("Showing X-Y of Z results", next/prev) works against the real `/audit-trail` response

## 8. Upcoming Visitors card made informational-only (post-review follow-up)

- [x] 8.1 Replace the "Expires" clock-icon time display with a plain date (`formatDate` added to `format-time.ts`)
- [x] 8.2 Remove "Print Pass" and "Check In" buttons from `UpcomingVisitorsCard.tsx`; remove "Pre-Register Visitor" from the card header
- [x] 8.3 Remove `checkingInIds`/`checkInVisitor`/`onPreRegister` from `use-admin-dashboard.ts` and `admin-dashboard.tsx`
- [x] 8.4 Delete `CheckInUpcomingVisitorUseCase`, its `DashboardRepository` port method and adapter implementation, its `composition-root.ts` wiring, and the `CHECK_IN_UPCOMING_VISITOR` endpoint — all now fully unused
- [x] 8.5 Update the `admin-dashboard` delta spec: move "Check In on an upcoming visitor checks them in" and "Pre-Register Visitor opens the Register Visitor wizard" to REMOVED; split "Print Pass and View All are presented but not yet functional" into a REMOVED (Print Pass) + ADDED (View All alone)
- [x] 8.6 Verify with `tsc --noEmit`, lint, and a live browser check (screenshot, no console errors)

## 9. Audit trail report download (post-review addition)

- [x] 9.1 Add `AuditReportJobSchema`/`AuditReportJobResponseSchema` (`src/domain/entities/audit-report-job-schema.ts`)
- [x] 9.2 Add `REQUEST_AUDIT_REPORT` (`POST /audit-trail/reports`) and `GET_AUDIT_REPORT` (`GET /audit-trail/reports/:jobId`) to `API_ENDPOINTS`
- [x] 9.3 Extend `AuditTrailRepository` port with `requestReport(filters, formats)` / `getReport(jobId)`; implement in `HttpAuditTrailRepository`, resolving `csvDownloadUrl`/`pdfDownloadUrl` against the API origin (see design.md's known gap — backend doesn't yet serve these paths)
- [x] 9.4 Add `RequestAuditReportUseCase` / `GetAuditReportUseCase`; wire into `composition-root.ts`
- [x] 9.5 Add `downloadReport(format)` to `use-staff-audit-trail.ts`: request → poll `GET_AUDIT_REPORT` every 1s (up to 20 attempts) until `ready`/`failed`, open the download link or toast the error
- [x] 9.6 Add "Download CSV"/"Download PDF" controls to `AuditFilterBar.tsx` with a per-format preparing/disabled state
- [x] 9.7 Verify against the live backend: confirmed `POST` → `pending` → poll → `ready` with populated download URLs (after the backend's `audit_report_jobs` migration was applied); confirmed the resulting download link itself 404s (backend gap, documented, not blocking this task since the request/poll/UI plumbing is correct and ready for when it's fixed)
- [x] 9.8 Update `staff-audit-trail` delta spec: add "Staff can download the filtered activity log as a report" (ADDED)
