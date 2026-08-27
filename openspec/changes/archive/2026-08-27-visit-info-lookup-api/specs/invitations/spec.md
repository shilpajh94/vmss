## ADDED Requirements

### Requirement: Visit Details Optionally Accept Catalog IDs Alongside Free Text
`VisitDetailsSubmit` (used by both `POST /invitations` and `POST
/registrations/walk-in`) SHALL accept optional `purposeId`, `hostId`,
`durationId`, and `departmentId` fields alongside its existing
`purposeOfVisit`, `hostNameOrEmail`, `expectedDuration`, `departmentToVisit`
free-text fields. When any id is supplied, the system SHALL validate it
against the corresponding catalog/`Department`/`User` record, scoped to the
resolved tenant, and SHALL overwrite the paired free-text field with that
record's canonical display value before persisting, regardless of what
free-text value the request also supplied for that field. When an id is
omitted, its paired free-text field is accepted and stored exactly as
submitted, unchanged from today's behavior.

#### Scenario: Submission with no ids behaves exactly as before
- **WHEN** a caller submits `purposeOfVisit`, `hostNameOrEmail`,
  `expectedDuration`, `departmentToVisit` with no `purposeId`/`hostId`/
  `durationId`/`departmentId`
- **THEN** the invitation is created with exactly the submitted free-text
  values, identical to today's behavior

#### Scenario: Submission with an id overwrites free text with the catalog value
- **WHEN** a caller submits `departmentId` referencing an active department,
  along with a `departmentToVisit` string that does not match that
  department's name
- **THEN** the invitation is created with `departmentToVisit` set to the
  referenced department's actual name, not the client-supplied string

#### Scenario: Unknown or cross-tenant id is rejected
- **WHEN** a caller submits an id (`purposeId`, `hostId`, `durationId`, or
  `departmentId`) that does not resolve to an existing, active row in the
  resolved tenant's schema
- **THEN** the request is rejected with a validation error and no invitation
  is created

#### Scenario: Walk-in registration inherits the same optional fields
- **WHEN** a caller submits `POST /registrations/walk-in` with any of
  `purposeId`/`hostId`/`durationId`/`departmentId`
- **THEN** the same validation and free-text overwrite behavior applies,
  since it submits the identical `VisitDetailsSubmit` shape
