## ADDED Requirements

### Requirement: Admins can export invitations from the board
The admin Invitations page SHALL show an "Export" button at the end of
the page's title row, directly above the search and filter bar. It SHALL
NOT be placed inside the filter bar, which keeps the bar on one row at
1440px wide. Activating the button SHALL open the Export invitations
dialog. Once the signed-in user has loaded, the button SHALL stay
available while the board is loading or showing an error, because the
export does not depend on the cards that are loaded.

#### Scenario: Export button opens the dialog
- **WHEN** an admin activates "Export" on the Invitations page
- **THEN** the Export invitations dialog opens and the board stays as it was
  behind it

### Requirement: The Export invitations dialog is prefilled from the board
The Export invitations dialog SHALL contain:
- a Status select offering "All statuses", Requested, Approved,
  Checked-in, Checked-out and Denied
- optional From and To date fields
- a Format choice of CSV or Excel

When the dialog opens, Status SHALL be prefilled from the board's Status
filter ("All statuses" when the board has none). Format SHALL default to
CSV, and the dates SHALL be empty. The dialog SHALL show, read-only, the
board's other active filters that the export will also apply (search
text, purpose of visit, registration type, source), or "No other filters"
when none are active. Below the dates, the dialog SHALL explain which
date the range applies to: the date of the chosen status, for example
"Check-in date" for Checked-in, or "Created date" for All statuses.

#### Scenario: Status prefilled from the board filter
- **WHEN** the board's Status filter is "Checked-in" and the admin opens the
  Export invitations dialog
- **THEN** the dialog's Status shows "Checked-in", Format shows CSV, both
  dates are empty, and the hint says the range applies to the check-in date

#### Scenario: Active board filters are summarised
- **WHEN** the board has search text "Priya" and the Source filter
  "Visitor Walk-in" and the admin opens the dialog
- **THEN** the dialog lists both as filters the export will also apply

#### Scenario: Changing the dialog does not change the board
- **WHEN** the admin changes Status in the dialog and then closes it
  without exporting
- **THEN** the board's own Status filter and columns are unchanged

### Requirement: Confirming the dialog downloads the export file
Confirming the dialog SHALL request the file from the API's invitation
export with:
- the dialog's status, From and To dates, and format, and
- the board's search, purpose of visit, registration type and source
  filters.

The browser SHALL save the response as
`invitations-<status or "all">-<YYYYMMDD>.<csv|xlsx>`, using the local
date. While the request is in flight, the confirm button SHALL show a busy
state and SHALL NOT start a second export. On success, the dialog SHALL
close and a success notification SHALL be shown.

#### Scenario: Exporting checked-in visitors for a day as Excel
- **WHEN** the admin sets Status "Checked-in", From and To to 14 Oct 2026,
  and Format Excel, and confirms
- **THEN** the browser downloads `invitations-checked_in-<today>.xlsx`
  containing that export, the dialog closes, and a success notification is
  shown

#### Scenario: Double activation exports once
- **WHEN** the admin activates the confirm button twice in quick succession
- **THEN** only one export request is made

### Requirement: Export dialog validates dates and reports server rejections
The dialog SHALL NOT send a request while From is later than To. It SHALL
show an inline message on the date fields instead. If the API rejects the
export (for example because there are too many rows, permission is denied
or the date range is invalid), the dialog SHALL stay open with the user's
choices intact and SHALL show the server's error message, so the user can
narrow the filters and try again.

#### Scenario: From later than To
- **WHEN** the admin sets From to 15 Oct 2026 and To to 14 Oct 2026
- **THEN** the dialog shows an inline date-range message, the confirm button
  does not send a request, and no file is downloaded

#### Scenario: Export too large
- **WHEN** the admin confirms an export that the API rejects because it has
  too many rows
- **THEN** the dialog stays open with the same choices and shows the API's
  message asking to narrow the filters, and no file is downloaded

### Requirement: The board's filter bar wraps instead of clipping controls
The admin Invitations filter bar SHALL wrap its controls onto another row
whenever they don't fit on one. No control, including "Clear filters",
SHALL be cut off or pushed outside the page at any width from 360px to
1920px, and the page SHALL NOT scroll sideways. When there is room
(for example at 1440px with no filter active), the search field and all
four filters SHALL still share one row.

#### Scenario: Filters active at 1280px
- **WHEN** an admin selects a Status and a Source filter with the page 1280px wide
- **THEN** every dropdown and the "Clear filters" link are fully visible,
  with the controls that don't fit wrapping onto a second row

#### Scenario: No filters at 1440px
- **WHEN** the Invitations page is viewed at 1440px wide with no filter set
- **THEN** the search field and all four filters sit on one row

