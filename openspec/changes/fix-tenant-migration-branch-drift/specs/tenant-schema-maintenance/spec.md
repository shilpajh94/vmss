## MODIFIED Requirements

### Requirement: Every Existing Tenant Can Be Upgraded to the Current Migration Head
The system SHALL provide an operation that applies any pending
`alembic_tenant` revisions to every tenant schema currently below the
migration head, without requiring a per-tenant manual invocation. If the
`alembic_tenant` revision tree itself currently has more than one head,
the operation SHALL fail with an explicit, actionable error instead of
applying migrations from only one branch or leaving tenants in an
inconsistent state.

#### Scenario: Tenant behind head is upgraded
- **WHEN** the upgrade-all-tenants operation runs and a tenant's schema is
  below the current `alembic_tenant` head
- **THEN** that tenant's schema is migrated forward to head and its recorded
  schema version is updated

#### Scenario: Tenant already at head is left unchanged
- **WHEN** the upgrade-all-tenants operation runs and a tenant's schema is
  already at the current `alembic_tenant` head
- **THEN** no migration is applied to that tenant and no error is raised

#### Scenario: Migration tree has multiple heads
- **WHEN** the upgrade-all-tenants operation runs and the `alembic_tenant`
  revision tree currently has more than one head
- **THEN** the operation fails with an explicit, actionable error
  identifying the ambiguous heads, and no tenant schema is partially
  migrated from just one of the unmerged branches

### Requirement: A Tenant Schema Lagging Behind Head Is Detected Before It Causes a Runtime Failure
The system SHALL be able to report, for every tenant, whether its schema is
at the current `alembic_tenant` migration head, and SHALL log a `WARNING`
during startup when any tenant is behind head. If the `alembic_tenant`
revision tree itself currently has more than one head, the system SHALL
treat that as a distinct, higher-severity condition and log an `ERROR`
during startup rather than silently skipping the drift check or reporting
tenants as up to date.

#### Scenario: Drift is logged at startup
- **WHEN** the application starts and at least one tenant's recorded schema
  version is behind the current `alembic_tenant` head
- **THEN** a `WARNING`-level log entry identifying the lagging tenant(s) is
  emitted

#### Scenario: Migration tree has multiple heads at startup
- **WHEN** the application starts and the `alembic_tenant` revision tree
  currently has more than one head
- **THEN** an `ERROR`-level log entry identifying the ambiguous heads is
  emitted, distinct from the ordinary per-tenant-lag `WARNING`, and no
  tenant is reported as being up to date while the tree is ambiguous
