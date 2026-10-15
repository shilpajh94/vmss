## RENAMED Requirements

- FROM: `### Requirement: Invitations are grouped into five status columns with live counts`
- TO: `### Requirement: Invitations are grouped by status with live counts`

## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Invitations board groups closed statuses and keeps a readable width
The admin Invitations board SHALL provide the same Closed column and minimum column width that the staff dashboard defines in "Closed statuses share one column on desktop" and "Board columns keep a readable minimum width". The admin board SHALL remember its last-selected closed status separately from the staff board's.

#### Scenario: Switching statuses on the admin board
- **WHEN** an admin at 1536px wide selects Denied in the Closed column on `/admin/invitations`
- **THEN** the Closed column lists Denied invitations and the other columns are unchanged

#### Scenario: Admin and staff boards remember independently
- **WHEN** a user selects Archived on the admin board and then opens the staff Invitations board in the same browser
- **THEN** the staff board's Closed column selects its own last choice, or Checked-out if it has none

## REMOVED Requirements

### Requirement: Invitations board columns can be collapsed and keep a readable width
**Reason**: Replaced by "Invitations board groups closed statuses and keeps a readable width". Per-column collapse is removed from both boards.
**Migration**: None for users. The feature was never released.
