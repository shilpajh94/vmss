## Context

See `proposal.md` - Why. Relevant existing pieces this builds on:

- `AuditLog` (`auth/models.py`) is already written for every mutating action
  via `auth/audit.py::record_audit_log`, called as a `BackgroundTasks` task
  from mutating routers. This change only adds read/export paths — the write
  path is untouched.
- `core/storage.py` already exposes an opaque `save`/`url_for` interface
  (local disk in dev, S3-compatible + presigned URLs in prod) used today for
  visitor ID-proof/photo uploads. Its `validate_upload` + `_ALLOWED_CONTENT_TYPES`
  gate is specifically about sniffing untrusted client-supplied bytes
  (`file-upload-handling.md` §2) — a generated report is server-produced,
  trusted content, so it doesn't need that gate, but it does need a storage
  key and a retrievable URL.
- `reports/tasks.py` and `invitations/router.py` are the two existing
  reference patterns for, respectively, an async Celery job with a Redis
  idempotency/run-marker, and the `Idempotency-Key` header +
  `_cached_response`/`_cache_response` request-dedup pattern
  (`api-conventions.md` §3).
- The user confirmed: both CSV and PDF must be supported, and generation
  must be asynchronous (Celery job + download link), not inline/streamed,
  given an audit trail can grow to thousands of rows per tenant.

## Goals / Non-Goals

**Goals:**
- List/filter/paginate/sort existing `AuditLog` rows; fetch one by id.
- Generate a CSV and/or PDF export of a filtered range as a background job;
  let the caller poll status and download the result once ready.
- Keep the write path (`record_audit_log`) completely unchanged.

**Non-Goals:**
- Real-time streaming/tailing of new audit events (e.g. a live feed/websocket).
- Editing, redacting, or deleting audit log entries — they are append-only
  per `database-architecture.md` §4, and nothing here changes that.
- Cross-tenant or platform-level audit reporting (`platform_audit_events`,
  the global-schema table, is a separate concern — out of scope here).
- Building the actual Figma-designed frontend screen — this repo is the API
  only (`project-rules.md` "Product"); the portal is a separate repo.

## Decisions

### Decision 1: New `audit_trail` feature package, reading `auth`'s `AuditLog`
Alternative considered: extend `auth/router.py` directly, since it already
owns `AuditLog`. Rejected — `auth` is about identity/roles/permissions, not
reporting, and `fastapi-architecture.md` §1's one-feature-per-domain-concern
convention plus this feature's own real complexity (filtering, pagination,
async report jobs, a new table) justify a dedicated package, the same way
`reports/` already exists as its own package rather than living in
`org_structure`. `audit_trail/repository.py` queries `AuditLog` directly
(cross-package read of another feature's table is already normal here —
`reports/repository.py` reads `org_structure`/`auth` tables today).

### Decision 2: A new `AuditReportJob` table tracks report generation
Alternative considered: track job state only in Redis (status +
storage keys), avoiding a new table/migration entirely. Rejected:
- A report job's outcome (who requested it, what filters, which format(s),
  when it completed) is itself exactly the kind of record this feature
  exists to make visible — losing it to a TTL eviction undercuts the
  compliance use case the whole feature serves.
- `GET /audit-trail/reports/{id}` needs to be pollable reliably; Redis key
  eviction (even with a generous TTL) risks a job silently becoming
  unpollable while report generation is still legitimately in progress for
  a very large export.

`AuditReportJob` (tenant-scoped, `Base` + `TimestampMixin`, new
`audit_trail/models.py`, new `alembic_tenant/` migration):
- `id`, `requested_by_user_id` (FK `users.id`), `status`
  (`pending` / `ready` / `failed`), `filters` (JSONB — the request's filter
  set, for traceability), `formats` (e.g. `["csv", "pdf"]`), `csv_storage_key`
  (nullable), `pdf_storage_key` (nullable), `error_message` (nullable),
  `completed_at` (nullable).
- Storage keys are resolved to a fresh presigned URL via `storage.url_for`
  on every poll (same pattern `invitations`' `BadgeOut.badge_url` already
  uses) rather than a URL being computed once and stored — keeps no
  long-lived secret sitting in the database, and each poll naturally gets a
  URL valid for `settings.storage_s3_presigned_url_ttl_seconds` from that
  moment.

### Decision 3: `Idempotency-Key` request-dedup reuses the existing Redis pattern
`POST /audit-trail/reports` follows `invitations/router.py`'s
`_cached_response`/`_cache_response` helpers exactly (same
`vmss:{tenant_id}:{feature}:idempotency:{key}` convention,
`database-architecture.md` §6): a retried request with the same key returns
the original job-creation response (including the original job id) instead
of enqueueing a second Celery job. This is a request-level cache
(≈24h, matching the existing convention) — it is separate from, and shorter
than, the `AuditReportJob` row's own lifetime, which persists like any other
tenant data.

### Decision 4: PDF generation via `reportlab`
No PDF library exists in this project yet. `reportlab` is chosen over
`weasyprint`/`xhtml2pdf`/`pdfkit`: it's pure-Python (no system-level
dependency like a headless browser or `wkhtmltopdf` binary to install in
every environment, including CI and whatever deployment target is
eventually chosen per `project-rules.md`'s "Deployment" — still open), and
this report is a simple tabular layout, not a richly styled document, so
`reportlab`'s lower-level canvas/table API is sufficient without the
overhead of an HTML-to-PDF rendering pipeline.

### Decision 5: Report building runs in a Celery task, offloaded per file-format
One Celery task (`audit_trail/tasks.py::generate_audit_report`) takes the
job id, re-resolves the tenant schema (`background-jobs.md` §4), queries
`AuditLog` via the same filtered query the list endpoint uses (one shared
repository method — `query-performance.md` §2, no loop-and-query), and
builds each requested format. CSV uses the stdlib `csv` module (no new
dependency); PDF uses `reportlab`. Both writes go through
`anyio.to_thread.run_sync` inside the task for the CPU-bound rendering step
(`fastapi-architecture.md` §4), then `core/storage.save(...)` persists each
file and the job row is updated to `ready` with the resulting storage
key(s) — or to `failed` with `error_message` if generation raises after
retries are exhausted (`background-jobs.md` §3/§4). Re-running the same job
id (redelivery) is idempotent: the task checks the row's current `status`
before doing any work, per `background-jobs.md` §2.

### Decision 6: Figma reference deferred
The Figma MCP connector was not authorized in this session, so the actual
portal design file could not be reviewed. The endpoints above are shaped
from this codebase's own list/filter/pagination and report-download
conventions (`api-conventions.md` §1, `invitations`' badge-download
pattern) rather than from the Figma spec directly. Flagged as an open item
below rather than guessed further.

## Risks / Trade-offs

- [A local-disk `storage_backend` (dev only) returns a plain filesystem path
  from `url_for`, not a genuinely time-boxed URL] → Accepted, pre-existing
  limitation shared with the badge-download endpoint today; production runs
  the S3-compatible backend where presigned URLs do expire.
- [A very large tenant's unfiltered report could still take a long time to
  render, even off the request path] → Mitigated by the job status/polling
  model itself (caller isn't blocked) plus `background-jobs.md` §3's
  required retry/backoff; a hard row-count cap per report can be added later
  if this proves necessary, not designed in speculatively now.
- [New dependency `reportlab` adds to the deployment image] → Accepted;
  pure-Python wheel, no system package needed, consistent with
  `project-rules.md`'s "bump deliberately" posture — it's a deliberate,
  justified addition, not an accidental one.

## Open Questions

- Once Figma access is available, confirm the list view's exact visible
  columns/default filters and the exact report-download UX (e.g. whether
  the portal expects a notification/email when a report becomes ready, vs.
  polling only) — neither changes this change's specs or endpoint shapes,
  only optional presentation details a follow-up change could add (e.g. a
  "report ready" notification via the existing `notifications` feature).
