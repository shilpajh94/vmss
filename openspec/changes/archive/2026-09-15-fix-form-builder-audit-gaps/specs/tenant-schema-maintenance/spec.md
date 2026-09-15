## Purpose

Keeps every existing tenant's Postgres schema *and* its seeded RBAC/form
catalog up to date with what a brand-new tenant gets, so a tenant-scoped
migration or a new permission/default shipped alongside new feature code is
actually applied everywhere that feature is reachable, instead of only
being applied to newly provisioned tenants.

## ADDED Requirements

### Requirement: Every Existing Tenant Can Be Upgraded to the Current Migration Head
The system SHALL provide an operation that applies any pending
`alembic_tenant` revisions to every tenant schema currently below the
migration head, without requiring a per-tenant manual invocation.

#### Scenario: Tenant behind head is upgraded
- **WHEN** the upgrade-all-tenants operation runs and a tenant's schema is
  below the current `alembic_tenant` head
- **THEN** that tenant's schema is migrated forward to head and its recorded
  schema version is updated

#### Scenario: Tenant already at head is left unchanged
- **WHEN** the upgrade-all-tenants operation runs and a tenant's schema is
  already at the current `alembic_tenant` head
- **THEN** no migration is applied to that tenant and no error is raised

### Requirement: Upgrading a Tenant Also Re-Syncs Its Standard Role Grants and Default Form Config
The same operation that upgrades a tenant's schema SHALL also grant every
tenant's standard roles any catalog permission they're missing, and
materialize default form-builder steps for a tenant with none configured —
the same two steps a brand-new tenant's provisioning already performs,
applied to an existing tenant instead of only a new one.

#### Scenario: Existing tenant's admin role gains a newly catalogued permission
- **WHEN** the upgrade-all-tenants operation runs and a tenant's standard
  role is missing a permission the current catalog defines for it
- **THEN** that role is granted the missing permission, and every grant it
  already holds beyond the catalog is left untouched

#### Scenario: Existing tenant's role grants already match the catalog
- **WHEN** the upgrade-all-tenants operation runs and a tenant's standard
  roles already hold every permission the current catalog defines for them
- **THEN** no role-permission change is made for that tenant

### Requirement: A Tenant Schema Lagging Behind Head Is Detected Before It Causes a Runtime Failure
The system SHALL be able to report, for every tenant, whether its schema is
at the current `alembic_tenant` migration head, and SHALL log a `WARNING`
during startup when any tenant is behind head.

#### Scenario: Drift is logged at startup
- **WHEN** the application starts and at least one tenant's recorded schema
  version is behind the current `alembic_tenant` head
- **THEN** a `WARNING`-level log entry identifying the lagging tenant(s) is
  emitted
