## Purpose

Lets authorized staff download invitations as a CSV or XLSX file, one row
per visitor, filtered by lifecycle status (for example checked-in, approved
or denied) and a date range. This supports handovers, gate lists and
compliance reviews without paging through the invitation board by hand.

## ADDED Requirements

### Requirement: Staff Exports Invitations as a Downloadable File
The system SHALL expose `GET /invitations/export`. It SHALL return the
matching invitations as a file download, not a JSON envelope. A `format`
query parameter SHALL accept `csv` or `xlsx` and default to `csv`; any other
value SHALL be rejected with a validation error. The response SHALL carry
the content type for the chosen format and a `Content-Disposition:
attachment` header whose filename includes the status filter (or `all`) and
the export date. Error responses SHALL keep the standard JSON error
envelope.

#### Scenario: CSV export by default
- **WHEN** an authorized caller requests `GET /invitations/export` without
  `format`
- **THEN** the response is 200 with a `text/csv` body and an attachment
  filename ending in `.csv`

#### Scenario: XLSX export on request
- **WHEN** an authorized caller requests `GET /invitations/export?format=xlsx`
- **THEN** the response is 200 with the
  `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
  content type, a body that opens as a valid workbook, and an attachment
  filename ending in `.xlsx`

#### Scenario: Unsupported format rejected
- **WHEN** a caller requests `GET /invitations/export?format=pdf`
- **THEN** the system returns a validation error and no file

#### Scenario: Filename reflects the status filter
- **WHEN** a caller exports with `status=checked_in`
- **THEN** the attachment filename contains `checked_in` and the export date

#### Scenario: No matching invitations
- **WHEN** an export's filters match no invitations
- **THEN** the response is 200 with a file that has the header row and no
  data rows

### Requirement: Export Rows Are One Per Visitor
Each exported data row SHALL represent one person on an invitation. Every
invitation SHALL produce one row for its primary contact, and a group
invitation SHALL also produce one row for each co-visitor. Every row SHALL
repeat its parent invitation's fields, so each row can be read on its own.
A column SHALL say whether the row is the primary contact or a co-visitor.
All rows of one invitation SHALL be adjacent, with the primary contact's
row first.

#### Scenario: Individual invitation yields one row
- **WHEN** an export includes an `individual` invitation
- **THEN** the file contains exactly one row for it, marked as the primary
  contact

#### Scenario: Group invitation yields a row per person
- **WHEN** an export includes a `group` invitation with a primary contact
  and three co-visitors
- **THEN** the file contains four adjacent rows for it, the primary contact
  first, all carrying the same tracking ID and status

### Requirement: Exported Columns Exclude Documents and Signed URLs
Each row SHALL include at least these values: tracking ID, status,
registration type, source, the visitor's role (primary contact or
co-visitor), the visitor's name, email, phone and ID-proof type, the
branch name, building name, department, purpose of visit, the host's name,
the preferred visit date and time, and the submitted, approved, denied,
checked-in and checked-out timestamps. The file SHALL NOT include ID-proof
document contents, photos, storage keys or signed URLs of any kind,
whether or not the caller holds `documents:view`. Timestamps SHALL be
written in the tenant's configured timezone with an explicit UTC offset.
Column headers SHALL be human-readable labels.

#### Scenario: Status-specific timestamps populated
- **WHEN** an exported invitation has been checked in
- **THEN** its rows carry a non-empty checked-in timestamp in the tenant's
  timezone, with its UTC offset

#### Scenario: No document or photo references leak
- **WHEN** a caller holding `documents:view` exports invitations whose
  visitors have ID-proof documents and photos on file
- **THEN** no cell in the file contains a storage key or a URL to either
  file

### Requirement: Export Uses the Invitation List's Filters Plus a Date Range
The export SHALL accept the same filters as `GET /invitations`, with the
same meaning: `status`, `registrationType`, `source`, `search`,
`purposeOfVisit`, `X-Branch-ID` and `relevantToMe`. It SHALL also accept
optional `dateFrom` and `dateTo` calendar dates, each inclusive and read in
the tenant's timezone. When `status` is given, the range SHALL apply to the
timestamp for that status: `submitted` uses submitted-at, `approved` uses
approved-at, `denied` uses denied-at, `checked_in` uses checked-in-at, and
`checked_out` uses checked-out-at. When `status` is omitted, the range
SHALL apply to the invitation's creation time. `status` SHALL match the
invitation's current status, the same as the list. A `dateFrom` later than
`dateTo` SHALL be rejected with a validation error. Rows SHALL be ordered by
the date-range timestamp, newest first.

#### Scenario: Export checked-in visitors for one day
- **WHEN** a caller exports with `status=checked_in`, `dateFrom=2026-10-13`
  and `dateTo=2026-10-13`
- **THEN** the file contains only invitations whose current status is
  `checked_in` and whose checked-in time falls on 2026-10-13 in the
  tenant's timezone

#### Scenario: Export approved visitors
- **WHEN** a caller exports with `status=approved`
- **THEN** the file contains only invitations whose current status is
  `approved`, and none that have since moved on to `checked_in` or
  `checked_out`

#### Scenario: Date range without a status filters on creation time
- **WHEN** a caller exports with `dateFrom` and `dateTo` but no `status`
- **THEN** the file contains invitations of every status that were created
  within that range

#### Scenario: Inverted date range rejected
- **WHEN** a caller exports with `dateFrom` later than `dateTo`
- **THEN** the system returns a validation error and no file

#### Scenario: List filters narrow the export the same way as the list
- **WHEN** a caller exports with `registrationType`, `source`, `search`
  and/or `purposeOfVisit` set
- **THEN** the file contains only invitations that `GET /invitations` would
  return for the same filter values

### Requirement: Export Requires invitations:export and Respects Branch Scope
The export SHALL require the `invitations:export` permission. It SHALL be
branch-scoped the same way as the branch-wide invitation listing. With
`X-Branch-ID`, the export SHALL be limited to that branch, and an unknown
or unauthorized branch SHALL be rejected the way other branch-scoped
endpoints reject it. Without `X-Branch-ID`, the export SHALL cover every
branch where the caller holds `invitations:export`, and SHALL be rejected
with 403 if there are none. `relevantToMe=true` SHALL further limit the
export to invitations relevant to the caller; it SHALL NOT replace the
`invitations:export` check. By default, `invitations:export` SHALL be
granted to the `admin`, `reception` and `security` roles, both for new
tenants and for existing tenants. The `host` role SHALL NOT receive it by
default.

#### Scenario: Reception exports their branch
- **WHEN** a `reception` caller exports with their branch's `X-Branch-ID`
- **THEN** the file contains only that branch's invitations

#### Scenario: Caller without invitations:export is denied
- **WHEN** a caller holding `invitations:view-all` but not
  `invitations:export` requests an export
- **THEN** the system returns 403 and no file

#### Scenario: Host is denied by default
- **WHEN** a caller holding only the default `host` role requests an export,
  with or without `relevantToMe=true`
- **THEN** the system returns 403

#### Scenario: Unauthorized branch rejected
- **WHEN** a caller exports with an `X-Branch-ID` for a branch where they do
  not hold `invitations:export`
- **THEN** the system returns 403 and no file

#### Scenario: Existing tenants receive the grant
- **WHEN** the tenant migrations are applied to a tenant provisioned before
  this change
- **THEN** that tenant's `admin`, `reception` and `security` roles hold
  `invitations:export`, and its `host` role and custom roles do not

#### Scenario: Export never crosses tenants
- **WHEN** two tenants both have invitations and a caller from the first
  tenant exports with no filters
- **THEN** the file contains only the first tenant's invitations

### Requirement: Export Size Is Capped Without Silent Truncation
The system SHALL enforce a configurable maximum number of data rows per
export. If an export would exceed it, the system SHALL reject the request
with 422, a message asking the caller to narrow the filters, and no file.
It SHALL NOT return a partial file.

#### Scenario: Over-cap export rejected
- **WHEN** the matching invitations would produce more visitor rows than the
  configured maximum
- **THEN** the system returns 422 with a message to narrow the filters, and
  no file

#### Scenario: Export at the cap succeeds
- **WHEN** the matching invitations would produce exactly the configured
  maximum number of rows
- **THEN** the response is 200 with every matching row

### Requirement: Exported Cells Are Safe Against Formula Injection
Any exported text value that begins with `=`, `+`, `-`, `@`, a tab or a
carriage return SHALL be neutralized so a spreadsheet application shows it
as literal text rather than evaluating it as a formula. This SHALL apply to
both CSV and XLSX.

#### Scenario: Formula-like visitor name is neutralized
- **WHEN** a visitor's name is stored as `=HYPERLINK("http://evil","x")` and
  that invitation is exported
- **THEN** the exported cell is not evaluated as a formula when the file is
  opened in a spreadsheet application, and the original text is still
  readable

### Requirement: Each Export Is Audited
Every successful export SHALL be recorded in the tenant's audit trail. The
entry SHALL include the acting user, the filters applied, the format, and
the number of data rows exported. It SHALL NOT include any exported visitor
data. A rejected export (permission denied, validation error, or over the
cap) SHALL NOT produce an export audit entry.

#### Scenario: Successful export is audited
- **WHEN** a caller successfully exports 42 rows as XLSX with
  `status=approved`
- **THEN** an audit entry is recorded with that caller as the actor, the
  `approved` status filter, format `xlsx` and a row count of 42

#### Scenario: Rejected export is not audited as an export
- **WHEN** an export is rejected for exceeding the row cap
- **THEN** no export audit entry is recorded
