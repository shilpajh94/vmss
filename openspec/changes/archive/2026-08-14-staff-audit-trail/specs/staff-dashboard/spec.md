## MODIFIED Requirements

### Requirement: Other sidebar navigation items are visible but not yet functional
The system SHALL render the "Help & Support" link per the design, but SHALL NOT navigate anywhere when it is activated.

#### Scenario: Inert nav item activated
- **WHEN** a staff member activates "Help & Support"
- **THEN** the current view does not change

## ADDED Requirements

### Requirement: "Audit trail" opens the Audit Trail page
The system SHALL, when a staff member activates "Audit trail" in the sidebar, navigate to the Audit Trail page.

#### Scenario: Staff opens Audit trail
- **WHEN** an authenticated staff member activates "Audit trail" in the sidebar
- **THEN** the system navigates to the Audit Trail page
