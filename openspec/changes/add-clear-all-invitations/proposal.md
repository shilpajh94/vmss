## Why

Admins have no way to wipe a tenant's invitation / visit-request data short of waiting for the retention purge (which only removes rows older than `invitation_retention_days`). Clearing test/demo data or resetting a tenant before go-live currently needs manual SQL, which bypasses backups and audit.

## What Changes

- New admin-only endpoint `POST /api/v1/invitations/clear-all` that permanently removes every invitation in scope for the caller's tenant (all of them by default, or only those whose visit date falls in a chosen date range or month) together with its dependents (visitors, vehicles, QR codes, approval steps, custom-field values).
- Optional scope in the request body, on the invitation's visit date (`preferred_visit_date`): either `fromDate`/`toDate` (inclusive, either bound optional) or `month` (`YYYY-MM`). The two forms are mutually exclusive; no scope means a full clear-all. Invitations with no visit date are never matched by a scoped clear.
- Requires a new RBAC permission `invitations:clear-all`, granted to the Admin role only, plus an explicit confirmation phrase in the request body (`CLEAR ALL INVITATIONS` for an unscoped run, `CLEAR INVITATIONS` for a scoped run, so a scoped request cannot be mistaken for a full wipe).
- Runs as a background Celery task (returns `202` with a job reference), reusing the retention purge's batching, verified gzipped backup, and per-tenant Redis run lock.
- Invitations whose visitor is currently checked in are skipped unless the caller passes `includeCheckedIn: true`, so the emergency "who's inside" report is not wiped by accident.
- One `AuditLog` entry per run (actor, scope, count, backup keys).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `invitations`: adds a requirement for the clear-all operation (permission, confirmation, backup-before-delete, checked-in protection, audit).

## Impact

- `src/vmss_api/invitations/`: `router.py`, `service.py`, `schemas.py`, `tasks.py`, `repository.py` (new `list_ids_for_clear` with optional date filter), `tests.py`.
- `src/vmss_api/auth/rbac_catalog.py`: new `invitations:clear-all` permission + Admin grant; permission catalog seeding/migration for existing tenants.
- `docs/features/invitations.md`, tag/description check for Swagger.
- No schema change, no new dependency, no new settings.
