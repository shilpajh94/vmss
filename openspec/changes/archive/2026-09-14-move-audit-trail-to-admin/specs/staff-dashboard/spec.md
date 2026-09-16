## MODIFIED Requirements

### Requirement: Dashboard renders the sidebar, workspace header, and kanban board
The system SHALL render, for an authenticated session, a sidebar (brand mark, "All visitors" / "My actions" navigation with "All visitors" selected, and a "Help & Support" link) and a main workspace containing the header, search bar, and visit-requests kanban board.

#### Scenario: Authenticated staff views the dashboard
- **WHEN** an authenticated staff member's dashboard finishes loading
- **THEN** the sidebar, the "Visits" workspace header, the search bar, and the kanban board are all visible

## REMOVED Requirements

### Requirement: "Audit trail" opens the Audit Trail page
**Reason**: The Audit Trail page is removed from the staff portal; it moves to the Admin portal as an admin-only page (see `admin-audit-trail`). The sidebar no longer has an "Audit trail" item.
**Migration**: None. Staff no longer have an Audit Trail entry point.
