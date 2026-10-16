## Purpose

The admin-devices capability lets an admin review registered kiosk and security devices, and approve, enable, disable, or delete them, so only vetted devices can perform check-in and check-out.

## ADDED Requirements

### Requirement: Device list is fetched by operating mode
The system SHALL load devices from the device list endpoint with `operatingMode=kiosk` on the Reception Desks page and `operatingMode=security` on the Security Gates page, and SHALL render one row per device showing name, device ID, branch, building, approval/active status, approved date, and created date.

#### Scenario: Reception Desks loads kiosk devices
- **WHEN** an admin with `devices:view` opens Reception Desks
- **THEN** the system requests devices with `operatingMode=kiosk` and shows one row per returned device

#### Scenario: Security Gates loads security devices
- **WHEN** an admin with `devices:view` opens Security Gates
- **THEN** the system requests devices with `operatingMode=security`

#### Scenario: No devices
- **WHEN** the list loads with zero devices
- **THEN** the system shows the shared empty state

#### Scenario: Load failure
- **WHEN** the list request fails
- **THEN** the system shows an error message, triggers an error notification, and allows retry

### Requirement: Status filter maps to approval and active status
The system SHALL offer a status filter whose options map to query parameters: Pending Approval → `approvalStatus=pending`; Approved → `approvalStatus=approved&status=active`; Disabled → `approvalStatus=approved&status=inactive`. The system SHALL NOT use a separate pending-devices endpoint.

#### Scenario: Pending Approval selected
- **WHEN** the admin selects "Pending Approval"
- **THEN** the system requests devices with `approvalStatus=pending` and no `status`

#### Scenario: Approved selected
- **WHEN** the admin selects "Approved"
- **THEN** the system requests `approvalStatus=approved&status=active`

#### Scenario: Disabled selected
- **WHEN** the admin selects "Disabled"
- **THEN** the system requests `approvalStatus=approved&status=inactive`

### Requirement: Branch and building filters, paging, and sorting
The system SHALL support filtering by branch and building, paging via `page`/`pageSize`, and sorting by name, created date, or approval status with ascending/descending order, resetting to page 1 when a filter or sort changes.

#### Scenario: Filter changes reset paging
- **WHEN** the admin is on page 3 and changes the branch filter
- **THEN** the system requests page 1 with the new filter

### Requirement: Row actions follow server capability flags
The system SHALL show Approve only when `canApprove` is true, Enable only when `canEnable` is true, and Disable only when `canDisable` is true. Enable and Disable SHALL NOT be shown for devices that are not approved.

#### Scenario: Pending device
- **WHEN** a row has `canApprove` true and `canEnable`/`canDisable` false
- **THEN** only Approve is offered

#### Scenario: Approved active device
- **WHEN** a row has `canDisable` true and `canApprove` false
- **THEN** only Disable is offered

#### Scenario: Approved disabled device
- **WHEN** a row has `canEnable` true
- **THEN** Enable is offered

### Requirement: Approve, enable, and disable update the row
The system SHALL call approve (`devices:approve`), enable, or disable (`devices:manage`) for the chosen device and replace the row with the returned updated device. Approving SHALL result in an active device.

#### Scenario: Approve succeeds
- **WHEN** the admin approves a pending device
- **THEN** the row updates to approved and active and a success notification is shown

#### Scenario: Enable/disable conflict
- **WHEN** enable or disable returns 409 because the device is not approved
- **THEN** the system shows the error message and refreshes the list

### Requirement: Delete requires confirmation
The system SHALL ask for confirmation before deleting a device and, on a 204 response, SHALL remove the row (stepping back a page if the page becomes empty).

#### Scenario: Delete confirmed
- **WHEN** the admin confirms deletion
- **THEN** the device is deleted and disappears from the list

#### Scenario: Delete cancelled
- **WHEN** the admin cancels the confirmation
- **THEN** no request is made

### Requirement: Device pages and actions are permission-gated
The system SHALL require `devices:view` to show the device pages' data, and SHALL hide or disable Approve without `devices:approve` and Enable/Disable/Delete without `devices:manage`. A 403 from the API SHALL be shown as a permission error.

#### Scenario: Lacks devices:view
- **WHEN** a user without `devices:view` opens the page
- **THEN** the system shows a no-access message and does not list devices

#### Scenario: Lacks devices:approve
- **WHEN** a user without `devices:approve` views a pending device
- **THEN** the Approve action is not available

### Requirement: New permissions appear in role management
The system SHALL list `devices:view`, `devices:manage`, `devices:approve`, `settings:view`, and `settings:manage` in the role and permission UI so they can be assigned.

#### Scenario: Permissions listed
- **WHEN** an admin opens a role's permissions
- **THEN** the five new permissions are available to toggle
