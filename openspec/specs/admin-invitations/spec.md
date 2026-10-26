# admin-invitations Specification

## Purpose

The admin-invitations capability is the Super Admin's Invitations screen at `/admin/invitations`: it gives an admin the same organisation-wide Kanban view and approve/reschedule/deny actions the staff dashboard gives staff, so an admin can monitor and act on visit requests without needing the staff-facing screen.

## Requirements

### Requirement: Admin section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Invitations page, and SHALL redirect to `/admin/login` instead of rendering when no token is present.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token navigates to `/admin/invitations`
- **THEN** the system redirects to `/admin/login` and does not render the page

### Requirement: Admin sidebar and top bar render with "Invitations" active
The system SHALL render, for an authenticated session, the Admin sidebar with "Invitations" shown as the active item, and the Admin top bar showing the Invitations-specific description and the signed-in staff member's name and role.

#### Scenario: Admin views the Invitations page
- **WHEN** an authenticated admin's Invitations page finishes loading
- **THEN** the sidebar shows "Invitations" marked active and the top bar shows the signed-in staff member's name and role

### Requirement: Invitations are grouped by status with live counts
The system SHALL group invitations by the same six statuses, in the same order, as the staff dashboard's "Visit requests are grouped by status with live counts", using the same board component. At `lg` and wider, that means three working columns followed by the Closed column. Every status SHALL show the server's total of invitations in that status matching the active search and filters, not the number of cards currently loaded. When a status filter is selected, only that status SHALL load invitations, and every other status SHALL show zero. Every status the status filter offers SHALL have a matching column or Closed-column entry.

#### Scenario: Invitations load successfully
- **WHEN** the invitations list loads successfully at 1536px wide
- **THEN** the board shows the Requested, Approved, Checked-in, and Closed columns, each invitation appears under its own status, and every status shows the server's total

#### Scenario: Checked-out invitations appear in their own column
- **WHEN** the invitations list loads and some invitations have the status `checked_out`
- **THEN** those invitations are listed when Checked-out is selected in the Closed column, and the Checked-out count shows the server's total matching the active search and filters

#### Scenario: Empty column
- **WHEN** a status has zero invitations
- **THEN** its column, or its Closed-column entry when selected, shows an empty-state message instead of any cards

#### Scenario: Status filter limits loading to one column
- **WHEN** an admin selects the "Approved" status filter
- **THEN** only the Approved column loads invitations, and the Requested and Checked-in columns and all three closed statuses show a count of zero

#### Scenario: Checked-out status filter loads the Checked-out column
- **WHEN** an admin selects the "Checked-out" status filter
- **THEN** the Closed column selects Checked-out, only Checked-out loads invitations and shows the server's total, and every other status shows a count of zero

### Requirement: Search filters visible invitations by visitor name or tracking ID
The system SHALL, as the admin types in the search field, show only invitations whose visitor name or tracking ID contains the entered text (case-insensitive), across all columns.

#### Scenario: Search narrows the board
- **WHEN** an admin enters text in the search field
- **THEN** only invitations whose visitor name or tracking ID contains that text remain visible, in their existing columns

### Requirement: Refresh reloads the invitations list
The system SHALL, when the refresh action is activated, re-fetch every column's already-loaded pages, the role list, and the employee directory, and re-render the board with the latest data. A column the admin has scrolled into SHALL keep its loaded depth and scroll position.

#### Scenario: Admin refreshes the board
- **WHEN** an admin activates the refresh action
- **THEN** the system re-fetches the underlying data and updates the board with the result

#### Scenario: Refresh keeps a scrolled column's depth
- **WHEN** an admin has loaded 60 cards into a column and activates the refresh action
- **THEN** that column still holds up to 60 cards after the refresh and is not scrolled back to the top

### Requirement: List load failure is reported without crashing
The system SHALL, when the invitations list fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the invitations list fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: Card expand, approve, reschedule, and deny behave the same as the staff dashboard
The system SHALL provide on this page the same card behaviours specified for the staff-dashboard capability's board, unchanged:
- activating a card opens Visitor Info
- the "Level X/Y · Pending" approval badge
- card-face Approve/Deny buttons and drag-to-approve (direct or step-based)
- drag-to-deny, with a required reason (direct or step-based)
- the Visitor info, Reschedule, Edit, and Delegate icon buttons and the modals they open

#### Scenario: Approve, reschedule, and deny available to admins
- **WHEN** an admin interacts with a card on the Invitations page the same way a staff member would on the staff dashboard
- **THEN** the same approve, reschedule, and deny behaviors apply, with the same success and failure notifications

#### Scenario: Activating a card opens Visitor Info
- **WHEN** an admin clicks a card on the Invitations board outside its buttons
- **THEN** the Visitor Info modal opens for that invitation, and the card does not expand

### Requirement: Invitations board pins its column headers and loads columns lazily
The admin Invitations board SHALL keep each column's header visible while its cards scroll. It SHALL load each column in pages of 20 as the admin scrolls, without duplicates, and SHALL stop requesting pages once a column is fully loaded. Each column SHALL be ordered newest first by when each invitation entered that column's status, exactly as the staff dashboard's lazy-load requirement defines, across the whole organisation. This is the same behaviour the staff dashboard defines in "Status column headers stay visible while cards scroll" and "Columns load visit requests lazily in pages".

#### Scenario: Scrolling a long column
- **WHEN** an admin scrolls to the end of the 20 cards loaded in the Requested column at 1280px wide
- **THEN** the "Requested" header and count stay visible, a loading indicator appears at the end of the column, and the next 20 invitations are appended

#### Scenario: Search change restarts columns
- **WHEN** an admin has scrolled a column past its first page and then changes the search text
- **THEN** every column reloads from its first page with the new search applied

#### Scenario: Admin board orders columns by status time
- **WHEN** an admin opens the Invitations board and an invitation submitted last week was checked in a minute ago
- **THEN** that invitation appears at the top of the Checked-in column, above invitations that were submitted more recently but checked in earlier

### Requirement: Checked-in cards on the admin board offer the same manual check-out
The system SHALL offer, on every card in the admin Invitations board's Checked-in column, the same confirmed "Check Out" action specified for the staff-dashboard capability's board, with the same confirmation, success, conflict, and failure behaviour. Admins SHALL always see the action on Checked-in cards on this page.

#### Scenario: Admin checks out a visitor from the Invitations board
- **WHEN** an admin activates "Check Out" on a Checked-in card on the Invitations page and confirms
- **THEN** the visitor is checked out, a success notification is shown, and after the board reloads the card appears in the Checked-out column

#### Scenario: Check Out with the Checked-in status filter active
- **WHEN** the admin board's status filter is set to Checked-in and an admin checks a visitor out from that column
- **THEN** after the reload the card no longer appears in the Checked-in column, and the Checked-in count decreases by one

### Requirement: Search and filters sit in one inline bar matching the staff dashboard
The system SHALL render, above the admin Invitations board, a single bar laid out like the staff dashboard's search bar. It SHALL contain, in this order:
- a search field the same 40px height as the filters, taking the remaining width
- a Purpose of Visit filter, defaulting to "All purposes", whose options are the same purposes the staff dashboard offers
- a Registration Type filter (All types / Individual / Group)
- a Status filter, defaulting to "All statuses", offering Requested, Approved, Checked-in, Checked-out, Denied and Archived
- a Source filter, defaulting to "All sources", offering Staff Pre-Registration and Visitor Walk-in

Every filter SHALL always be visible; the page SHALL NOT have a separate "Filters" toggle or pop-open filter panel. On wide screens the controls SHALL sit on one row. On narrow screens they SHALL wrap or stack without horizontal page scroll. Selecting a filter SHALL narrow every column on the server, combined with the search text and other filters, and each column's count SHALL reflect the filtered total. A "Clear filters" action SHALL appear in the bar whenever any filter differs from its default, and SHALL reset all four filters, without clearing the search text.

#### Scenario: All filters visible without a toggle
- **WHEN** an admin opens the Invitations page
- **THEN** the search field and the Purpose, Registration Type, Status, and Source filters are all visible in one bar, and there is no "Filters" toggle button

#### Scenario: Filtering by purpose of visit
- **WHEN** an admin selects a Purpose of Visit filter value
- **THEN** only invitations whose purpose of visit matches that value are shown, in their existing columns, and each column's count reflects the filtered total

#### Scenario: Status filter still loads one column
- **WHEN** an admin selects "Approved" in the Status filter
- **THEN** only the Approved column loads invitations and the other columns show zero, as before

#### Scenario: Clear filters resets every filter
- **WHEN** an admin has a Purpose and a Source filter selected and a search term entered, and activates "Clear filters"
- **THEN** all four filters return to their defaults, the search term is kept, and "Clear filters" is no longer shown

#### Scenario: Wide screen layout
- **WHEN** the Invitations page is viewed at 1440px wide
- **THEN** the search field and all four filters sit on a single row at equal height

#### Scenario: Narrow screen layout
- **WHEN** the Invitations page is viewed at 360px wide
- **THEN** the search field and filters stack or wrap with no horizontal page scroll

#### Scenario: Archived is a status option
- **WHEN** an admin opens the Status filter
- **THEN** "Archived" is listed after "Denied", and selecting it loads only the Archived column

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

### Requirement: Invitations board groups closed statuses and keeps a readable width
The admin Invitations board SHALL provide the same Closed column and minimum column width that the staff dashboard defines in "Closed statuses share one column on desktop" and "Board columns keep a readable minimum width". The admin board SHALL remember its last-selected closed status separately from the staff board's.

#### Scenario: Switching statuses on the admin board
- **WHEN** an admin at 1536px wide selects Denied in the Closed column on `/admin/invitations`
- **THEN** the Closed column lists Denied invitations and the other columns are unchanged

#### Scenario: Admin and staff boards remember independently
- **WHEN** a user selects Archived on the admin board and then opens the staff Invitations board in the same browser
- **THEN** the staff board's Closed column selects its own last choice, or Checked-out if it has none

### Requirement: The admin board opens a status from a deep link
The system SHALL, when the admin Invitations board is opened with one or
more `status` query parameters naming known invitation statuses
(`submitted`, `approved`, `checked_in`, `checked_out`, `denied` or
`archived`), apply those statuses as the status filter once on load,
exactly as if the admin had picked them in the filter bar. Unknown `status`
values SHALL be ignored; if none is known, the board loads with no status
filter.

The board SHALL also accept the dashboard drill-down parameters
`visitDateFrom`, `visitDateTo`, `upcoming=true`, `excludeExpired=true` and
`branchId`. It SHALL send them on every column request and on export, and
SHALL show them as one "From dashboard" row of removable chips (for example
"Visit date: 26 Oct", "Upcoming only", "Not expired", "Branch: HQ"), with
the branch shown by name. A malformed value SHALL be ignored with no error.

The admin SHALL be able to clear or change every one of these afterwards:
removing a chip drops that parameter, and "Clear filters" removes the
status filter and every chip. A `status` and an `invitationId` parameter
SHALL work together: the filter applies, and that invitation's details
open.

#### Scenario: Open pending approvals from the dashboard
- **WHEN** an admin opens `/admin/invitations?status=submitted`
- **THEN** the board shows only submitted invitations, and the status filter
  shows that status

#### Scenario: Several statuses and a visit date
- **WHEN** an admin opens
  `/admin/invitations?status=approved&status=checked_in&status=checked_out&visitDateFrom=2026-10-26&visitDateTo=2026-10-26`
- **THEN** the status filter shows the three statuses, a "Visit date: 26
  Oct" chip is shown, and every column lists only invitations visiting on
  that day

#### Scenario: Removing a chip widens the board
- **WHEN** an admin removes the "Not expired" chip from a board opened with
  `status=submitted&excludeExpired=true`
- **THEN** the board reloads and shows every submitted invitation,
  including expired ones

#### Scenario: Export follows the drill-down
- **WHEN** an admin exports from a board opened with `upcoming=true` and a
  branch chip
- **THEN** the export contains exactly the invitations the board shows

#### Scenario: Unknown status ignored
- **WHEN** an admin opens `/admin/invitations?status=bogus`
- **THEN** the board loads unfiltered, with no error
