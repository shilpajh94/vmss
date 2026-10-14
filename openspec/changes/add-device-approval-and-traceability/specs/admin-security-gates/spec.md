## REMOVED Requirements

### Requirement: Security gate list loads on page entry
**Reason**: The list now shows security devices from the device endpoint.
**Migration**: See `admin-devices` "Device list is fetched by operating mode".

## ADDED Requirements

### Requirement: Security Gates page lists security devices
The system SHALL render the Security Gates page at `/admin/security-gates` as the device list filtered to security devices, with the behaviors defined in `admin-devices`, and SHALL NOT offer the legacy Register/Edit Gate form or call the legacy security-gate endpoints from it.

#### Scenario: Page content
- **WHEN** an authenticated admin opens `/admin/security-gates`
- **THEN** the system shows security devices with status/branch/building filters and row actions

#### Scenario: Legacy routes
- **WHEN** a browser navigates to `/admin/security-gates/new` or `/admin/security-gates/:id/edit`
- **THEN** the system redirects to `/admin/security-gates`
