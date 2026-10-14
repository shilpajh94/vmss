## ADDED Requirements

### Requirement: A Local Environment Can Be Pruned to Only Its Default Tenant
The system SHALL provide a maintenance operation that removes every tenant
except the default tenant, which is named by the configured default tenant
slug. For each other tenant, the operation SHALL remove:
- its Postgres schema,
- its rows in every global table that references a tenant (the user-index
  entries, the schema-version record, registration device keys and
  platform audit events) and its tenant registry row,
- its cache keys, and
- its locally stored files.

The default tenant's schema, its rows in those global tables, its cache
keys and its stored files SHALL remain unchanged.

Without explicit confirmation, the operation SHALL only report what it
would remove and SHALL change nothing. It SHALL refuse to run, changing
nothing, when the environment is anything other than local or testing, or
when the default tenant doesn't exist. All database removals for one run
SHALL be applied in a single transaction, so a failure leaves every tenant
as it was.

#### Scenario: Extra tenant is removed and the default tenant is kept
- **WHEN** the operation runs with confirmation in a local environment that
  has the default tenant and one other tenant
- **THEN** the other tenant's schema, its global rows, its registry row, its
  cache keys and its stored files no longer exist, and the default
  tenant's schema contents, global rows, cache keys and stored files are
  unchanged

#### Scenario: Dry run changes nothing
- **WHEN** the operation runs without confirmation
- **THEN** it lists each tenant it would remove, with the row, key and file
  counts, and every tenant, schema, row, key and file still exists afterwards

#### Scenario: Refuses outside local and testing
- **WHEN** the operation runs with confirmation and the environment is
  `production` or `staging`
- **THEN** it exits with an error and nothing is removed

#### Scenario: Refuses when the default tenant is missing
- **WHEN** the operation runs with confirmation and no tenant has the
  configured default slug
- **THEN** it exits with an error and nothing is removed

#### Scenario: Only the default tenant exists
- **WHEN** the operation runs with confirmation and the default tenant is
  the only tenant
- **THEN** it reports that there is nothing to remove and changes nothing

### Requirement: Pruning Also Removes Cache Keys and Files Left by Unregistered Tenants
The same operation SHALL also remove cache keys and locally stored files
filed under a tenant id that matches no registered tenant, such as those
left behind by test runs that share the local storage folder and cache.
Only entries named with a well-formed tenant id SHALL be considered. The
default tenant's cache keys and files, and any entry not named with a
tenant id, SHALL be left untouched. Without confirmation, the orphaned
entries SHALL only be counted and reported.

#### Scenario: Orphaned test files and keys are removed
- **WHEN** the operation runs with confirmation and the local storage folder
  and cache hold entries filed under tenant ids that aren't registered
- **THEN** those entries are removed, and the default tenant's files and
  keys and any non-tenant entries remain

#### Scenario: Orphans are only reported on a dry run
- **WHEN** the operation runs without confirmation
- **THEN** it reports how many orphaned folders and keys it found, and none
  are removed

