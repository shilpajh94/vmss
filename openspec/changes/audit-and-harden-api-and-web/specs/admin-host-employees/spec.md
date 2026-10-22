## ADDED Requirements

### Requirement: Creating an Employee Never Alters Any Other Employee
Adding a single employee SHALL create only that employee, through the API's
single-employee creation. It SHALL NOT resubmit the employee directory.
Every other employee's active status, employee code and details SHALL be
unchanged by the create, however many employees the tenant has.

#### Scenario: Tenant with more than 100 employees
- **WHEN** an admin adds one employee to a tenant that already has 150
  active employees with codes
- **THEN** the tenant has 151 active employees afterwards, and none of the
  existing 150 was deactivated or had its code changed

## REMOVED Requirements

### Requirement: Import Hosts is presented but not yet functional
**Reason**: A visible control that does nothing is dead UI. Bulk import is
tracked as a future feature (gap register G16, `add-employee-import`).
**Migration**: None for users. The control is removed until import is built.
