## Context

- `users` (tenant schema) already has `is_active` and `deleted_at`; login
  (`auth/service.py::authenticate_user`) and `core/tenancy.py::get_current_user`
  already reject inactive/deleted users on every request, so token revocation on
  disable/delete comes for free.
- `sync_employee_directory` sets `is_active = True` on every employee in a batch
  and deactivates those omitted — so a manual disable would be undone by the next
  sync unless it is distinguishable.
- `users.email` and `users.employee_code` have plain unique constraints, and the
  global `tenant_user_index` uses email as its primary key. A soft delete alone
  would therefore keep the email/code reserved.
- Invitations reference users via several FKs (`host_id`, `created_by`,
  `checked_in_by_user_id`, ...), so employees cannot be hard-deleted.
- The only existing beat task is `reports.tasks.dispatch_daily_rollup_snapshots`
  (dispatcher → per-tenant task, fresh `asyncio.run` + `engine.dispose()`);
  `background-jobs.md` rules apply (idempotent, explicit retries, ERROR on
  exhaustion, `tenant_id` argument).
- "VMSS admin" is read as the tenant admin (`employees:manage`), not the
  platform superadmin.

## Goals / Non-Goals

**Goals:**
- Per-employee disable/enable/delete from the admin API, safe against lockout and sync.
- A nightly, tenant-isolated, backup-first invitation purge.

**Non-Goals:**
- Bulk disable/delete endpoints; UI.
- Purging stored files (ID proofs, photos, QR/badge images) from object storage.
- Retention for entities other than invitations (visitors master data, audit logs).
- Restore tooling — the backup is a recoverable artifact, restore is a manual ops task.

## Decisions

1. **Disable = `is_active=False` plus new `disabled_by_admin` boolean on `users`**
   (tenant migration, default false). Sync stops forcing `is_active=True` when the
   flag is set; `enable` clears both. Alternative: a status enum — rejected as a
   larger migration for a two-state need. Alternative: a separate "blocklist" table
   — rejected, extra join on every sync.

2. **Delete = soft delete with identifier release.** Set `deleted_at`,
   `is_active=False`, rewrite `email` to `deleted+<user_id>@invalid.local` and null
   `employee_code`, and delete the `tenant_user_index` row — all in one
   transaction (global and tenant tables share a connection). Original email is
   kept in the audit-log diff only. Alternative: partial unique indexes
   `WHERE deleted_at IS NULL` — cleaner but needs a data-model change across two
   unique constraints and the global index anyway; tombstoning is smaller and
   matches `tenant_user_index`'s email PK.

3. **Guard rails in the service layer**: reject self-target and "last active admin"
   (count of active, non-deleted users holding an admin role, computed in one
   repository query) with `409`. Last-admin check runs with a row lock on the
   candidate set to avoid two concurrent disables emptying the tenant.

4. **Endpoints** in `auth/router.py`: `POST /auth/employees/{id}/disable`,
   `POST /auth/employees/{id}/enable`, `DELETE /auth/employees/{id}`, all
   `require_permission("employees:manage")`, `response_model=Envelope[EmployeeOut]`
   (delete returns `204`), audit via `record_audit_log` background task
   (`employee_disabled|enabled|deleted`).

5. **Retention job shape** — new `invitations/tasks.py` entries, routed to the
   `cron_jobs` queue: `dispatch_invitation_purge` (beat, daily, lists active
   tenants, enqueues one task each, per-tenant enqueue failure isolated) and
   `purge_tenant_invitations(tenant_id, tenant_schema)`.

6. **Backup-first, per batch.** For each batch (`INVITATION_PURGE_BATCH_SIZE`,
   default 500) of expired ids: load invitations with children (one eager-loaded
   query, no N+1), serialize to gzipped JSONL, save via `core.storage.save` under
   category `backups/invitations/<run-date>`, reload via `storage.load` and compare
   record count, and only then `DELETE ... WHERE id IN (...)` children-first in one
   transaction. Backup failure raises → Celery retry with backoff; nothing deleted.
   Alternative: `pg_dump` — rejected: needs DB credentials/binaries in the worker
   and dumps a whole schema, not the selected rows. Backups are PII, so they go
   through the existing storage tier (SSE in prod) and are never exposed via
   presigned URLs.

7. **Eligibility**: `COALESCE(preferred_visit_date, created_at::date) < today -
   retention_days`, excluding rows with `check_in_status = 'checked_in'` and no
   check-out. Retention default **365 days** (assumption — see Open Questions);
   `0`/unset disables the job.

8. **Idempotency**: eligibility is re-evaluated from the DB each run, and a batch's
   backup contains exactly its delete ids, so a redelivery either finds nothing or
   re-backs-up and deletes only still-existing rows. A Redis run marker
   (`vmss:{tenant_id}:invitations:purge:{date}`) prevents duplicate concurrent
   runs, as in `reports/tasks.py`.

9. **Audit/logging**: one `AuditLog` row per tenant run (cutoff, count, backup
   keys) written with the tenant session; ERROR log with `tenant_id` on exhaustion;
   no visitor PII in logs.

## Risks / Trade-offs

- [Irreversible hard delete of PII-bearing rows] → backup verified before delete;
  default window is conservative; disabled when unset.
- [Backup holds PII for as long as it exists] → same encryption/storage tier;
  backup expiry is an open question.
- [FK rows elsewhere pointing at invitations (e.g. notifications, audit entity ids)]
  → implementation must enumerate FKs to `invitations.id` and either cascade or
  null them; audit entries only store ids and survive.
- [Last-admin check race] → row lock inside the transaction.
- [Tombstoned email is not human-readable] → original recorded in the audit diff.
- [Files in object storage orphaned after purge] → explicit non-goal; tracked below.

## Migration Plan

1. Tenant Alembic migration adding `users.disabled_by_admin` (default false,
   not null); apply to every tenant schema via the existing provisioning/upgrade path.
2. Deploy API (new endpoints), then worker + beat (new task, schedule, routes,
   autodiscover is already registered for `invitations`).
3. Ship with `INVITATION_RETENTION_DAYS` unset in prod; run once manually on staging,
   inspect the backup, then set the value.
4. Rollback: unset `INVITATION_RETENTION_DAYS` (stops purges); endpoints are additive.
   Deleted employees can be restored manually from the audit diff; purged invitations
   from the backup.

## Open Questions

- Confirm the default retention window (assumed 365 days) and whether the reference
  date should be visit date or creation date.
- How long backups are kept, and whether their files need a separate expiry job.
- Whether ID-proof/photo files of purged invitations must also be removed (and
  backed up) for the compliance requirement.
