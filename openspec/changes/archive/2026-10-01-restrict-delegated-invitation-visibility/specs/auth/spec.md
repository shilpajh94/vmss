## ADDED Requirements

### Requirement: Branch-Wide Invitation Visibility Is a Separate Permission
The permission catalog SHALL include `invitations:view-all`, meaning "may
see every invitation at this branch", distinct from `invitations:view`. The
standard roles SHALL grant it by default to `admin`, `reception`, and
`security`, and SHALL NOT grant it to `host` or `visitor`. When an existing
tenant is upgraded to include this permission, every role in that tenant
that already held `invitations:view` — standard or custom — other than
`host` SHALL additionally be granted `invitations:view-all`, so a role's
existing branch-wide access is preserved rather than silently lost; `host`
SHALL keep `invitations:view` without gaining `invitations:view-all`.

#### Scenario: A newly provisioned tenant's standard roles
- **WHEN** a new tenant is provisioned
- **THEN** its `admin`, `reception`, and `security` roles hold
  `invitations:view-all`, and its `host` role holds `invitations:view` but
  not `invitations:view-all`

#### Scenario: Upgrading an existing tenant preserves a custom role's access
- **WHEN** an existing tenant has a custom role (e.g. "manager") holding
  `invitations:view`, and the tenant is upgraded to the release adding
  `invitations:view-all`
- **THEN** that custom role holds `invitations:view-all` afterward, and the
  `host` role does not

#### Scenario: The upgrade is idempotent
- **WHEN** the tenant upgrade that grants `invitations:view-all` runs a
  second time against the same tenant
- **THEN** no duplicate grant or catalog entry is created and no error is
  raised

#### Scenario: The new permission is listed in the catalog
- **WHEN** a caller with `roles:view` requests the permission catalog
- **THEN** `invitations:view-all` is included
