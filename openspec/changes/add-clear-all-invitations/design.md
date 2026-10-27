## Context

The retention purge (`invitations/tasks.py::purge_expired_invitations`, `repository.py::{list_expired_ids, load_rows_for_backup, delete_with_children}`, `retention.py`) already batches, backs up with read-back verification, hard-deletes children-first across the four tables FK'd to `invitations.id`, writes an audit row, and guards runs with a per-tenant Redis lock. Clear-all differs only in selection (everything, or everything within an optional visit-date scope, not "older than cutoff") and in being user-triggered. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:** reuse the purge machinery; make accidental invocation hard; keep the request path non-blocking.

**Non-Goals:** per-branch/status-filtered clearing; soft delete; restore-from-backup tooling; clearing visitors master data, notifications, or audit logs; a UI.

## Decisions

1. **Generalize the purge loop instead of copying it.** Extract the batch loop from `purge_expired_invitations` into a helper taking an id-selector, shared by retention and clear-all. Alternative (duplicate loop) rejected: two copies of backup-before-delete logic would drift.
2. **New repository selector `list_ids_for_clear(limit, include_checked_in, from_date, to_date)`** filtering `preferred_visit_date BETWEEN from_date AND to_date` (either bound optional, inclusive). A bounded scope excludes rows where `preferred_visit_date` is NULL; with no bounds, all rows are selected. The selector with keyset-free `LIMIT` batches (deleted rows drop out of the next query). Soft-deleted rows are included, as in retention.
3. **Background Celery task `clear_tenant_invitations(tenant_id, tenant_schema, actor_user_id, include_checked_in, from_date, to_date, request_id)`; the service converts `month` into the first and last day of that month before enqueuing, so the task only deals with dates**, registered per `background-jobs.md`: idempotent, explicit retry kwargs, ERROR log on exhaustion, request id re-bound. Endpoint calls `.delay()` and returns 202. Alternative (inline delete) rejected: large tenants would time out.
4. **Lock:** reuse `vmss:{tenant_id}:invitations:purge:lock` so clear-all and retention cannot overlap. The endpoint does a non-destructive `SET NX` check is not possible across the handoff, so the task acquires the lock; the endpoint pre-checks `EXISTS` and returns 409 if held (best effort), and the task silently exits if it loses the race.
5. **Permission `invitations:clear-all`** added to `rbac_catalog.py`, granted to Admin only; existing tenants get it via the catalog sync / a data migration consistent with how earlier permissions were added.
6. **Confirmation phrase in body** validated by the Pydantic request schema: `CLEAR ALL INVITATIONS` when no scope is given, `CLEAR INVITATIONS` when a scope is given. The schema also rejects `month` combined with `fromDate`/`toDate`, `fromDate > toDate`, and a `month` not matching `YYYY-MM`. `includeCheckedIn` defaults to `false`.
7. **Audit:** the run's audit row uses `action="invitations_cleared"` with `actor_user_id` set (retention's is `None`) and the `scope` (`{fromDate, toDate}`, or null for all) recorded.
8. **Idempotency-Key** header supported per `api-conventions.md` §3.

## Risks / Trade-offs

- [Irreversible data loss] → permission, confirmation phrase, verified backup, audit, checked-in protection.
- [Scoped runs share the single per-tenant lock] → they serialize with retention and other clears; acceptable.
- [Backups hold PII] → same storage-tier-only handling as retention; no presigned URLs.
- [Long run holds the tenant lock up to 1h TTL] → acceptable; retention simply skips that night and a retry is safe.
- [409 pre-check is racy] → the task re-checks via `SET NX`, so correctness never depends on the pre-check.
