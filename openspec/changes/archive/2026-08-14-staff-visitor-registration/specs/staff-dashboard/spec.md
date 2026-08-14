## MODIFIED Requirements

### Requirement: Other sidebar navigation items are visible but not yet functional
The system SHALL render the "Audit trail" sidebar item and the "Help & Support" link per the design, but SHALL NOT navigate anywhere when they are activated.

#### Scenario: Inert nav item activated
- **WHEN** a staff member activates "Audit trail" or "Help & Support"
- **THEN** the current view does not change

## ADDED Requirements

### Requirement: "My actions" opens the Register Visitor wizard
The system SHALL, when a staff member activates "My actions" in the sidebar, navigate to the Register Visitor wizard's first step.

#### Scenario: Staff opens My actions
- **WHEN** an authenticated staff member activates "My actions" in the sidebar
- **THEN** the system navigates to the Register Visitor wizard, showing the Visitor Info step
