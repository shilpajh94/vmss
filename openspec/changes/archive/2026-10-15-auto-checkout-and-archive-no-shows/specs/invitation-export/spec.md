## MODIFIED Requirements

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
| `archived` | Archived |

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

#### Scenario: Archived status label
- **WHEN** an `archived` invitation is exported
- **THEN** its Status cell shows `Archived`

#### Scenario: Primary contact role label
- **WHEN** an individual invitation is exported
- **THEN** its row's Visitor Role is `Primary Contact`

#### Scenario: Unknown code still readable
- **WHEN** an invitation carries a status code that has no defined label,
  such as `pending`
- **THEN** its Status cell shows `Pending`

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
32. Archived At

Rules for these columns:

- Visit-level columns (Visitor Category through Archived At) SHALL be
  repeated on every row of the invitation.
- Vehicle Number(s) SHALL list every vehicle's license plate on the
  invitation, separated by `, `.
- Carried Items SHALL list the declared items, separated by `, `.
- Checked In By and Checked Out By SHALL be the full names of the staff
  users who did those actions. When the visit was checked out by the
  automatic check-out sweep, Checked Out By SHALL be
  `System (auto check-out)`.
- A value that is not recorded SHALL be an empty cell.
- The file SHALL NOT include ID-proof document contents, photos, storage
  keys or signed URLs of any kind, whether or not the caller holds
  `documents:view`.
- Column headers SHALL be human-readable labels. Each timestamp header
  (Requested At, Approved At, Denied At, Checked In At, Checked Out At,
  Archived At) SHALL end with the tenant's timezone name in parentheses,
  for example `Approved At (Asia/Kolkata)`.

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

#### Scenario: Automatic check-out is labelled
- **WHEN** an exported invitation was checked out by the automatic
  check-out sweep
- **THEN** its Checked Out By cell shows `System (auto check-out)`

#### Scenario: No document or photo references leak
- **WHEN** a caller holding `documents:view` exports invitations whose
  visitors have ID-proof documents and photos on file
- **THEN** no cell in the file contains a storage key or a URL to either
  file

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
| `archived` | Requested At, Approved At, Archived At |

For `status=archived`, the export's date range and sort order SHALL apply
to `archivedAt`. When `status` is omitted, the export SHALL include every
lifecycle column. All non-lifecycle columns SHALL be present whatever the
status filter.

#### Scenario: Approved export omits later-stage columns
- **WHEN** a caller exports with `status=approved`
- **THEN** the header row has Requested At and Approved At, and has no
  Denied At, Denial Reason, Checked In At, Checked In By, Checked Out At,
  Checked Out By or Archived At column

#### Scenario: Archived export uses the archive date
- **WHEN** a caller exports with `status=archived` and a date range
- **THEN** the header row has Requested At, Approved At and Archived At
  only, and the rows are the archived invitations whose `archivedAt` falls
  in that range

#### Scenario: Denied export shows the reason
- **WHEN** a caller exports with `status=denied` and an invitation was
  denied with the reason "No host available"
- **THEN** the header row has Denied At and Denial Reason, and that
  invitation's rows show "No host available"

#### Scenario: All-status export keeps every column
- **WHEN** a caller exports with no `status`
- **THEN** the header row has all 32 columns in the order defined under
  "Exported Columns Exclude Documents and Signed URLs"
