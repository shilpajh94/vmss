## ADDED Requirements

### Requirement: Reception can export invitations from the staff dashboard
The staff dashboard SHALL show an "Export" button at the right of its
"Invitations" title row, as the admin Invitations page does, but only to a
signed-in user who holds the Reception role. It
SHALL NOT be shown to any other staff member, such as a host. Activating
it SHALL open the same Export invitations dialog the admin-invitations
capability specifies, with the same prefill, validation, download, and
error behaviour. The dialog's Status SHALL open on the board's current
Status filter ("All statuses" when none is set). The export SHALL be
limited to the invitations this board shows the user (`relevantToMe`),
combined with the board's search, purpose of visit, registration type and
source filters.

#### Scenario: Reception sees and uses Export
- **WHEN** a Reception user opens the staff dashboard, activates "Export",
  sets Status "Approved", and confirms with Format CSV
- **THEN** the browser downloads `invitations-approved-<today>.csv` limited
  to the invitations that user's board shows, filtered to approved ones

#### Scenario: A host does not see Export
- **WHEN** a staff member without the Reception role (for example a host)
  opens the staff dashboard
- **THEN** no "Export" button is shown

#### Scenario: Dialog opens on the board's status
- **WHEN** a Reception user with no Status filter set opens the Export
  invitations dialog from the staff dashboard
- **THEN** the dialog's Status shows "All statuses" and the hint says the
  date range applies to the created date. With a Status filter set, the
  dialog opens on that status instead

#### Scenario: Export button at tablet and laptop widths
- **WHEN** a Reception user views the staff dashboard at any width from
  360px to 1920px
- **THEN** the Export button is fully visible in the title row with its
  "Export" label, and the page has no horizontal scroll

