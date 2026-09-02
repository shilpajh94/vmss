## Why

`AuditLog` rows are already written for every mutating action
(`auth/audit.py::record_audit_log`, per `security-architecture.md` §5), but
nothing exposes them back to a tenant admin. There is no way today to answer
"who did what, and when" without a direct database query — which blocks the
product's compliance/incident-review story and the "who's inside during an
emergency" trail this data is meant to support. This change adds a
tenant-scoped audit trail history: a filterable, paginated list of every
recorded action, plus asynchronous generation and download of a report
(CSV or PDF) covering a selected range.

## What Changes

- New `GET /audit-trail` list endpoint: paginated, filterable (actor, action,
  entity type, entity id, date range) and sortable, following
  `api-conventions.md` §1 (explicit typed query params, `page`/`pageSize`
  envelope, whitelisted `sortBy`).
- New `GET /audit-trail/{id}` detail endpoint: single audit log entry
  including its before/after `diff`.
- New `POST /audit-trail/reports` endpoint: accepts the same filter set plus
  a requested format (`csv` and/or `pdf`), enqueues a Celery job, and returns
  a report job id + `pending` status. Requires an `Idempotency-Key` header
  per `api-conventions.md` §3 so a retried request doesn't enqueue a
  duplicate job.
- New `GET /audit-trail/reports/{id}` endpoint: returns the job's status
  (`pending` / `ready` / `failed`) and, once `ready`, a time-boxed download
  URL for the generated file.
- New Celery task that builds the requested file(s) from the filtered
  `AuditLog` rows and persists them via the existing storage tier
  (`core/storage.py`), following `background-jobs.md`'s idempotent-task-body
  and retry conventions.
- New permissions `audit-logs:view` and `audit-logs:export`, seeded into the
  RBAC catalog (`auth/rbac_catalog.py`), granted to the `admin` role.
- Every audit trail HTTP action (viewing the list/detail, requesting a
  report, downloading a report) is itself logged at `INFO`/`WARNING` per
  `logging-observability.md` — this is read access to a security-sensitive
  trail, so accessing it is itself worth a trail.

No existing endpoint, schema, or table changes shape — this is additive only.

## Capabilities

### New Capabilities
- `audit-trail`: tenant-scoped listing, filtering, and detail view of
  recorded audit log actions, plus asynchronous report generation (CSV/PDF)
  and time-boxed download of the generated file.

### Modified Capabilities
(none — this change is additive and does not alter the recorded behavior of
any existing capability, including how `AuditLog` rows are written)

## Impact

- **New feature package**: `src/vmss_api/audit_trail/` (`router.py`,
  `service.py`, `schemas.py`, `models.py`, `repository.py`, `tasks.py`,
  `tests.py`) per `project-rules.md`'s "New Features" convention. Reads the
  existing `AuditLog` table owned by `auth/models.py`; owns one new table of
  its own to track report-generation jobs (decision recorded in
  `design.md`).
- **New tenant-schema migration** (`alembic_tenant/`) for the new report-job
  table — applied to every tenant schema per
  `database-architecture.md` §5.
- **`auth/rbac_catalog.py`**: two new permission codes
  (`audit-logs:view`, `audit-logs:export`), granted to `admin`.
- **`core/storage.py`**: reused to persist generated report files; may need
  a small extension so a Celery-generated file (not a client upload) can be
  written without going through the client-upload validation path
  (`validate_upload`) — decision recorded in `design.md`.
- **New dependency**: a PDF-generation library (none exists in the project
  today) — decision recorded in `design.md`.
- **`api.py`**: register the new router.
- **`main.py`**: add `audit-trail` to `_TAGS_METADATA`.
