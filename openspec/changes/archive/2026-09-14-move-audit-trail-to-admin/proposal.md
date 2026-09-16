## Why

The Audit Trail is currently a staff-portal tab (`/staff/audit-trail`) scoped to each individual staff member's own hosted visitors. Audit history is sensitive, organisation-wide information — it should live in the Admin portal and be visible only to admins, not to every authenticated staff member.

## What Changes

- **BREAKING**: Remove the "Audit trail" tab, page, and route from the staff portal. Staff members lose the ability to view any audit trail from `/staff/dashboard` — the "Audit trail" sidebar item and the `/staff/audit-trail` route are deleted.
- Add a new "Audit Trail" item to the Admin sidebar and a new page at `/admin/audit-trail`, showing the **full**, organisation-wide activity log (not scoped to a single host) — summary stats, filters, search, pagination, and report download, matching the depth of the page it replaces.
- Restrict `/admin/audit-trail` to admins only: the system SHALL check the signed-in user's admin status (via the current-user response's `isAdmin` flag) before rendering the page, and SHALL redirect a non-admin authenticated user away instead of rendering the page. This is a new frontend enforcement pattern — today every `/admin/*` route is reachable by any authenticated token regardless of role.

## Capabilities

### New Capabilities
- `admin-audit-trail`: Admin-only, organisation-wide Audit Trail page at `/admin/audit-trail` — summary stats, date-range/activity-type/search filters, paginated activity log, report download, and an admin-only access guard.

### Modified Capabilities
- `staff-audit-trail`: The capability is removed — the Audit Trail page and its `/staff/audit-trail` route no longer exist for staff members.
- `staff-dashboard`: The "Audit trail" sidebar navigation item and the "'Audit trail' opens the Audit Trail page" requirement are removed from the staff dashboard sidebar.

## Impact

- **Affected code**:
  - `src/App.tsx` — remove the `/staff/audit-trail` route; add `/admin/audit-trail`.
  - `src/presentation/pages/staff-audit-trail/**` — removed (page, hooks, components).
  - `src/presentation/components/DashboardSidebar.tsx` — remove the `audit-trail` nav item and its `'staff-audit-trail'` union member.
  - `src/presentation/components/AdminSidebar.tsx` — add an `audit-trail` nav item, union member, and `/admin/audit-trail` navigation target.
  - New `src/presentation/pages/admin-audit-trail/**` (page, hooks, components) — reusing the existing `GetAuditTrailUseCase`, `RequestAuditReportUseCase`, `GetAuditReportUseCase`, `DownloadAuditReportUseCase`, and `AuditTrailRepository` port (`src/data/use-cases/*`, `src/data/repositories/audit-trail-repository.ts`, `src/infrastructure/audit-trail-repository.ts`) — no `data/`, `domain/`, or `infrastructure/` changes are needed for the underlying audit-trail data flow itself.
  - `src/domain/entities/staff-user-schema.ts` / `GetCurrentStaffUserUseCase` — reused as-is (`isAdmin` already exists) to gate the new page.
  - `openspec/specs/staff-audit-trail/spec.md` — all requirements removed.
  - `openspec/specs/staff-dashboard/spec.md` — sidebar and "Audit trail" navigation requirements updated.
  - `openspec/specs/admin-audit-trail/spec.md` — new.
- **Not affected**: the underlying `/audit-trail` and `/audit-trail/reports*` API endpoints, their Zod schemas, the repository port, and the use cases — this change is presentation-layer only (which portal exposes the page, and who can reach it).
