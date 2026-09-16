## MODIFIED Requirements

### Requirement: Dashboard renders the sidebar, workspace header, and kanban board
The system SHALL render, for an authenticated non-Reception session, a sidebar (brand mark, "All visitors" / "My actions" navigation with "All visitors" selected, and a "Help & Support" link) and a main workspace containing the header, search bar, and visit-requests kanban board. For an authenticated Reception session, the system SHALL instead render the Reception sidebar (see `reception-dashboard`) with "Visits" marked active, alongside the same main workspace.

#### Scenario: Authenticated staff views the dashboard
- **WHEN** an authenticated, non-Reception staff member's dashboard finishes loading
- **THEN** the staff sidebar, the "Visits" workspace header, the search bar, and the kanban board are all visible

#### Scenario: Authenticated Reception user views the dashboard
- **WHEN** an authenticated Reception user's dashboard finishes loading
- **THEN** the Reception sidebar (with "Visits" marked active), the "Visits" workspace header, the search bar, and the kanban board are all visible
