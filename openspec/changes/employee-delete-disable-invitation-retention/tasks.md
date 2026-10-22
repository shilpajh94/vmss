## 1. Employee disable / enable / delete

- [x] 1.1 Add `disabled_by_admin` to `User` (`auth/models.py`) and a tenant Alembic migration in `alembic_tenant/versions/`
- [x] 1.2 Repository: `count_active_admins`, bulk-safe lookup that includes deleted-state checks, and delete-tombstone update in `auth/repository.py`
- [x] 1.3 Service: `disable_employee`, `enable_employee`, `delete_employee` with self-target and last-admin guards (409), idempotent disable/enable, and `tenant_user_index` removal in the same transaction for delete
- [x] 1.4 Change `sync_employee_directory` to not re-enable `disabled_by_admin` employees and to treat deleted emails as new
- [x] 1.5 Router: three endpoints with `require_permission("employees:manage")`, `response_model=Envelope[...]`, `-> JSONResponse`/204, and `record_audit_log` background tasks
- [x] 1.6 Update `docs/features/auth.md` with the new endpoints and sync behaviour

## 2. Invitation retention job

- [x] 2.1 Add `invitation_retention_days`, `invitation_purge_batch_size`, `invitation_purge_hour/minute` to `core/config.py` and `.env.example`
- [x] 2.2 Enumerate every FK referencing `invitations.id` and decide cascade vs. null for each
- [x] 2.3 Repository: `list_expired_ids(cutoff, limit)` (excluding still-checked-in), `load_with_children(ids)` (eager-loaded), `delete_with_children(ids)` single-statement per table in `invitations/repository.py`
- [x] 2.4 Backup writer: gzipped JSONL serializer, save via `core.storage`, read-back verification of record count
- [x] 2.5 `invitations/tasks.py`: `dispatch_invitation_purge` and `purge_tenant_invitations` with retry kwargs, Redis run marker, per-tenant audit entry, ERROR on exhaustion
- [x] 2.6 Register route (`cron_jobs` queue) and `beat_schedule` entry in `core/celery_app.py`
- [x] 2.7 Update `docs/features/invitations.md` and `docs/features/background-jobs.md`

## 3. Tests

- [x] 3.1 Employee tests: happy path for disable/enable/delete, login/token rejection, host-search exclusion, 403 permission-denied, 404, self and last-admin 409, email/code reuse after delete
- [x] 3.2 Tenant-isolation test: employee operations in one tenant schema never touch another's
- [x] 3.3 Sync tests: disabled employee stays disabled; sync-deactivated employee reactivates
- [x] 3.4 Retention tests: old purged, recent kept, checked-in kept, retention unset = no-op, nothing-to-purge creates no backup
- [x] 3.5 Backup tests: backup precedes delete; forced backup failure deletes nothing; verified record count matches
- [x] 3.6 Idempotency/isolation tests: double run safe; one tenant's failure doesn't block another
- [ ] 3.7 Run `ruff check`, `ruff format --check`, `mypy` on touched `auth/` and `core/`, and `pytest`
