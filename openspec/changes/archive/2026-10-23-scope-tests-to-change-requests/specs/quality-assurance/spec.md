## ADDED Requirements

### Requirement: Change-request verification is scoped to the change
When a change request or a suggestion task is implemented, verification SHALL run
only the targeted test set, not the full test suite. The targeted test set is:
- the test modules of every feature package the change edits;
- the test modules of every other area that depends on the changed code, meaning
  it imports it, calls it, or consumes its output (for example a shared `core`
  helper, a schema, a background task, a tenant migration, or a response shape the
  web client reads);
- the API documentation tests, when the change adds, removes, or registers a route
  or a response schema.

When a change touches no code that other areas depend on, only the change's own
feature tests SHALL be run.

When a task step asks for a full suite run, the targeted test set SHALL be run in
its place. The task's completion note SHALL say that targeted tests were run
instead.

The full suite SHALL still run in two cases: in the CI merge gate, and when the
user explicitly asks for a full run.

The verification report for a change SHALL list the test modules that were run and
their result. It SHALL name any dependent area that was included, with the reason.

#### Scenario: Self-contained change
- **WHEN** a change edits only one feature package and no other area depends on the edited code
- **THEN** only that feature's test modules are run, and the full suite is not run

#### Scenario: Change with a dependent area
- **WHEN** a change edits code that another feature imports or consumes
- **THEN** both the changed feature's tests and the dependent feature's tests are run, and the report names the dependent area and why it was included

#### Scenario: Route or schema change
- **WHEN** a change adds, removes, or registers a route or a response schema
- **THEN** the API documentation tests are run as part of the targeted set

#### Scenario: Task asks for a full suite
- **WHEN** a tasks.md step says to run the full suite during implementation
- **THEN** the targeted test set is run instead, and the task's note records that substitution

#### Scenario: User asks for a full run
- **WHEN** the user explicitly asks for the full suite
- **THEN** the full suite is run

#### Scenario: CI gate is unchanged
- **WHEN** a branch is proposed for merge
- **THEN** the CI gate still runs the full test suite
