# background-jobs Specification

## Purpose

Cross-cutting requirements every Celery task in this system must satisfy —
covering both request-triggered tasks (e.g. invitation-confirmation
dispatch) and scheduled, time-triggered tasks (e.g. the reports snapshot) —
so a broker redelivery, a crash mid-run, or a transient downstream failure
never corrupts state or goes unnoticed.

## Requirements

### Requirement: Idempotent Task Execution
Every background task SHALL be safe to execute more than once with the same
input. A task SHALL check the current state of the entity it acts on before
performing a side effect (e.g. sending a notification, mutating a record)
rather than assuming it is the first and only execution.

#### Scenario: Redelivered task does not duplicate its side effect
- **WHEN** a task is redelivered and re-executed for the same logical event
  (e.g. after a worker crash, or a broker at-least-once redelivery)
- **THEN** the side effect that a first successful execution already
  performed is not repeated a second time

#### Scenario: Task acting on a since-removed entity is a no-op
- **WHEN** a task runs against an entity id that no longer exists (e.g. the
  row was deleted between enqueue and execution)
- **THEN** the task returns without error and without attempting the side
  effect, rather than raising

### Requirement: Explicit Retry Policy for External-System Tasks
Every task that calls an external system (email/SMS provider, object
storage) SHALL declare an explicit retry policy — which exceptions trigger a
retry, a backoff strategy, and a maximum retry count. A task SHALL NOT retry
indefinitely with no backoff, and SHALL NOT fail silently on a transient
error with no retry at all.

#### Scenario: Transient failure is retried with backoff
- **WHEN** a task's call to an external system fails with a transient error
- **THEN** the task retries the call, with each retry delayed by a backoff
  interval rather than retrying immediately

#### Scenario: Retry count is bounded
- **WHEN** a task's external-system call keeps failing
- **THEN** the task stops retrying once its declared maximum retry count is
  reached, rather than retrying forever

### Requirement: Retry Exhaustion Is Logged With Enough Context to Reprocess
A task that exhausts its retries SHALL log at `ERROR` with enough context —
at minimum the tenant identifier and the entity type/id it was acting on —
that a human can locate and manually reprocess the failed event.

#### Scenario: Exhausted task logs actionable context
- **WHEN** a task exhausts its configured maximum retries
- **THEN** an `ERROR`-level log line is emitted carrying the tenant
  identifier and the entity type and id the task was acting on

### Requirement: Request and Tenant Context Is Correlated Into Task Execution
A task enqueued from a request SHALL receive that request's correlation id
as a task argument and re-bind it into the structured logger's context at
the start of the task body, so every log line the task emits carries the
same `request_id` as the request that triggered it. A task resolves its own
tenant-scoped database session explicitly from a tenant argument it
receives — it SHALL NOT assume a single shared schema is already in scope.

#### Scenario: Task log lines carry the triggering request's correlation id
- **WHEN** a request enqueues a task and the task later executes
- **THEN** every log line the task emits carries the same `request_id` as
  the request that enqueued it

#### Scenario: Task resolves its own tenant schema
- **WHEN** a task that needs database access executes
- **THEN** it resolves the tenant-scoped session itself from a tenant
  argument passed at enqueue time, rather than relying on any
  ambient/default schema

### Requirement: Scheduled Tasks Run Independently of Any Request
The job runner SHALL support recurring, time-triggered tasks that execute on
a schedule rather than being dispatched from a request. A scheduled task
that operates across every tenant SHALL process each tenant independently,
so that a failure processing one tenant does not prevent the others from
being processed.

#### Scenario: A scheduled task runs without any triggering HTTP request
- **WHEN** a task is registered on a recurring schedule
- **THEN** it executes at each scheduled interval with no request in the
  call chain that dispatched it

#### Scenario: One tenant's failure does not block another tenant's run
- **WHEN** a scheduled task that iterates every active tenant encounters an
  error processing one tenant
- **THEN** it still processes every other tenant in that same scheduled run
