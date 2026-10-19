## REMOVED Requirements

### Requirement: Add Reception Desk navigates to a dedicated page
**Reason**: Reception Desks now lists self-registered kiosk devices; desks are no longer created or edited by admins here.
**Migration**: Kiosk devices register themselves via the mobile app and are approved on this page (see `admin-devices`).

### Requirement: Adding a reception desk requires a name and a building
**Reason**: The Add/Edit Reception Desk form is removed along with the legacy desk register.
**Migration**: Use device registration plus approval (see `admin-devices`).

### Requirement: Reception desk list loads on page entry
**Reason**: The list now shows kiosk devices from the device endpoint.
**Migration**: See `admin-devices` "Device list is fetched by operating mode".

## ADDED Requirements

### Requirement: Reception Desks page lists kiosk devices
The system SHALL render the Reception Desks page at `/admin/reception-desks` as the device list filtered to kiosk devices, with the behaviors defined in `admin-devices`, and SHALL NOT call the legacy reception-desk or `/kiosks` endpoints from it.

#### Scenario: Page content
- **WHEN** an authenticated admin opens `/admin/reception-desks`
- **THEN** the system shows kiosk devices with status/branch/building filters and row actions

#### Scenario: Legacy routes
- **WHEN** a browser navigates to `/admin/reception-desks/new` or `/admin/reception-desks/:id/edit`
- **THEN** the system redirects to `/admin/reception-desks`
