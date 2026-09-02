# Audit Trail

Tenant-wide visibility into every recorded mutating action (`auth/models.py`'s
`AuditLog`, written by `auth/audit.py::record_audit_log` — see
`security-architecture.md` §5). This feature is read-only: it lists/filters/
views existing `AuditLog` rows and generates downloadable reports from them.
It never writes an `AuditLog` row itself.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/audit-trail` | `audit-logs:view` | Paginated, filtered, sorted list of audit log entries. |
| GET | `/api/v1/audit-trail/{auditLogId}` | `audit-logs:view` | One entry by id, including its recorded before/after `diff`. |
| POST | `/api/v1/audit-trail/reports` | `audit-logs:export` | Enqueues CSV/PDF report generation for a filter set; returns a job id. Accepts `Idempotency-Key`. |
| GET | `/api/v1/audit-trail/reports/{jobId}` | `audit-logs:export` | Job status; once `ready`, includes a time-boxed download URL per requested format. |

Company-wide, not branch-scoped (`require_permission`, not
`require_branch_permission`) — same posture as `reports/router.py`.

## Filters (list + report request)

`actorUserId`, `action`, `entityType`, `entityId`, `createdAfter`,
`createdBefore` — each an explicit typed query param
(`api-conventions.md` §1), not a generic `?filter=` string. `sortBy` is
restricted to `createdAt` / `action` / `entityType`.

## Report generation

Report generation is asynchronous (`background-jobs.md`), not inline —
`POST /audit-trail/reports` returns immediately with a `pending` job; poll
`GET /audit-trail/reports/{jobId}` until `status` is `ready` (or `failed`,
with `errorMessage` populated). `audit_trail/tasks.py::generate_audit_report`
builds the requested format(s) — CSV via the stdlib `csv` module, PDF via
`reportlab` — from the exact same filtered query the list endpoint uses, and
persists each file through the existing storage tier
(`core/storage.py`). Download URLs are resolved fresh on every poll
(`storage.url_for`), not stored, so they're valid for
`settings.storage_s3_presigned_url_ttl_seconds` from the moment they're
returned, never a permanently valid link.

Job state (`audit_trail/models.py::AuditReportJob`) is tenant-scoped like any
other tenant table — a job id from another tenant simply isn't resolvable
against a different tenant's session (schema-per-tenant,
`database-architecture.md` §2).

## Design reference

See `openspec/changes/add-audit-trail-history/design.md` for the full set of
decisions (new `AuditReportJob` table vs. Redis-only job tracking, the
`reportlab` choice, the `Idempotency-Key` reuse from `invitations`). That
document also flags that the Figma portal design file was not accessible
when these endpoints were shaped — the request/response contracts here
follow this codebase's own list/filter/pagination and report-download
conventions instead.
