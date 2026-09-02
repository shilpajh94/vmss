## Why

The working tree already points the app at a new backend host (`.env.example` / `vite.config.ts` now target `vmss-new-api.ddev.site:8443` instead of `vmss-dev.mypits.org`). Verifying `staff-audit-trail` and `admin-dashboard` against that live backend (via its OpenAPI spec and authenticated calls) found that both capabilities were built against assumed wire contracts that don't match what the real backend actually serves:

- `GET /admin/dashboard/overview` returns only `{visitsTodayCount, checkedInCount, pendingApprovalCount, upcomingVisitorCount, upcomingVisitors[]}` — no trend captions, no "Average Visit Duration", no 7-day traffic series, and no department breakdown; recent check-ins live on a separate `GET /admin/dashboard/checkins` endpoint. `PATCH /admin/dashboard/upcoming-visitors` (check-in) also takes `{invitationId}` in the request body, not `id` as a query param.
- The real audit trail lives at `GET /audit-trail` (not `/staff/audit-trail`) and is a generic, org-wide actor/action/entity change log (`{id, actorUserId, action, entityType, entityId, createdAt}`) with no visitor name, zone, access method, status pill, or per-host "hosted visitors" stats — a fundamentally different resource than the visitor check-in/deny/overstay activity feed the page currently assumes.

This change narrows both pages to what the real backend can actually supply, so the UI stops rendering hardcoded placeholder data (`DUMMY_OVERVIEW`) or assuming fields that don't exist, and instead shows real data end-to-end — including a redefinition of what "audit trail" means for this app now that it's backed by a system-wide log rather than a per-visitor activity feed.

## What Changes

- Remove the `DUMMY_OVERVIEW` fallback in `use-admin-dashboard.ts`; an overview load failure now shows the existing inline error + retry + toast instead of fake KPI values.
- Rework the `admin-dashboard` KPI row, Recent Check-ins, and Upcoming Visitors sections around the real `overview` + `checkins` endpoints and their real fields; drop the Visitor Traffic chart and Visitors-by-Department breakdown (no backend support), and drop badge number / scheduled-time / company fields that don't exist on the real payload.
- Make the Upcoming Pre-Registered Visitors card informational-only: remove "Print Pass", "Check In", and "Pre-Register Visitor" entirely (product decision made during implementation), and remove the now-fully-unused `checkInUpcomingVisitor` capability end-to-end (endpoint, port method, adapter, use case, composition-root wiring) rather than leaving it as dead code.
- Point `LIST_AUDIT_TRAIL` at the real `/audit-trail` endpoint and rework `staff-audit-trail`'s filters, table columns, and summary section around the real actor/action/entity/timestamp shape: humanized action labels replace the status pill, actor identity replaces visitor name, entity type replaces zone/method, and the per-host "hosted visitors" stats block is removed (no backend aggregate exists for it). Visitor-name search is removed (the resource has no visitor-name field).
- **BREAKING** (internal, pre-release feature): the audit trail page's displayed columns, filters, and summary stats change shape; nothing external depends on the old shape.
- Add report download to `staff-audit-trail`: "Download CSV"/"Download PDF" request a report from the backend's async job endpoints (`POST /audit-trail/reports`, `GET /audit-trail/reports/{job_id}`) using the current filters, poll until the job is `ready` or `failed`, and open the resulting download link. (The backend initially 500'd on this — a missing `audit_report_jobs` migration — fixed during this change; see design.md for a known follow-up gap in how the download link itself resolves.)

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `admin-dashboard`: overview data source, KPI set, Recent Check-ins fields, and Upcoming Visitors fields all change to match the real backend; the Visitor Traffic chart, Visitors-by-Department, Check In, Pre-Register Visitor, and Print Pass requirements are removed (the Upcoming Visitors list becomes informational-only).
- `staff-audit-trail`: the underlying data source changes from an assumed visitor-activity feed to the real org-wide actor/action/entity audit log; activity-type filtering, entry fields, and the status-pill and summary-stats requirements change or are removed accordingly. Visitor-name search is removed. Report download (CSV/PDF) is added.

## Impact

- `src/data/api/api-endpoints.ts` — `LIST_AUDIT_TRAIL` endpoint path
- `src/domain/entities/dashboard-overview-schema.ts`, `src/domain/entities/audit-trail-response-schema.ts`, `src/domain/entities/audit-log-entry-schema.ts` — rewritten to match real payloads
- `src/infrastructure/dashboard-repository.ts`, `src/infrastructure/audit-trail-repository.ts` — new request/response shapes, envelope unwrapping
- `src/data/repositories/dashboard-repository.ts`, `src/data/repositories/audit-trail-repository.ts` — port signatures follow the schema changes
- `src/presentation/pages/admin-dashboard/**` (hook + `KpiRow`, `RecentCheckinsCard`, `UpcomingVisitorsCard`; `VisitorTrafficChart` and `DepartmentBreakdownCard` removed from the page; `UpcomingVisitorsCard` loses its action buttons)
- `src/data/use-cases/check-in-upcoming-visitor.ts` — deleted (no longer called from anywhere)
- `src/presentation/pages/staff-audit-trail/**` (hook + `SummaryStatCard` removed, `AuditFilterBar`, `ActivityTable`, `StatusPill` reworked; `AuditFilterBar` gains Download CSV/PDF controls)
- `src/domain/entities/audit-report-job-schema.ts` (new), `src/data/use-cases/request-audit-report.ts` (new), `src/data/use-cases/get-audit-report.ts` (new) — report job request/poll
- `.env.example`, `vite.config.ts` — already updated in the working tree to the new backend host
