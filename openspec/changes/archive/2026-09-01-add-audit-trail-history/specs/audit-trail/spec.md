## Purpose

Gives a tenant admin visibility into every recorded mutating action within
their tenant — who did what, to which entity, and when — through a
filterable, paginated list and detail view, plus asynchronous generation and
time-boxed download of a report (CSV and/or PDF) covering a selected range.

## ADDED Requirements

### Requirement: Audit trail is listable, filtered, paginated, and sorted
The system SHALL provide a tenant-scoped, paginated endpoint that lists
recorded audit log entries, filterable by actor, action, entity type, entity
id, and a creation-date range, and sortable by an explicit whitelist of
columns — never omitting a match because a filter combination wasn't
anticipated.

#### Scenario: Unfiltered list returns every entry, newest first by default
- **WHEN** the audit trail is listed with no filters applied
- **THEN** every recorded entry for the caller's tenant is returned across
  pages, ordered newest-created-first by default

#### Scenario: Filters narrow the result set correctly
- **WHEN** the audit trail is listed with a combination of actor, action,
  entity type, entity id, and/or date-range filters
- **THEN** only entries matching every supplied filter are returned

#### Scenario: Pagination metadata is accurate
- **WHEN** the audit trail is listed with a given `page` and `pageSize`
- **THEN** the response includes the page's entries plus `page`, `pageSize`,
  `total`, and `totalPages` reflecting the full filtered result set, not
  just the returned page

#### Scenario: Sorting is restricted to a known-safe column set
- **WHEN** a `sortBy` value outside the endpoint's whitelisted sortable
  columns is supplied
- **THEN** the request is rejected with a validation error rather than
  being passed through to the query

### Requirement: Audit trail entry has a retrievable detail view
The system SHALL provide an endpoint that returns one audit log entry by id,
including its recorded before/after diff, for a caller in the same tenant
that the entry belongs to.

#### Scenario: Detail view includes the diff
- **WHEN** a single audit log entry is fetched by id
- **THEN** the response includes the actor, action, entity type, entity id,
  timestamp, and the recorded diff (if any was captured at write time)

#### Scenario: Entry from another tenant is not reachable
- **WHEN** a caller requests an audit log entry id that belongs to a
  different tenant's schema
- **THEN** the request does not return that entry — schema-per-tenant
  session binding means it is not resolvable at all, the same as any other
  tenant-scoped lookup (`database-architecture.md` §2)

### Requirement: Audit trail access requires explicit permission
The system SHALL require the caller to hold a dedicated permission to list
or view audit trail entries, and a separate dedicated permission to request
or download a report — distinct from any other reporting or admin
permission — enforced the same way every other RBAC-gated endpoint is
(`security-architecture.md` §1).

#### Scenario: Caller without the view permission is denied
- **WHEN** a caller lacking the audit-trail view permission requests the
  list, detail, or report-status endpoint
- **THEN** the request is rejected with 403 and no audit trail data is
  returned

#### Scenario: Caller without the export permission cannot request a report
- **WHEN** a caller holds the view permission but not the export permission
  and requests report generation
- **THEN** the request is rejected with 403 and no report job is enqueued

### Requirement: Report generation runs asynchronously and supports CSV and PDF
The system SHALL accept a report request (the same filter set the list
endpoint supports, plus a requested format of `csv`, `pdf`, or both),
process it as a background job rather than within the request/response
cycle, and expose the job's status until the file(s) are ready.

#### Scenario: Report request returns immediately with a job reference
- **WHEN** a report is requested for a given filter set and format
- **THEN** the endpoint responds without waiting for the file to be built,
  returning a job id and a `pending` status

#### Scenario: Report job reflects the filtered data at request time
- **WHEN** a report job completes
- **THEN** the generated file's rows match exactly the entries the list
  endpoint would have returned for the same filters at the time the report
  was requested

#### Scenario: Both formats can be requested together
- **WHEN** a report is requested with both `csv` and `pdf`
- **THEN** both files are generated as part of the same job, each
  independently downloadable once ready

#### Scenario: A failed report job is visible, not silent
- **WHEN** report generation fails after exhausting its retries
- **THEN** the job's status reflects `failed` rather than remaining
  `pending` indefinitely, and the failure is logged with enough context to
  investigate (`logging-observability.md` §3, `background-jobs.md` §4)

### Requirement: Report requests are idempotent under retry
The system SHALL treat a report request carrying the same idempotency key
and tenant as a retry of the original request, returning the original job's
outcome rather than enqueuing a second job.

#### Scenario: Retried report request does not duplicate the job
- **WHEN** a report request is sent twice with the same `Idempotency-Key`
  and the same tenant, in close succession
- **THEN** only one report generation job is enqueued, and the second
  request's response matches the first

### Requirement: Generated report files are downloadable only via a time-boxed reference
The system SHALL make a completed report file retrievable only through a
time-boxed download reference tied to the report job, never a permanently
valid or guessable static URL, and only to a caller in the owning tenant who
holds the export permission.

#### Scenario: Ready report exposes a working download reference
- **WHEN** a report job's status is polled after it has completed
- **THEN** the response includes a download reference that successfully
  retrieves the generated file

#### Scenario: Download reference expires
- **WHEN** a download reference is used after its validity window has
  elapsed
- **THEN** retrieving the file through that reference no longer succeeds

#### Scenario: Report from another tenant is not downloadable
- **WHEN** a caller attempts to poll or download a report job id belonging
  to a different tenant
- **THEN** the request does not succeed in returning that tenant's job
  status or file

### Requirement: Audit trail access is itself observable
The system SHALL log, at the level appropriate to the action
(`logging-observability.md` §3), each time the audit trail list/detail is
viewed and each time a report is requested or downloaded — access to a
security-sensitive trail is itself worth a trail.

#### Scenario: Report request and download are logged
- **WHEN** a report is requested, and separately when its file is
  downloaded
- **THEN** both actions are logged with the acting user, tenant, and
  request id, without logging the file's contents
