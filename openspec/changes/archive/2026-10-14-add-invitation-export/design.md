## Context

`GET /invitations` (`invitations/router.py::list_invitations`) already
covers the filtering staff need: status, registration type, source,
search, purpose of visit, branch scope through `require_branch_scope`, and
`relevantToMe`. The filters are built inline in
`InvitationRepository.list_page`, which is paginated (hard max of 100 per
page) and does not load the `visitors` child rows. The child relationships
are `lazy="raise"`, so they must be loaded explicitly.

The one existing export, the audit-trail report, runs as an asynchronous
Celery job with a job table, a polling endpoint and a time-boxed download.
The user chose a **direct download** for this change instead, with CSV and
XLSX formats and one row per visitor. See proposal.md for why the export is
needed and specs/invitation-export/spec.md for the required behavior.

The relevant model facts:
- An `individual` invitation has no `InvitationVisitor` rows. The primary
  contact's details live on `Invitation` itself (`primary_contact_*`).
- A `group` invitation has one or more `InvitationVisitor` rows.
- Lifecycle timestamps are stored on `Invitation`: `submitted_at`,
  `approved_at`, `denied_at`, `checked_in_at` and `checked_out_at`.
- `Tenant.timezone` holds the tenant's timezone and defaults to `UTC`.

## Goals / Non-Goals

**Goals:**
- One endpoint, synchronous, that produces a correct and complete file or a
  clear rejection. A partial file is never returned.
- The export and the list share one filter implementation, so they cannot
  drift apart.
- A bounded memory and time cost per request.

**Non-Goals:**
- Exporting admin-authored custom form fields (`custom_field_values`,
  `group_field_values`). Their columns change per branch and form version,
  so they need their own design. Fixed columns only for now.
- Exporting vehicles or carried items.
- An asynchronous or scheduled export, or emailing the file. If the row cap
  turns out to be too low, revisit the audit-trail job pattern.
- PDF output.
- Changes to the web client (VMMS_WEB). That is tracked separately.

## Decisions

### 1. Synchronous `GET /invitations/export` with a row cap, not a Celery job
The file is built in memory and returned as a `Response` with a
`Content-Disposition: attachment` header. A new setting,
`invitation_export_max_rows`, defaults to 10,000 visitor rows. Before any
rows are loaded, a count query sums the rows the export would produce
(one per invitation, plus one per co-visitor). If the sum is over the cap,
the route returns 422 through `error_response` and does no further work.

*Alternatives considered:* the async job pattern from audit-trail handles
any volume, but it needs a job table, a migration, a polling endpoint and
polling UI. A day's or week's status export is far below 10,000 rows. A
`StreamingResponse` with no cap avoids buffering, but XLSX cannot really
be streamed, and an unbounded export of PII has no ceiling at all.
Truncating silently was rejected: a gate list that is quietly missing
people is worse than an error.

### 2. Extract one filter builder shared by `list_page` and the export
`InvitationRepository._list_filters(...)` returns a `list[ColumnElement]`
built from the scope, the status, the registration type, the source, the
search term and the purpose of visit. `list_page` calls it, so its
behavior is unchanged and the existing list tests guard the refactor. The
new `list_for_export(...)` and `count_export_rows(...)` methods call the
same builder and add the date-range clause.

The scope rule is different from the list. The list uses `relevantToMe`
*instead of* a branch filter. The export always applies the
`invitations:export` branch filter, and `relevantToMe` is added on top of
it with AND. The builder therefore accepts both an optional `branch_scope`
and an optional relevance filter and combines them with AND. `list_page`
keeps passing exactly one of the two, as it does today.

### 3. The date range applies to the status-matched timestamp
A fixed mapping, `{submitted: submitted_at, approved: approved_at, denied:
denied_at, checked_in: checked_in_at, checked_out: checked_out_at,
None: created_at}`, picks the timestamp column. That column is used for
both the range and the sort order (newest first). The `dateFrom`/`dateTo`
calendar dates are turned into half-open UTC bounds,
`[dateFrom 00:00 local, dateTo+1 00:00 local)`, in the visit timezone
resolved by the existing `service._resolve_visit_timezone`
(`Company.default_timezone`, then `Tenant.timezone`, then UTC). That is the
same zone the visit-day expiry already uses, so "the day" means the same
thing everywhere. A query schema validates
`dateFrom <= dateTo`.

*Alternative considered:* a separate `dateField` parameter. It is more
flexible, but it allows combinations that make no sense, such as
`status=denied` with `dateField=checkedInAt`, and adds a second thing to
explain in the UI. The fixed mapping answers the actual question ("checked
in on date X").

### 4. Load visitors with `selectinload`, joined lookups with explicit joins
`list_for_export` loads `Invitation` with
`selectinload(Invitation.visitors)`, following query-performance.md §1.
Branch, building and department names and the host's display name come
from one outer-joined query over `branches`, `buildings`, `departments` and
`users` (through `host_id`). There is no per-row lookup (§2). The host
column falls back to `host_name_or_email` when `host_id` is null, and the
department column falls back to `department_to_visit` when `department_id`
is null.

### 5. Rendering lives in a new `invitations/export.py` and runs off the event loop
`export.py` has two pure functions: `build_rows(invitations, lookups, tz)`
returns a `list[list[str]]` of header-ordered rows, and
`render_csv(rows)` / `render_xlsx(rows)` return bytes. The renderers run
through `anyio.to_thread.run_sync` (fastapi-architecture.md §4). CSV uses
the stdlib `csv` module and is written as UTF-8 with a BOM, so Excel
detects the encoding of non-ASCII names correctly. XLSX uses `openpyxl` in
write-only mode, with every cell written as an explicit string so no value
can be interpreted as a formula.

`build_rows` neutralizes formula injection for both formats in one place:
any value starting with `=`, `+`, `-`, `@`, `\t` or `\r` gets a leading
`'`. This follows OWASP's CSV-injection guidance. For XLSX it is a second
layer of protection on top of the string cell type. A phone number such as
`+91…` therefore exports as `'+91…`. That is the expected and documented
cost of the guard.

*Alternative considered:* rendering inside the repository or the service.
Keeping it in pure functions makes the row and escaping logic unit-testable
without a database.

### 6. A new `invitations:export` permission, not a reuse of `invitations:view-all`
A bulk download of visitor PII is a different capability from viewing a
paged board. A tenant may want reception to see the board but not take the
data offline. Following the earlier grant migrations
(`6054f5200ed1_grant_invitations_revert_approval.py`,
`d4e6f8a0b2c3_grant_invitations_view_all.py`), the work is:
- add `invitations:export` to the `rbac_catalog.py` permission list and to
  the `admin`, `reception` and `security` defaults, and
- add an idempotent `alembic_tenant` migration that inserts the catalog row
  (`ON CONFLICT DO NOTHING`) and grants it to those three standard roles.
  Its downgrade removes only this tenant's grants.

### 7. Route placement and response contract
The route is registered before `/{invitation_id}`. Otherwise `export` would
be parsed as a UUID path parameter and fail with 422, the same issue as
`/track`. The success response is a raw file, which is the sanctioned
exception to `success_response` (fastapi-architecture.md §5). In OpenAPI,
the route declares `response_class=Response` and a `responses={200:
{"content": {"text/csv": {}, "application/vnd...sheet": {}}}}` block, so
Swagger shows a file download instead of an untyped body. Errors (403, 404
and 422) still go through `error_response`. The filename is
`invitations-<status|all>-<YYYYMMDD>.<ext>`, using the tenant-local date.

### 8. Audit through `record_audit_log` in a background task
After the file is built, the route calls
`background_tasks.add_task(record_audit_log, ...)` with
`action="invitations_exported"`, `entity_type="Invitation"`,
`entity_id=None`, and `diff={"filters": {...}, "format": ..., "row_count":
N}`. This is the same non-blocking pattern the other invitation actions
use. The structlog `INFO` line carries the same metadata and no visitor
values (logging-observability.md §2).

## Risks / Trade-offs

- [10,000 rows can still be large in memory, roughly a few MB, under
  concurrent exports] → The cap is a setting that can be lowered per
  deployment. Rendering runs in a worker thread so the event loop is not
  blocked. Move to the async job pattern if real usage hits the cap.
- [The count query and the row query run separately, so an invitation
  created between them can push the export one row over the cap] → This is
  acceptable. The cap protects resources; it is not an exact contract.
  Both queries run in the same request transaction.
- [`status` filters on *current* status, so "approved" excludes visitors
  who have since checked in] → This matches the list and is stated in the
  spec. Staff who want "everyone approved this week regardless of what
  happened next" can export with no status and a date range, or run
  several exports. Revisit only if users ask for it.
- [`allow-multiple-checkins` may overwrite `checked_in_at` on a re-check-in]
  → The export reflects the latest check-in, the same as the detail view.
  Visit history per check-in is out of scope.
- [The formula-injection prefix changes how `+`-prefixed phone numbers look]
  → This is documented in `docs/features/invitations.md`. Security comes
  first here.
- [The new permission is granted only to the standard role names] → Custom
  roles must be granted it by an admin, the same as earlier grant
  migrations. This is noted in the docs.

## Migration Plan

1. `uv add openpyxl`.
2. Add the tenant grant migration. Before authoring it, run
   `alembic -c alembic_tenant.ini heads` so that `down_revision` chains onto
   the single current head. The uncommitted
   `add-invitation-approval-revert` migrations on this branch may still be
   the head.
3. Deploy. `prestart` applies the migration to every tenant. Rollback is a
   downgrade of that one revision (it removes the grants) plus reverting
   the code. No data is changed.
