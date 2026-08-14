## 1. Domain schemas

- [x] 1.1 Add `src/domain/entities/audit-log-entry-schema.ts` with `AuditLogEntrySchema` (timestamp, activity, visitorName, description, zone, method, status) and its `z.infer` type.
- [x] 1.2 Add `AuditTrailStatsSchema` (totalCheckIns, deniedEntries, overstayedVisits) and `AuditTrailResponseSchema` (items: AuditLogEntry[], total, stats) to `src/domain/entities/audit-trail-response-schema.ts`, with their `z.infer` types.

## 2. API endpoint and data layer

- [x] 2.1 Add `LIST_AUDIT_TRAIL` to `API_ENDPOINTS` in `src/data/api/api-endpoints.ts` (`endpoint: "/staff/audit-trail"`, `method: "GET"`, `hasToken: true`).
- [x] 2.2 Add `src/data/repositories/audit-trail-repository.ts` exporting an `AuditTrailRepository` port with `list(filters: AuditTrailFilters): Promise<AuditTrailResponse>` (filters: dateRange, activityType, search, page, pageSize).
- [x] 2.3 Add `src/infrastructure/audit-trail-repository.ts` implementing `AuditTrailRepository`, calling `apiClient.makeRequest` with `API_ENDPOINTS.LIST_AUDIT_TRAIL`, `queryParams` built from the filters, and `parserSchema: AuditTrailResponseSchema`.
- [x] 2.4 Add `src/data/use-cases/get-audit-trail.ts` exporting `GetAuditTrailUseCase`, constructor-injected with `AuditTrailRepository`, `execute(filters)` delegating to `list`.
- [x] 2.5 Wire `resolveAuditTrailRepository` and `resolveGetAuditTrailUseCase` into `src/composition-root.ts`, exposing `getAuditTrailUseCase` on `AppDependencies`.

## 3. Sidebar navigation fix

- [x] 3.1 In `src/presentation/components/DashboardSidebar.tsx`, add the missing navigation branch so activating `'audit-trail'` navigates to `/staff/audit-trail` (mirroring the existing `'my-actions'` branch).

## 4. Routing and page shell

- [x] 4.1 Add route `/staff/audit-trail` in `src/App.tsx` rendering the new `StaffAuditTrailPage`.
- [x] 4.2 Create `src/presentation/pages/staff-audit-trail/staff-audit-trail.tsx`: check for a staff auth token, redirect to `/staff/login` if absent, otherwise render the shared sidebar (`activeItem="audit-trail"`), a page-local workspace header, and the audit trail content.
- [x] 4.3 Create `src/presentation/pages/staff-audit-trail/Components/WorkspaceHeader.tsx`: title "Audit Trail", subtitle "Complete activity log for your hosted visitors", signed-in staff name/role from `getCurrentStaffUserUseCase`, and sign-out — following the identity/sign-out pattern already used in the staff-dashboard header.
- [x] 4.4 Create `src/presentation/pages/staff-audit-trail/hooks/use-staff-audit-trail.ts` managing filter state (dateRange, activityType, search, page), calling `getAuditTrailUseCase.execute(filters)` on mount and whenever filters change (debounced for `search`), and exposing loading/error/data/retry.
- [x] 4.5 Create `src/presentation/pages/staff-audit-trail/types.ts` with the page's filter-state type and any view-model mapping helpers.

## 5. Summary stats

- [x] 5.1 Create `src/presentation/pages/staff-audit-trail/Components/SummaryStatCard.tsx` (label + value) matching the Figma "stat-total-checkins"/"stat-denied-entries"/"stat-overstayed" styling.
- [x] 5.2 Render the three stat cards from `AuditTrailStats` in `staff-audit-trail.tsx`.

## 6. Filter bar

- [x] 6.1 Create `src/presentation/pages/staff-audit-trail/Components/DropdownFilter.tsx` (icon + label + chevron, options list) matching the Figma "date-range"/"activity-type" control styling.
- [x] 6.2 Create `src/presentation/pages/staff-audit-trail/Components/AuditFilterBar.tsx` composing a date-range `DropdownFilter` (default "Last 30 days"), an activity-type `DropdownFilter` (default "All Activities"), and a visitor-name search input, matching the Figma "filter-bar" layout.
- [x] 6.3 Wire `AuditFilterBar`'s changes into `use-staff-audit-trail.ts`'s filter state.

## 7. Activity table and status pill

- [x] 7.1 Create `src/presentation/pages/staff-audit-trail/Components/StatusPill.tsx` mapping each status (Approved, Rejected, Completed, Modified, Flagged) to its pill color, using theme tokens (adding `--color-modified` and a neutral-subtle token to `src/styles/theme.css` for the statuses with no existing token).
- [x] 7.2 Create `src/presentation/pages/staff-audit-trail/Components/ActivityTable.tsx` rendering the header row (Timestamp, Activity, Visitor, Description, Zone, Method, Status) and one row per `AuditLogEntry`, using `StatusPill` for the status column, matching the Figma "activity-table" layout.
- [x] 7.3 Show an empty-state message in `ActivityTable` when the filtered result set is empty.

## 8. Pagination

- [x] 8.1 Create `src/presentation/pages/staff-audit-trail/Components/Pagination.tsx` showing "Showing X-Y of N results" and prev/next controls, matching the Figma "pagination" styling, disabling prev/next at the first/last page respectively.
- [x] 8.2 Wire `Pagination`'s prev/next into `use-staff-audit-trail.ts`'s `page` state, using a fixed page size of 8 to match the Figma.

## 9. Loading and error states

- [x] 9.1 Show a loading state in `staff-audit-trail.tsx` while the initial audit trail request is in flight.
- [x] 9.2 On load failure, show an error message in place of the stats/table and a retry action that re-runs `getAuditTrailUseCase.execute(filters)` without reloading the page.

## 10. Specs housekeeping

- [x] 10.1 Update `openspec/specs/staff-dashboard/spec.md`'s "Other sidebar navigation items" and "Audit trail" behavior per this change's delta spec once implementation lands (handled at archive time; no action needed before then).
