## Why

Tenant admins can create employees and sync the directory, but cannot remove or
suspend an individual employee from the admin side — the only way an employee
becomes inactive today is by being absent from a directory-sync batch. Separately,
invitations (and the visitor PII hanging off them: ID proofs, contact details,
photos' keys) accumulate forever; there is no retention job, so data is kept
longer than needed and tables grow without bound.

## What Changes

- Add admin endpoints to **disable** (reversible), **enable**, and **delete**
  (soft delete) a single employee, gated by `employees:manage`, audited.
- Disabled employees cannot log in and are excluded from host search (existing
  `is_active` behaviour), and a manual disable is not silently undone by the next
  directory sync.
- Deleting an employee soft-deletes the user, revokes access, and frees their
  email/employee code for reuse (removes the global `tenant_user_index` row).
- Guard rails: an admin cannot disable/delete themself, nor the tenant's last
  active admin.
- Add a Celery-beat **invitation retention job**: for each active tenant, find
  invitations past the configured retention age, **write a backup first**, verify
  it, then permanently delete the invitations and their child rows. If the backup
  fails, nothing is deleted.
- Add settings for retention age, schedule, and batch size (with `.env.example`
  entries).

## Capabilities

### New Capabilities
- `invitation-retention`: scheduled, backup-first purge of invitations older than
  the retention window, including the backup artifact, idempotency, and audit.

### Modified Capabilities
- `auth`: adds employee disable/enable/delete requirements and changes how
  directory sync treats manually disabled employees.

## Impact

- Code: `auth/` (router, service, repository, schemas, rbac), `invitations/`
  (repository + new `tasks.py`), `core/celery_app.py` (beat schedule, routes,
  autodiscover), `core/config.py`, `core/storage.py` usage for backups.
- DB: tenant migration adding a `disabled_by_admin` flag on `users` (see design).
- APIs: three new endpoints under `/auth/employees/{id}`; additive, no `v1` break.
- Config: `INVITATION_RETENTION_DAYS`, `INVITATION_PURGE_BATCH_SIZE`,
  `INVITATION_PURGE_SCHEDULE_*`; `.env.example` updated.
- Data: irreversible hard deletion of invitation rows after backup — needs
  sign-off on the default retention window.
