## Why

The first real export from `GET /invitations/export`
(`invitations-approved-20261014.csv`) is hard to read. It shows raw
database codes (`approved`, `visitor_walk_in`, `staff_pre_registration`,
`group`). Every timestamp is in ISO-8601 form with the offset inside the
cell (`2026-10-11T08:15:19+05:30`). Every phone number starts with a
visible `'`. Several columns are always empty for the status that was
exported. Staff also asked for fields the file leaves out: visitor
category, badge and vehicle numbers, who checked the visitor in and out,
the denial reason, and notes. This change fixes the export before it
ships, while it is still part of the uncommitted `add-invitation-export`
change.

## What Changes

- **Readable values.** Status, source, registration type and visitor role
  are written as labels, not codes. The labels match the ones the web
  invitation board already shows: `submitted` → "Requested",
  `checked_in` → "Checked-in", `visitor_walk_in` → "Visitor Walk-in",
  `staff_pre_registration` → "Staff Pre-Registration", `group` → "Group",
  and "Primary Contact" / "Co-Visitor".
- **Readable dates.** Timestamps are written as `YYYY-MM-DD HH:MM`, with
  no `T`, no seconds and no offset in the cell. The timezone appears once,
  in the column header, for example `Approved At (Asia/Kolkata)`.
  **BREAKING** for the unreleased export contract: cells no longer carry
  their own UTC offset. In XLSX, dates, times and timestamps are stored as
  real date/time cells, so they sort and filter correctly.
- **Clean phone numbers in XLSX.** The leading `'` used for
  formula-injection protection is dropped in XLSX, where every cell is
  already stored as a text or date value that a spreadsheet will not run
  as a formula. CSV keeps the `'` guard, because plain CSV has no cell
  type.
- **Removed columns.** Lifecycle date columns that cannot have a value for
  the filtered status are left out. For example, an `approved` export has
  no Denied At, Checked In At or Checked Out At columns. An export with no
  status filter keeps every column.
- **Added columns.** Visitor Category, Expected Duration, Badge Number,
  Vehicle Number(s), Checked In By, Checked Out By, Denial Reason, Point
  of Contact, Additional Notes and Carried Items.
- **Renamed headers.** "Submitted At" becomes "Requested At" (it follows
  the "Requested" status label), "Preferred Visit Date/Time" becomes
  "Visit Date/Time", and "Phone" becomes "Phone Number".
- **Filename.** The status in the attachment filename uses hyphens and the
  date uses dashes, for example `invitations-checked-in-2026-10-14.xlsx`.
- **Spreadsheet polish (XLSX).** The header row is bold and frozen, has an
  auto-filter, and every column has a sensible width.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `invitation-export`: changes to the column set, value labels, date
  formatting, the status-dependent date columns, filename formatting and
  the XLSX formula-injection approach. This capability is introduced by the
  unarchived `add-invitation-export` change, so that change must be
  archived before this one.

## Impact

- **Code:** `src/vmss_api/invitations/export.py` (headers, label maps,
  typed row values, status-dependent columns, both renderers),
  `invitations/repository.py` (`list_for_export` also joins the visitor
  category and the check-in/check-out users, and eager-loads `vehicles`),
  `invitations/service.py` (filename format, passing the status and
  timezone name to the renderer), and `invitations/tests.py` (export
  tests).
- **API:** `GET /invitations/export` keeps the same parameters, permission
  and status codes. Only the file's content and the filename change. The
  endpoint is not released yet, so no `/api/v2` is needed.
- **Docs:** the column list and the formula-escaping note in
  `docs/features/invitations.md`.
- **Dependencies:** none (`openpyxl` is already added).
- **VMMS_WEB (separate repo, follow-up):** the web app builds its own
  download filename in `filter-options.ts::exportFilename`, because the
  API's `Content-Disposition` header is not readable across origins. That
  function needs the same hyphenated format, or a user still downloads
  `invitations-checked_in-20261014.csv`. It is outside this repo's edit
  scope and is listed as a follow-up task.
