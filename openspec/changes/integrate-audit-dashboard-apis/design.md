## Context

See `proposal.md` - Why. Verification against the live backend (its `/openapi.json`, plus authenticated calls) turned up the real contracts for the four endpoints this change touches. All response bodies use the same `{ success, message, data }` envelope already seen in `CompanyResponseSchema` / `StaffLoginResponseSchema` / `InvitationDetailResponseSchema`; the two list endpoints add a sibling `pagination: { page, pageSize, total, totalPages }` next to `data`.

Verified shapes:

- `GET /admin/dashboard/overview` → `{ visitsTodayCount, checkedInCount, pendingApprovalCount, upcomingVisitorCount, upcomingVisitors: [{ id, trackingId, primaryContactFullName, hostId, purposeOfVisit, expiresAt }] }`. No trend data, no traffic series, no department breakdown.
- `GET /admin/dashboard/checkins` (paginated) → rows of `{ id, trackingId, primaryContactFullName, hostId, branchId, status, checkedInAt, checkedOutAt }`. No badge number, no host name (only `hostId`).
- `PATCH /admin/dashboard/upcoming-visitors` → body `{ invitationId }` (not a query param).
- `GET /audit-trail` (paginated; requires a permission the seeded admin role didn't have until granted mid-verification — likely gated similarly to `reports:view`) → rows of `{ id, actorUserId, action, entityType, entityId, createdAt }`. Sampled real data (385 rows) shows `action` is a system-wide machine taxonomy covering config CRUD (`branch_created`, `role_created`, ...), auth (`login`), and invitation lifecycle (`invitation_created`, `walk_in_registration_created`, `invitation_approved`, `invitation_approval_step_approved`, `invitation_checked_in_public`, `invitation_rescheduled`). `actorUserId` is `null` for actions a visitor triggered directly (e.g. `walk_in_registration_created`, `invitation_checked_in_public`).

`hostId` (on both upcoming visitors and check-ins) is a user id, resolvable the same way `use-invitations-board.ts` already resolves hosts: `listHostEmployeesUseCase.execute()` → `Record<id, fullName>`.

**Report download (added mid-implementation, per user request).** `POST /audit-trail/reports` (body: same filters as the list endpoint, plus `formats: ('csv'|'pdf')[]`) enqueues an async job and returns it `202` with `status: "pending"`; `GET /audit-trail/reports/{job_id}` polls it. Initially this 500'd — `relation "tenant_default.audit_report_jobs" does not exist" — fixed by the backend team via `alembic -c alembic_tenant.ini -x tenant_schema=tenant_default upgrade head` (to `dfb1340caf66`) during this change. Verified live afterward: job resolves `pending` → `ready` (not `completed`) in ~1-3s, or `failed`; `status` is a plain string column with no enum, so only these three values are ever written. On `ready`, `csvDownloadUrl`/`pdfDownloadUrl` are populated.

**Known follow-up gap**: `csvDownloadUrl`/`pdfDownloadUrl` come back as bare storage paths (e.g. `var/storage/vmss/<tenant>/audit-trail/reports/<id>.csv`), not fetchable URLs — there is no confirmed static-file route serving them. Tried and confirmed 404 against the real backend: the path as-is from the API origin root, `/storage/...`, `/files/...`, `/media/...`, `/static/...`, `/api/v1/storage/...`, `/api/v1/files/...`. `HttpAuditTrailRepository` resolves the link as `{api origin}/{path}` (the most standard convention) so the plumbing is ready, but the resulting link will 404 until the backend adds a route for it (or the response is changed to return a real URL). This is a backend follow-up, not something fixable from this codebase — flag it the same way the migration gap was flagged.

## Goals / Non-Goals

**Goals:**
- Make `admin-dashboard` and `staff-audit-trail` render exactly what the real backend can supply, with no invented fields and no dummy fallback.
- Keep the wire-envelope handling consistent with the rest of the codebase: the domain schema for each endpoint models the full `{ success, message, data[, pagination] }` response (matching `StaffLoginResponseSchema`'s pattern), and the infra adapter parses that and returns `.data`.
- Give the audit trail's machine-readable `action`/`entityType` taxonomy a legible presentation (humanized labels, resolved actor names) without inventing data the backend doesn't have.

**Non-Goals:**
- Restoring the Visitor Traffic chart or Visitors-by-Department breakdown — no backend endpoint exists for either; out of scope until one does.
- Building a generic action-taxonomy admin/config UI — the curated activity-type filter only covers actions relevant to visitor/invitation activity; the table still renders any other action (humanized as a fallback), it's just not individually filterable.
- Changing who can access `/audit-trail` — that's a backend permission concern; the frontend keeps its existing generic "load failed, retry" handling for a 403 same as any other failure.

## Decisions

**1. Envelope + pagination schemas live in `domain/entities`, adapters parse-and-unwrap.**
For each endpoint, the domain entity file exports the inner payload schema/type (what the rest of the app uses) *and* the outer response schema wrapping it in `{ success, message, data }` (add `pagination` for the two paginated list endpoints) — mirroring `StaffLoginResponseSchema`/`CompanyResponseSchema` exactly. The `Http*Repository` adapter is the only place that sees the outer schema; it parses the full response and returns `.data` (plus `.pagination.total` for paginated ones). Ports and use cases stay envelope-agnostic, per `.claude/rules/data-api-layer.md`.

**2. Dashboard overview KPIs are the four real counts, no trend captions.**
`DashboardKpi` becomes `{ key, label, value }` — no `trendCaption`/`trendDirection`, since the backend has no trend/comparison data. The hook derives the four `DashboardKpi` values from `visitsTodayCount`, `checkedInCount`, `pendingApprovalCount`, `upcomingVisitorCount` — no separate mapping needed in the repository/schema layer; `DashboardOverviewSchema` stops including a `kpis` field at all and instead exposes the four counts directly, and `useAdminDashboard` builds the `KpiRow` input from them. `KpiRow.tsx` drops its trend-arrow rendering.
Alternative considered: keep `kpis` as an array shape for UI-code symmetry with today's `KpiRow` — rejected because it would mean inventing an array wrapper around four fixed, always-present fields for no benefit; a plain object is simpler and equally typed.

**3. Recent Check-ins comes from a second endpoint (`GET /admin/dashboard/checkins`), fetched alongside the overview.**
Add `LIST_DASHBOARD_CHECKINS` to `API_ENDPOINTS` and a `listRecentCheckins()` method on `DashboardRepository`/`HttpDashboardRepository`. `useAdminDashboard.loadOverview` fetches overview + recent-checkins + host employees in parallel (`Promise.all`, matching the pattern already used in `use-invitations-board.ts`), and a checkins-fetch failure is treated the same as an overview-fetch failure (existing error path) rather than a separate silent-partial state, to keep the failure model simple and already-spec-compliant.
`DashboardRecentCheckin` becomes `{ id, visitorName, hostId, checkedInAt, checkedOutAt }`; display status ("Checked In" vs "Checked Out") is derived client-side from whether `checkedOutAt` is set, since the raw `status` string's exact vocabulary isn't guaranteed. Badge number is dropped (no such field).

**4. Upcoming Visitors and Check-in fields follow the real `UpcomingVisitorOut`/`DashboardCheckInRequest` shapes.**
`DashboardUpcomingVisitor` becomes `{ id, trackingId, visitorName (primaryContactFullName), hostId, purpose (purposeOfVisit, nullable), expiresAt }` — drop `company` (not available) and rename the displayed time from a scheduled visit time to the invitation's expiry, labeled accordingly in the UI so it isn't misread as a start time. `checkInUpcomingVisitor(invitationId)` sends `{ invitationId }` as the request body instead of `id` as a query param.

**5. Host names are resolved the same way the invitations board already does it.**
`useAdminDashboard` additionally calls `listHostEmployeesUseCase.execute()` and builds an `employeeNameById` map, passed down to `RecentCheckinsCard`/`UpcomingVisitorsCard` for display; a `null`/unresolved `hostId` renders as "Unassigned".

**6. `staff-audit-trail` is rebuilt around the real actor/action/entity log; summary stats and visitor-name search are dropped.**
- `AuditLogEntry` becomes `{ id, actorUserId, action, entityType, entityId, createdAt }` (wire-shaped, no display formatting in the schema).
- A small presentation-side lookup (`ACTION_LABELS` in `ActivityTable.tsx` or a co-located util) humanizes known actions (e.g. `invitation_checked_in_public` → "Checked In") and falls back to a generic snake_case→Title Case conversion for anything not explicitly mapped, so unrecognized future actions still render legibly instead of breaking.
- The actor column resolves `actorUserId` via the same `listHostEmployeesUseCase` → `employeeNameById` map used on the dashboard (fetched once in `useStaffAuditTrail`), showing "System" when `actorUserId` is `null` (the two null-actor actions observed, `walk_in_registration_created` and `invitation_checked_in_public`, are both visitor-self-service actions with no staff actor).
- The activity-type filter (`ACTIVITY_TYPE_OPTIONS` in `types.ts`) is curated to the confirmed, visitor-relevant action values (`invitation_created`, `walk_in_registration_created`, `invitation_approved`, `invitation_approval_step_approved`, `invitation_checked_in_public`, `invitation_rescheduled`) plus "All Activities" — it does not attempt to enumerate the full system-wide taxonomy (config/CRUD/auth actions still show up under "All Activities" via the fallback label, just aren't individually filterable).
- `AuditTrailFilters` drops `search` (no visitor-name field exists on the resource); `AuditFilterBar` drops its search input; `SummaryStatCard` and the stats row are removed entirely (no backend aggregate for check-ins/denials/overstays); `StatusPill` is removed (no discrete status field — the humanized action label communicates what happened).
- `ActivityTable` columns become Timestamp | Action | Actor | Entity Type (was Timestamp | Activity | Visitor | Description | Zone | Method | Status).
- `LIST_AUDIT_TRAIL`'s endpoint path changes to `/audit-trail`; the date-range filter keeps its existing UI (Last 7/30/90 days, All time) and is translated to `createdAfter` in the adapter, same abstraction boundary as before.

## Risks / Trade-offs

- [The curated activity-type list may miss an action value that matters to a real user] → Mitigation: "All Activities" always shows every entry via the fallback humanizer, so nothing is hidden — only individual filtering by an uncurated action is unavailable; the list can be extended later without a schema change.
- [Deriving check-in/check-out status from `checkedOutAt` presence rather than trusting the `status` string could diverge if the backend's `status` vocabulary is richer (e.g. a "flagged" or "overstayed" state)] → Mitigation: only two states are observable in the current data (`checked_in` with `checkedOutAt: null`); revisit if a third status value is seen in practice.
- [Dropping visitor-name search and per-host stats is a real feature reduction relative to what `staff-audit-trail`'s original spec promised] → Mitigation: this is the explicit, agreed trade-off for this change (see proposal.md) — the backend simply doesn't expose a per-visitor, per-host audit resource; documented in the delta spec's REMOVED requirements with a stated reason.
- [The `/audit-trail` permission gate is inconsistent with "any authenticated staff member" per the current spec's auth requirement] → Mitigation: not changed here — a 403 falls through the existing generic "list load failure" error/retry path, which is accurate (if unhelpful-worded) behavior; a friendlier "you don't have access" message is a follow-up, not required for this change.

## Migration Plan

No data migration. Deploy is: merge the already-updated `.env.example`/`vite.config.ts`, ship the schema/adapter/hook/UI changes together (they're not independently deployable — the UI depends on the new schema shapes). Rollback is a plain revert.
