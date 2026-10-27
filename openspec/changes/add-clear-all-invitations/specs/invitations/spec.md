## ADDED Requirements

### Requirement: Admin Can Clear Invitation Data
The system SHALL let a caller holding `invitations:clear-all` permanently delete invitations in their own tenant (all of them, or only those in an optional visit-date scope), with all dependent records (visitors, vehicles, QR codes, approval steps, custom-field values), via `POST /invitations/clear-all`. The request body MAY contain a scope on the invitation visit date: either `fromDate` and/or `toDate` (inclusive) or `month` (`YYYY-MM`), never both forms. The body MUST contain `confirm` equal to `CLEAR ALL INVITATIONS` when no scope is given, or `CLEAR INVITATIONS` when a scope is given; any other value or a missing body SHALL be rejected with 422 and nothing deleted. The tenant is resolved from the caller's token, never from the request. The operation SHALL be processed in the background and the endpoint SHALL return 202 immediately. A caller lacking the permission SHALL receive 403.

#### Scenario: Admin clears all invitations
- **WHEN** an Admin posts `{"confirm": "CLEAR ALL INVITATIONS"}` to `/invitations/clear-all`
- **THEN** the response is 202 and, once the background run completes, the tenant has no invitation rows and no dependent rows, and other tenants' data is untouched

#### Scenario: Month scope
- **WHEN** an Admin posts `{"month": "2026-09", "confirm": "CLEAR INVITATIONS"}`
- **THEN** only invitations whose visit date is in September 2026 (and their dependents) are deleted

#### Scenario: Inclusive date range
- **WHEN** an Admin posts `fromDate` 2026-09-01 and `toDate` 2026-09-05
- **THEN** invitations visiting on both boundary dates are deleted and those outside the range remain

#### Scenario: Invalid scope
- **WHEN** `month` is combined with `fromDate`/`toDate`, `fromDate` is after `toDate`, or `month` is not `YYYY-MM`
- **THEN** the response is 422 and nothing is deleted

#### Scenario: Invitations without a visit date
- **WHEN** a scoped clear runs
- **THEN** invitations with no visit date are not deleted

#### Scenario: Missing or wrong confirmation
- **WHEN** the request body omits `confirm` or sends any other text
- **THEN** the response is 422 and no invitation is deleted

#### Scenario: Caller lacks permission
- **WHEN** a user without `invitations:clear-all` calls the endpoint
- **THEN** the response is 403 and no invitation is deleted

### Requirement: Clear-All Protects Checked-In Visitors By Default
The system SHALL skip invitations that are currently checked in (status or check-in status `checked_in`) during a clear-all run unless the request sets `includeCheckedIn` to `true`.

#### Scenario: Checked-in visit survives default clear
- **WHEN** a clear-all run executes without `includeCheckedIn` and one invitation is checked in
- **THEN** that invitation and its dependents remain and all others are deleted

#### Scenario: Checked-in visit removed when opted in
- **WHEN** `includeCheckedIn` is `true`
- **THEN** checked-in invitations are deleted as well

### Requirement: Clear-All Is Backed Up, Audited, and Single-Flight
Before deleting each batch, the system SHALL write and verify a backup of the rows to be deleted in the storage tier and SHALL NOT delete the batch if the backup cannot be verified. The system SHALL record one audit entry per run containing the actor, scope, deleted count, and backup keys. Only one clear-all or retention purge run SHALL execute per tenant at a time; a second request while one is running SHALL be rejected with 409. Running the task twice SHALL be safe (a repeat finds nothing left to delete).

#### Scenario: Backup failure aborts deletion
- **WHEN** the backup for a batch fails verification
- **THEN** that batch is not deleted and the failure is logged at ERROR with tenant and run context

#### Scenario: Concurrent request rejected
- **WHEN** a clear-all (or retention purge) is already running for the tenant
- **THEN** a new clear-all request returns 409

#### Scenario: Run is audited
- **WHEN** a run deletes at least one invitation
- **THEN** one audit entry records the actor, scope, count, and backup keys
