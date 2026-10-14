## ADDED Requirements

### Requirement: Reception can export invitations from the staff dashboard
The staff dashboard SHALL show an "Export" button as the last control in
its search and filter bar, but only to a signed-in user who holds the Reception role. It
SHALL NOT be shown to any other staff member, such as a host. Activating
it SHALL open the same Export invitations dialog the admin-invitations
capability specifies, with the same prefill, validation, download, and
error behaviour. Because this board has no Status filter, the dialog's
Status SHALL open as "All statuses". The export SHALL be limited to the
invitations this board shows the user (`relevantToMe`), combined with the
board's search, purpose of visit and registration type filters.

#### Scenario: Reception sees and uses Export
- **WHEN** a Reception user opens the staff dashboard, activates "Export",
  sets Status "Approved", and confirms with Format CSV
- **THEN** the browser downloads `invitations-approved-<today>.csv` limited
  to the invitations that user's board shows, filtered to approved ones

#### Scenario: A host does not see Export
- **WHEN** a staff member without the Reception role (for example a host)
  opens the staff dashboard
- **THEN** no "Export" button is shown

#### Scenario: Dialog opens with all statuses
- **WHEN** a Reception user opens the Export invitations dialog from the
  staff dashboard
- **THEN** the dialog's Status shows "All statuses" and the hint says the
  date range applies to the created date

#### Scenario: Export button at tablet and laptop widths
- **WHEN** a Reception user views the staff dashboard at any width from
  360px to 1920px
- **THEN** the Export button is fully visible. On phones it spans the bar's
  width like the other controls. When the bar's row is full (for example at
  1024px), it wraps to the next row, aligned right, instead of being cut off.

