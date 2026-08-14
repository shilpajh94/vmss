## Why

Staff can already see the "Audit trail" item in the dashboard sidebar, but it is inert per the current `staff-dashboard` spec. Hosts and tenant admins have no way to review the history of check-ins, rejections, modifications, and flagged incidents for the visitors they host. The Figma design (`node-id=62-1532`, "host-audit-trail") defines a complete Audit Trail page — stats, filters, and an activity log table — that should replace that dead nav item.

## What Changes

- Add a new Audit Trail page at `/staff/audit-trail`, reachable by activating "Audit trail" in the shared staff sidebar.
- Wire the sidebar's "Audit trail" item (currently a no-op) to navigate to the new page.
- Show three summary stat cards — Total Check-ins, Denied Entries, Overstayed Visits — scoped to the signed-in staff member's hosted visitors.
- Show a filter bar: a date-range control (defaulting to "Last 30 days"), an activity-type control (defaulting to "All Activities"), and a search-by-visitor-name field.
- Show an activity log table (Timestamp, Activity, Visitor, Description, Zone, Method, Status) with a status pill per row, and pagination ("Showing X-Y of N results" with prev/next).
- Reuse the existing staff shell conventions (auth guard, sidebar, signed-in-user header pattern, sign-out) already established by `staff-dashboard` and `staff-visitor-registration`.

## Capabilities

### New Capabilities
- `staff-audit-trail`: an authenticated staff page showing hosted-visitor activity history — summary stats, filters (date range, activity type, visitor search), a paginated activity log table, and empty/loading/error states.

### Modified Capabilities
- `staff-dashboard`: the "Audit trail" sidebar item changes from inert to navigating to the new Audit Trail page, narrowing the "other nav items are inert" requirement to just "Help & Support" (both "My actions" and "Audit trail" now have destinations).

## Impact

- **New**: `src/domain/entities/audit-log-entry-schema.ts` (activity row + stats shape), `src/data/api/api-endpoints.ts` gains `LIST_AUDIT_TRAIL`, `src/data/repositories/audit-trail-repository.ts` (port), `src/infrastructure/audit-trail-repository.ts` (adapter), `src/data/use-cases/get-audit-trail.ts` (use case), `src/composition-root.ts` gains `getAuditTrailUseCase`, `src/presentation/pages/staff-audit-trail/**` (page, hook, stat cards, filter bar, activity table, status pill, pagination), new route in `src/App.tsx`.
- **Modified**: `src/presentation/components/DashboardSidebar.tsx` — add the missing navigation branch for `activeItem === 'audit-trail'`.
- **Reused, unmodified**: staff auth-guard pattern (`sessionStorage` token check + redirect to `/staff/login`), `getCurrentStaffUserUseCase` for the header identity, `DashboardSidebar` component itself (no prop-shape change).
