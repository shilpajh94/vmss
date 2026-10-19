## MODIFIED Requirements

### Requirement: Staff Exports Invitations as a Downloadable File
The system SHALL expose `GET /invitations/export`. It SHALL return the
matching invitations as a file download, not a JSON envelope. A `format`
query parameter SHALL accept `csv` or `xlsx` and default to `csv`; any other
value SHALL be rejected with a validation error. The response SHALL carry
the content type for the chosen format and a `Content-Disposition:
attachment` header. The filename SHALL have the form
`invitations-<status>-<YYYY-MM-DD>.<ext>`. `<status>` SHALL be the status
filter with underscores replaced by hyphens, or `all` when no status is
given. `<YYYY-MM-DD>` SHALL be the export date in the tenant's timezone.
Error responses SHALL keep the standard JSON error envelope.

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
- **WHEN** a caller exports with `status=checked_in` on 2026-10-14 in the
  tenant's timezone
- **THEN** the attachment filename is
  `invitations-checked-in-2026-10-14.csv` and contains no underscore

#### Scenario: Filename without a status filter
- **WHEN** a caller exports with no `status`
- **THEN** the attachment filename starts with `invitations-all-`

#### Scenario: No matching invitations
- **WHEN** an export's filters match no invitations
- **THEN** the response is 200 with a file that has the header row and no
  data rows

### Requirement: Exported Columns Exclude Documents and Signed URLs
Each row SHALL contain these columns, in this order, apart from any date
column left out under "Date Columns Follow the Status Filter":

1. Tracking ID
2. Status
3. Visitor Name
4. Visitor Role
5. Email
6. Phone Number
7. ID Proof Type
8. Visitor Category
9. Registration Type
10. Source
11. Branch
12. Building
13. Department
14. Host
15. Point of Contact
16. Purpose of Visit
17. Visit Date
18. Visit Time
19. Expected Duration
20. Badge Number
21. Vehicle Number(s)
22. Carried Items
23. Additional Notes
24. Requested At
25. Approved At
26. Denied At
27. Denial Reason
28. Checked In At
29. Checked In By
30. Checked Out At
31. Checked Out By

Rules for these columns:

- Visit-level columns (Visitor Category through Checked Out By) SHALL be
  repeated on every row of the invitation.
- Vehicle Number(s) SHALL list every vehicle's license plate on the
  invitation, separated by `, `.
- Carried Items SHALL list the declared items, separated by `, `.
- Checked In By and Checked Out By SHALL be the full names of the staff
  users who did those actions.
- A value that is not recorded SHALL be an empty cell.
- The file SHALL NOT include ID-proof document contents, photos, storage
  keys or signed URLs of any kind, whether or not the caller holds
  `documents:view`.
- Column headers SHALL be human-readable labels. Each timestamp header
  (Requested At, Approved At, Denied At, Checked In At, Checked Out At)
  SHALL end with the tenant's timezone name in parentheses, for example
  `Approved At (Asia/Kolkata)`.

Formats:

- Timestamps SHALL be expressed in that timezone.
- In CSV, a timestamp SHALL be written as `YYYY-MM-DD HH:MM` (24-hour
  clock), a visit date as `YYYY-MM-DD`, and a visit time as `HH:MM`. No
  cell SHALL contain a `T` separator, seconds or a UTC offset.
- In XLSX, these values SHALL be stored as spreadsheet date/time values
  displayed in the same formats, so they sort and filter as dates.

#### Scenario: Status-specific timestamps populated
- **WHEN** an exported invitation was checked in at 2026-10-13 09:05:42 UTC
  and the tenant's timezone is `Asia/Kolkata`
- **THEN** its rows show `2026-10-13 14:35` under the header
  `Checked In At (Asia/Kolkata)`

#### Scenario: XLSX dates are real date values
- **WHEN** an exported invitation with a visit date and an approval time is
  exported as XLSX
- **THEN** the Visit Date and Approved At cells are spreadsheet date/time
  values, not text

#### Scenario: Visit-level details repeated on group rows
- **WHEN** a group invitation with a primary contact, two co-visitors, a
  badge number and two vehicles is exported
- **THEN** all three rows carry the same Badge Number and the same
  Vehicle Number(s) cell listing both license plates

#### Scenario: Check-in and check-out staff named
- **WHEN** an exported invitation was checked in by one staff user and
  checked out by another
- **THEN** Checked In By and Checked Out By show those users' full names

#### Scenario: No document or photo references leak
- **WHEN** a caller holding `documents:view` exports invitations whose
  visitors have ID-proof documents and photos on file
- **THEN** no cell in the file contains a storage key or a URL to either
  file

### Requirement: Exported Cells Are Safe Against Formula Injection
Opening an exported file in a spreadsheet application SHALL NOT cause any
exported value to be evaluated as a formula. This applies to both CSV and
XLSX. In CSV, any text value that begins with `=`, `+`, `-`, `@`, a tab or
a carriage return SHALL be prefixed with `'`. In XLSX, every text value
SHALL be stored as a text cell, so the application shows it as literal
text. XLSX cells SHALL carry the original value with no added prefix.

#### Scenario: Formula-like visitor name is neutralized
- **WHEN** a visitor's name is stored as `=HYPERLINK("http://evil","x")` and
  that invitation is exported in either format
- **THEN** the exported cell is not evaluated as a formula when the file is
  opened in a spreadsheet application, and the original text is still
  readable

#### Scenario: Phone number is clean in XLSX
- **WHEN** a visitor whose phone is `+919800000261` is exported as XLSX
- **THEN** the Phone Number cell is a text cell whose value is exactly
  `+919800000261`

#### Scenario: Phone number is guarded in CSV
- **WHEN** a visitor whose phone is `+919800000261` is exported as CSV
- **THEN** the Phone Number cell is `'+919800000261`

## ADDED Requirements

### Requirement: Exported Values Are Human-Readable Labels
The export SHALL write enumerated values as labels, never as internal codes.
Status SHALL use the labels shown on the web invitation board:

| Code | Label |
|---|---|
| `submitted` | Requested |
| `approved` | Approved |
| `denied` | Denied |
| `checked_in` | Checked-in |
| `checked_out` | Checked-out |

Source SHALL use these labels:

| Code | Label |
|---|---|
| `staff_pre_registration` | Staff Pre-Registration |
| `visitor_walk_in` | Visitor Walk-in |

Registration Type SHALL use `Individual` or `Group`. Visitor Role SHALL use
`Primary Contact` or `Co-Visitor`. Branch, building, department, host,
visitor category, purpose, duration and ID-proof type SHALL be written as
their configured display names. A code with no known label SHALL be written
in title case with underscores replaced by spaces, never as the raw code.

#### Scenario: Codes become labels
- **WHEN** a `group` invitation from `visitor_walk_in` with status
  `checked_in` is exported
- **THEN** its rows show `Checked-in`, `Visitor Walk-in` and `Group`, and
  no cell in those columns contains an underscore

#### Scenario: Primary contact role label
- **WHEN** an individual invitation is exported
- **THEN** its row's Visitor Role is `Primary Contact`

#### Scenario: Unknown code still readable
- **WHEN** an invitation carries a status code that has no defined label,
  such as `pending`
- **THEN** its Status cell shows `Pending`

### Requirement: Date Columns Follow the Status Filter
When `status` is given, the export SHALL include only the lifecycle columns
that can hold a value for that status, and SHALL leave the rest out
entirely. The columns kept for each status SHALL be:

| `status` | Lifecycle columns kept |
|---|---|
| `submitted` | Requested At |
| `approved` | Requested At, Approved At |
| `denied` | Requested At, Denied At, Denial Reason |
| `checked_in` | Requested At, Approved At, Checked In At, Checked In By |
| `checked_out` | Requested At, Approved At, Checked In At, Checked In By, Checked Out At, Checked Out By |

When `status` is omitted, the export SHALL include every lifecycle column.
All non-lifecycle columns SHALL be present whatever the status filter.

#### Scenario: Approved export omits later-stage columns
- **WHEN** a caller exports with `status=approved`
- **THEN** the header row has Requested At and Approved At, and has no
  Denied At, Denial Reason, Checked In At, Checked In By, Checked Out At or
  Checked Out By column

#### Scenario: Denied export shows the reason
- **WHEN** a caller exports with `status=denied` and an invitation was
  denied with the reason "No host available"
- **THEN** the header row has Denied At and Denial Reason, and that
  invitation's rows show "No host available"

#### Scenario: All-status export keeps every column
- **WHEN** a caller exports with no `status`
- **THEN** the header row has all 31 columns in the order defined under
  "Exported Columns Exclude Documents and Signed URLs"

### Requirement: XLSX Export Is Presented for Reading
An XLSX export SHALL have:

- a bold header row,
- the header row frozen so it stays visible while scrolling,
- an auto-filter on the header row, and
- column widths set so typical values are visible without resizing.

#### Scenario: Header row is frozen and filterable
- **WHEN** an authorized caller exports as XLSX
- **THEN** the worksheet has its first row frozen, an auto-filter covering
  the header row, and bold header cells
