## Why

Reception, security and admins can see a visit's current status but not how it got there. "Who approved it, when was ID checked, was the badge reprinted, which notifications went out" is scattered across `audit_logs`, `badge_prints` and `notifications`, with no single ordered view. The emergency and dispute flows both need one read-only, chronological history per visit.

This is the parent task "Visitor Timeline" (subtasks 2.2–2.5). Decision with the user: no `TIMELINE_ENABLED` feature flag is needed, so subtask 2.1's flag is dropped; the endpoints are gated by permission only.

## What Changes

- Add the timeline event model: a fixed set of event types (invited, approved, denied, approval reverted, ID verified, photo captured, checked in, checked out, badge printed, badge reprinted, notification sent) mapped from existing audit actions, `badge_prints` rows and `notifications` rows.
- Add one read query that merges `audit_logs`, `badge_prints` and `notifications` for a visit into a single, SQL-sorted, SQL-paginated result, with actors resolved in one batched lookup (no N+1).
- Add `GET /api/v1/visitors/{visitor_id}/timeline` and `GET /api/v1/invitations/{invitation_id}/timeline`: pagination, date-range filter, whitelisted sort, `PaginatedEnvelope`, permission-gated, PII masked.
- Add permission `timeline:view`.
- Add tests (ordering, permission-denied, tenant isolation) and `docs/features/timeline.md`.

Additive only. No existing endpoint, table or response shape changes.

## Capabilities

### New Capabilities
- `visit-timeline`: event types and their sources, the merged read query, the two timeline endpoints, pagination/filter/sort rules, permission and PII-masking rules.

### Modified Capabilities
- `auth`: new `timeline:view` permission and its default role grants.

## Impact

- Code: new `src/vmss_api/timeline/` feature package (router, service, repository, schemas), registered in `api.py` and `_TAGS_METADATA`; small edit to `auth/rbac_catalog.py`.
- Database: no new tables. A tenant migration grants `timeline:view` to existing roles. One optional index (see design.md Decision 4) if the notifications lookup by `invitation_id` is not already covered (it is: `ix_notifications_invitation_id`).
- API: two new read endpoints. Additive, no breaking change.
- Config: none.
- Docs: `docs/features/timeline.md`.
- Frontend (separate repos): portal visit-detail and visitor-detail timeline panels.

## Out of scope

- **Zone entry/exit and overstay events.** The repo has no zones, `access_control` package or overstay detection, so these have no data source. Decision with the user: omit both now; add the event types when those features land.
- Writing new audit rows or changing what is audited; the timeline reads existing data only.
- Real-time streaming/push of timeline events.
- A feature flag (dropped by decision).

## Open items to confirm before apply

- **Visitor id scope.** There is no visitors master table. Per the user, `{visitor_id}` is `invitation_visitors.id`. Those rows exist only for co-visitors of `group` invitations; an `individual` invitation's primary contact has no such id, so it is reachable only via the invitation endpoint. Confirm that is acceptable, or decide on an alias for primary contacts.
- **`timeline:view` role grants.** Proposed: Admin, Reception, Security. Confirm.
- **Task 2.3 names `visit_info` as a source.** The `visit_info` package holds visit purposes and durations only, not visit events. This design reads visit milestones from `audit_logs` instead. Confirm that matches intent.
