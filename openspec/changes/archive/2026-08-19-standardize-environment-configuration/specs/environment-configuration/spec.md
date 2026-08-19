## Purpose

Defines how every runtime setting the API depends on (database, cache/broker,
auth secrets, mail, SMS, file storage, CORS, tenancy, logging) is sourced from
environment variables, so no environment-specific value — least of all a
database or cache credential — ships as a real-looking default baked into
source code.

## ADDED Requirements

### Requirement: No Hardcoded Connection Credentials
The system SHALL NOT define a default value for any database, cache, or
message-broker connection setting (host, port, username, password, or a full
connection string) that resolves to a real, usable connection target. Every
such value SHALL be required from the environment, with no fallback other
than a value that is obviously non-functional (e.g. empty) or explicitly
documented as local-development-only in a non-committed file.

#### Scenario: Application refuses to start with no environment configured
- **WHEN** the application is started with no `.env` file present and no
  database-related environment variables set in the process environment
- **THEN** startup fails with a configuration error naming the missing
  setting, rather than silently connecting to a hardcoded host

#### Scenario: Committed example file contains no real credential
- **WHEN** `.env.example` is inspected
- **THEN** every database, cache, and broker value is a placeholder or
  documented as a local-dev-only convenience value, not a credential valid
  against any shared or production system

### Requirement: Database Connection Is Configured By Component Variables
The system SHALL accept the database connection as a set of discrete
environment variables — connection driver, host, port, database name,
username, and password — and SHALL assemble the connection string used to
reach the database from those parts. If a single full database connection
URL is instead present in the environment, the system SHALL use that value
as-is in preference to assembling one from the component variables.

#### Scenario: Component variables produce a working connection
- **WHEN** the connection driver, host, port, database name, username, and
  password are set individually in the environment, and no full connection
  URL is set
- **THEN** the application connects to the database at the specified
  host/port/database using the specified credentials

#### Scenario: A full connection URL overrides component variables
- **WHEN** a full database connection URL is set in the environment
  alongside (or instead of) the component variables
- **THEN** the application connects using the full URL, ignoring any
  component variables also present

### Requirement: Cache and Broker Connections Are Configured By Component Variables
The system SHALL accept the cache/message-broker connection as discrete
host, port, and password environment variables plus a distinct logical
database index per purpose (application cache, task queue broker, task
result backend), and SHALL assemble each purpose's connection target from
those parts. If a full connection URL is instead present for a given
purpose, the system SHALL use that value as-is.

#### Scenario: Distinct logical databases stay isolated
- **WHEN** the cache, task-queue-broker, and task-result-backend logical
  database indices are configured to different values on the same
  host/port
- **THEN** data written for one purpose (e.g. cached lookups) is not visible
  through another purpose's connection (e.g. the task broker)

### Requirement: Every Setting Is Documented in the Example File
The committed environment example file SHALL declare every environment
variable the application reads, grouped by the service or concern it
configures, with each entry either a safe placeholder or a comment
explaining what a real deployment must supply.

#### Scenario: New setting added without a corresponding example entry is a defect
- **WHEN** a new environment-backed setting is added to the application's
  configuration
- **THEN** the example file is updated in the same change to declare that
  setting, so no setting exists that a deployer cannot discover from the
  example file alone

### Requirement: Log Verbosity Is Configurable Without a Code Change
The system SHALL read the minimum log level to emit from an environment
variable, defaulting to a production-safe level, so verbosity can be raised
for diagnosis in a given environment without modifying and redeploying code.

#### Scenario: Debug logging enabled via environment only
- **WHEN** the log-level environment variable is set to a more verbose level
  than the default in a given environment
- **THEN** log lines at that verbosity appear in that environment's output
  without any source code change
