## ADDED Requirements

### Requirement: Standard Roles Can Be Resynced Against the Current Permission Catalog
A caller holding `roles:manage` SHALL be able to trigger an idempotent
resync of the tenant's standard roles (Admin, Reception, Security, Host)
against the current permission catalog, granting each standard role any
catalog-defined permission it is currently missing — the same union-merge
`seed_default_roles` already applies at provisioning time — without
removing any permission a role holds that is not part of that role's
catalog-defined default set. The response SHALL report which permissions
were newly granted to which roles.

#### Scenario: A stale standard role is backfilled
- **WHEN** a tenant's Reception role was seeded before a permission (e.g.
  `invitations:view`) existed in the catalog, and a caller with
  `roles:manage` triggers the resync
- **THEN** Reception's permission set includes that permission afterward,
  with no direct database edit required

#### Scenario: Resync is idempotent
- **WHEN** a caller triggers the resync twice in a row with no catalog
  change in between
- **THEN** the second call reports no newly granted permissions and no
  role's permission set changes

#### Scenario: A custom grant beyond the catalog default survives
- **WHEN** a standard role holds a permission an admin granted manually
  that is not part of that role's catalog-defined default set, and the
  resync runs
- **THEN** that permission remains granted on the role afterward

#### Scenario: Caller lacks roles:manage
- **WHEN** a caller without `roles:manage` attempts to trigger the resync
- **THEN** the request is rejected with 403 and no role's permissions
  change
