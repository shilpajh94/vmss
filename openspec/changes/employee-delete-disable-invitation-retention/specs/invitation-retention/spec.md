## Purpose

Bounds how long invitation records and the visitor personal data attached to
them are kept, by purging old invitations on a schedule after first taking a
verified backup, so data can be recovered if a purge was unwanted.

## ADDED Requirements

### Requirement: Scheduled Purge of Invitations Past the Retention Window

The system SHALL run a scheduled job, at a configured time of day, that
permanently deletes each active tenant's invitations whose reference date is
older than the configured retention period (`INVITATION_RETENTION_DAYS`). The
reference date SHALL be the invitation's visit date, falling back to its
creation date when no visit date is set. Each tenant SHALL be processed
independently: one tenant's failure SHALL NOT prevent other tenants' purges.

An invitation SHALL NOT be purged while its visitor is still checked in
(`check_in_status` of checked-in without a check-out), regardless of age.

Purging an invitation SHALL also remove its dependent records (visitors, QR
code, vehicles, approval steps). Records of other kinds (audit log entries,
users) SHALL NOT be removed.

#### Scenario: Old invitation is purged

- **WHEN** the job runs and an invitation's reference date is older than the retention period
- **THEN** the invitation and its dependent records no longer exist after the run

#### Scenario: Recent invitation is kept

- **WHEN** the job runs and an invitation's reference date is within the retention period
- **THEN** it is not modified

#### Scenario: Visitor still inside is never purged

- **WHEN** an invitation is older than the retention period but its visitor is checked in and not checked out
- **THEN** it is not purged

#### Scenario: One tenant's failure is isolated

- **WHEN** the purge for one tenant fails
- **THEN** other tenants' purges still run and the failure is logged at `ERROR` with the tenant identifier

#### Scenario: Retention disabled

- **WHEN** `INVITATION_RETENTION_DAYS` is unset or zero
- **THEN** the job deletes nothing

### Requirement: Backup Is Taken and Verified Before Any Deletion

Before deleting any invitation, the job SHALL write a backup of exactly the
rows it intends to delete (invitations and their dependent records) to the
object-storage tier, under a tenant-scoped, server-generated key, and SHALL
confirm the backup is readable and its record count matches. If the backup
cannot be written or verified, the job SHALL delete nothing for that tenant and
SHALL log the failure at `ERROR` and retry per the retry policy.

The backup SHALL be encrypted at rest to the same standard as other stored
PII, and SHALL NOT be publicly accessible. A run that finds nothing to purge
SHALL NOT create an empty backup.

#### Scenario: Backup precedes deletion

- **WHEN** the job purges N invitations
- **THEN** a backup containing those N invitations exists and was verified before the first row was deleted

#### Scenario: Backup failure blocks deletion

- **WHEN** writing or verifying the backup fails
- **THEN** no invitations for that tenant are deleted and an `ERROR` log is emitted

#### Scenario: Nothing to purge

- **WHEN** no invitation is past the retention window
- **THEN** no backup file is created and nothing is deleted

### Requirement: Purge Is Idempotent and Auditable

The purge job SHALL be safe to run twice for the same period: a redelivered or
repeated run SHALL NOT delete rows that were not in its backup, and SHALL NOT
fail because rows were already purged. Each run that deletes data SHALL write
one audit entry per tenant recording the cutoff date, number of invitations
purged, and the backup's storage key. Logs SHALL NOT contain visitor personal
data.

#### Scenario: Repeated run is harmless

- **WHEN** the job runs twice in succession
- **THEN** the second run purges nothing and does not error

#### Scenario: Run is recorded

- **WHEN** a run purges invitations
- **THEN** an audit entry records the cutoff, the count, and the backup key
