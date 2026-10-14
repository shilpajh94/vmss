## ADDED Requirements

### Requirement: Approval Revert Is a Separate Permission Granted to Approving Roles by Default
The permission catalog SHALL include `invitations:revert-approval`, distinct
from `invitations:approve`, so a tenant can let a role approve without
letting it undo approvals (or vice versa). The standard roles SHALL grant it
by default to `admin`, `reception`, and `host`, and SHALL NOT grant it to
`security` or `visitor`. When an existing tenant is upgraded to this
release, its standard `admin`, `reception`, and `host` roles SHALL each be
granted `invitations:revert-approval` if they do not already hold it. The
upgrade SHALL NOT grant it to `security` or any custom role, and SHALL NOT
remove any existing grant. Tenant-defined roles MAY be given the permission
through the normal role-editing endpoints.

#### Scenario: A newly provisioned tenant's approving roles can revert
- **WHEN** a new tenant is provisioned
- **THEN** its `admin`, `reception`, and `host` roles hold
  `invitations:revert-approval`, and its `security` and `visitor` roles do
  not

#### Scenario: The permission is in the catalog
- **WHEN** a caller lists the permission catalog or creates a custom role
  with `invitations:revert-approval`
- **THEN** the code is present and accepted

#### Scenario: Security cannot revert an approval
- **WHEN** a user holding only the `security` role calls the revert-approval
  endpoint for an approved invitation at their branch
- **THEN** the request is rejected with 403 and the invitation stays
  `approved`

#### Scenario: Upgrading an existing tenant backfills the approving roles
- **WHEN** an existing tenant whose standard roles lack
  `invitations:revert-approval` is upgraded to this release
- **THEN** its `admin`, `reception`, and `host` roles hold the permission
  afterward, and its `security` role and any custom role are unchanged

#### Scenario: The upgrade is idempotent
- **WHEN** the upgrade that grants `invitations:revert-approval` runs a
  second time against the same tenant
- **THEN** no duplicate grant is created and no error is raised
