## Purpose

Gives VMSS a repeatable QA harness. It checks the API and the web portal at three
levels: API regression, browser end to end, and load. A committed findings report
says whether any release blocker is still open.

## ADDED Requirements

### Requirement: Idempotent shared QA fixtures
The harness SHALL provide one fixture seeder, used by every QA suite. It SHALL create
the following in the local default tenant, and nowhere else:
- QA users for every role under test: admin, reception, security, host, approver,
  no-role, and a reception user scoped to the second branch only.
- Branches MAIN and QA-B.
- Visitor categories `QA_SINGLE` (one approval step) and `QA_MULTI` (reception, then
  host).

Running the seeder repeatedly SHALL NOT create duplicate rows or fail. The seeder
SHALL NOT create, or depend on, any tenant other than the default tenant.

#### Scenario: First run seeds fixtures
- **WHEN** the seeder runs against a default tenant with no QA fixtures
- **THEN** every QA user, branch and category exists, and each user holds its intended role and branch scope

#### Scenario: Re-run is a no-op
- **WHEN** the seeder runs a second time
- **THEN** it exits successfully, and the count of QA users, branches and categories does not change

#### Scenario: Refuses a non-default tenant
- **WHEN** the seeder is pointed at any tenant other than the default tenant
- **THEN** it exits with a non-zero status and writes nothing

### Requirement: API regression runner covers every router
The harness SHALL provide an API regression runner. It SHALL call, over HTTP, the
main endpoints of every feature router registered in the API. For each call it SHALL
record:
- the endpoint and method,
- the acting role,
- the expected and actual status code,
- whether the response matches the standard `{success, message, data}` envelope,
- the latency.

The runner SHALL exit non-zero when any call returns a 5xx status, returns a status
other than the expected one, or returns a JSON body that does not use the envelope.

#### Scenario: Happy path per router
- **WHEN** the runner executes against a seeded local stack
- **THEN** each registered feature router has at least one endpoint called with a permitted role, and that call returns its expected 2xx status

#### Scenario: Permission denied is enforced
- **WHEN** the no-role QA user calls a permission-protected endpoint
- **THEN** the runner records a 403 enveloped error, and any other status is reported as a failure

#### Scenario: Branch scoping is enforced
- **WHEN** the QA-B-only reception user requests a MAIN-branch resource with `X-Branch-ID` set to MAIN
- **THEN** the request is rejected, and a successful response is reported as a failure

#### Scenario: Server error fails the run
- **WHEN** any call returns a 5xx status
- **THEN** the runner exits non-zero, and its output names the endpoint, the role and the response's request id

#### Scenario: Unknown router is flagged
- **WHEN** a feature router is registered in the API but has no entry in the runner
- **THEN** the runner reports that router as uncovered and exits non-zero

### Requirement: Browser end-to-end suite for critical portal journeys
The harness SHALL provide a browser suite. It SHALL drive the web portal against the
local API and cover:
- admin login,
- org-structure create and edit,
- form builder step editing,
- visitor category and workflow setup,
- staff invitation create → approve → check-in → check-out,
- the reception dashboard,
- visitor self-request and visit tracking,
- RBAC route guarding.

A journey SHALL fail when any of the following happens during it:
- an assertion fails,
- an uncaught page error occurs,
- an API response with status 5xx is observed.

On failure, the suite SHALL save a screenshot and a trace for that journey.

#### Scenario: Invitation lifecycle in the browser
- **WHEN** the suite creates an invitation as a host for category `QA_MULTI`, approves it as reception and then as the host-approver, checks it in, and checks it out
- **THEN** each step's status is visible in the portal UI, and the final status is checked out

#### Scenario: Route guarding
- **WHEN** a user without admin permissions opens an `/admin/*` route
- **THEN** the portal does not render the admin page content, and the user sees a redirect or an access-denied state

#### Scenario: Console error fails the journey
- **WHEN** an uncaught JavaScript error or a 5xx API response occurs during a journey
- **THEN** that journey is marked failed, and its screenshot and trace are saved

### Requirement: Load test with a recorded baseline
The harness SHALL provide a load test. It SHALL exercise these paths:
- authenticated reads: dashboards and the invitation list,
- writes: invitation create, check-in and check-out,
- the public visit lookup.

It SHALL run at a configurable number of concurrent users, defaulting to 50. It SHALL
report p50, p95 and p99 latency and the error rate for each endpoint. The run SHALL
fail when any of these holds:
- the aggregate p95 latency is 500 ms or more,
- the aggregate error rate is 1% or more,
- any 5xx response occurs.

The load test SHALL run only against the local default tenant, unless a different
target is explicitly configured.

#### Scenario: Baseline run passes thresholds
- **WHEN** the load test runs with 50 users for its default duration against a seeded local stack
- **THEN** it writes per-endpoint statistics to a file, and exits zero when the aggregate p95 is below 500 ms, the error rate is below 1% and no 5xx occurred

#### Scenario: Threshold breach fails the run
- **WHEN** the aggregate p95 is at or above 500 ms, or the error rate is at or above 1%
- **THEN** the run exits non-zero, and its output names the endpoints that exceeded the thresholds

#### Scenario: Load-test data does not leak into real data
- **WHEN** the load test creates invitations
- **THEN** every created record is identifiable as QA data, by a `QA LOAD` name prefix and the QA categories, and can be removed by the QA reset tooling

### Requirement: Blocker classification and findings report
Every failure found by the pytest suite, the API runner, the browser suite or the
load test SHALL be classified as a blocker or a non-blocker. A blocker is any of the
following:
- a 5xx on a core flow,
- a broken core visitor journey (invite, approve, check-in, check-out, self-request),
- data visible across tenants or across branches it should not be,
- an authentication or permission bypass,
- a crash or a blank page in the portal,
- a load-test error-rate breach, or any 5xx, on a core endpoint.

A load-test latency breach on its own (aggregate p95 at or above the limit
with errors and 5xx under their limits) measured on the local stack SHALL be
recorded in the report as a capacity baseline, with the concurrency the gate
does pass at and a named follow-up change. It is not a blocker, because the
local stack does not represent production sizing.

The harness SHALL produce a committed findings report. For each finding, the report
SHALL list:
- the suite that found it,
- its classification,
- reproduction steps,
- the fixing commit, or the follow-up change it was deferred to.

The report SHALL state the overall verdict. The verdict SHALL be "no open blockers"
only when every blocker has a fixing commit and a passing re-run.

#### Scenario: Blocker fixed and re-verified
- **WHEN** a blocker is fixed
- **THEN** the suite that found it is re-run and passes, and the report records the fixing commit and the passing re-run

#### Scenario: Non-blocker deferred
- **WHEN** a finding is classified as a non-blocker
- **THEN** the report records it with reproduction steps and a named follow-up, and it does not prevent a "no open blockers" verdict

#### Scenario: Local latency-only breach is a recorded baseline
- **WHEN** the local load test breaches only the p95 limit, with errors under 1% and no 5xx
- **THEN** the report records the per-endpoint numbers, the highest passing concurrency and a follow-up change, and does not count it as a blocker

#### Scenario: Open blocker prevents a clean verdict
- **WHEN** any blocker has no fixing commit or no passing re-run
- **THEN** the report's verdict states that blockers are open, and lists them
