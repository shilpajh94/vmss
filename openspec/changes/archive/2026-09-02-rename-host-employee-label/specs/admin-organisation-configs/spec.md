## MODIFIED Requirements

### Requirement: Admin sidebar renders all admin navigation sections with "Organisation Configs" active
The system SHALL render, for an authenticated session, a sidebar with the brand mark and navigation items — Dashboard, Organisation Configs, Branches, Departments, Buildings, Floors, Reception Desks, Security Gates, Employees, Visitor Categories — with "Organisation Configs" shown as the active item.

#### Scenario: Admin views the Organisation Configs page
- **WHEN** an authenticated admin's Organisation Configs page finishes loading
- **THEN** the sidebar shows all ten navigation items with "Organisation Configs" marked active

### Requirement: Only "Organisation Configs" sidebar navigation is functional
The system SHALL render the other nine sidebar navigation items (Dashboard, Branches, Departments, Buildings, Floors, Reception Desks, Security Gates, Employees, Visitor Categories) per the design, but SHALL NOT navigate anywhere when any of them is activated.

#### Scenario: Inert nav item activated
- **WHEN** an admin activates a sidebar navigation item other than "Organisation Configs"
- **THEN** the current view does not change
