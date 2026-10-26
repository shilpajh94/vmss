## MODIFIED Requirements

### Requirement: Dashboard renders the sidebar, workspace header, and kanban board
The system SHALL render, for an authenticated non-Reception session:
- a sidebar with the brand mark and the "Dashboard", "Invitations" and "My
  actions" navigation, with "Invitations" selected. The sidebar SHALL
  contain no "Help & Support" item;
- the shared staff top bar;
- a main workspace containing the "Invitations" title row, the search and
  filter bar, and the invitations kanban board.

For an authenticated Reception session, the system SHALL instead render the
Reception sidebar (see `reception-dashboard`) with "Invitations" marked
active, alongside the same top bar and main workspace.

#### Scenario: Authenticated staff views the dashboard
- **WHEN** an authenticated, non-Reception staff member's dashboard finishes loading
- **THEN** the staff sidebar (with "Invitations" selected), the staff top bar, the "Invitations" title row, the search bar, and the kanban board are all visible

#### Scenario: Authenticated Reception user views the dashboard
- **WHEN** an authenticated Reception user's dashboard finishes loading
- **THEN** the Reception sidebar (with "Invitations" marked active), the staff top bar, the "Invitations" title row, the search bar, and the kanban board are all visible

#### Scenario: No inert Help item
- **WHEN** an authenticated staff member views any page with the staff sidebar
- **THEN** no "Help & Support" item is shown

## ADDED Requirements

### Requirement: The staff board opens a status from a deep link
The system SHALL, when the staff Invitations board is opened with a
`status` query parameter naming a known invitation status (`submitted`,
`approved`, `checked_in`, `checked_out`, `denied` or `archived`), apply
that status filter once on load, exactly as if the user had picked it in
the filter bar. The user SHALL be able to clear or change it afterwards. An
unknown `status` value SHALL be ignored, leaving the board unfiltered.

#### Scenario: Open the checked-in visitors from a dashboard
- **WHEN** a staff member opens `/staff/invitations?status=checked_in`
- **THEN** the board shows only checked-in invitations, and the status
  filter shows "Checked in"

#### Scenario: Unknown status ignored
- **WHEN** a staff member opens `/staff/invitations?status=bogus`
- **THEN** the board loads unfiltered, with no error

## REMOVED Requirements

### Requirement: Other sidebar navigation items are visible but not yet functional
**Reason**: There is no help destination, and an inert control is not
allowed on a staff page (`dashboard-insights` "Every Dashboard Control Is
Functional").
**Migration**: The "Help & Support" item is removed from the staff sidebar.
A real help destination can be added in a later change.
