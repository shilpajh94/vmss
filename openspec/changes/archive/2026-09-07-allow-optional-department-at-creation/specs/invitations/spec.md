## MODIFIED Requirements

### Requirement: Visit Details Optionally Accept Catalog IDs Alongside Free Text
`VisitDetailsSubmit` (used by both `POST /invitations` and `POST
/registrations/walk-in`) SHALL accept optional `purposeId`, `durationId`, and
`departmentId` fields alongside its existing `purposeOfVisit`,
`expectedDuration` free-text fields and its optional `departmentToVisit`
free-text field. When any id is supplied, the system SHALL validate it
against the corresponding catalog/`Department` record, scoped to the
resolved tenant, and SHALL overwrite the paired free-text field with that
record's canonical display value before persisting, regardless of what
free-text value the request also supplied for that field. When an id is
omitted, its paired free-text field is accepted and stored exactly as
submitted, unchanged from today's behavior. `departmentToVisit` SHALL be
optional — a request may omit it (and `departmentId`) entirely, leaving the
invitation's department unset at creation, since a visitor or the staff
member creating the invitation on their behalf often does not yet know
which internal department is relevant; the field can be filled in later via
`PATCH /invitations/{id}/edit`. `VisitDetailsSubmit` SHALL NOT accept
`hostId` or `hostNameOrEmail` from either channel — the host is never
client-supplied at creation (see "Every New Invitation Is Owned by the
Tenant's Default Host Role at Creation"); a request that includes either
field SHALL have it ignored rather than rejected, so an un-updated client
does not start failing outright.

#### Scenario: Submission with no ids behaves exactly as before
- **WHEN** a caller submits `purposeOfVisit`, `expectedDuration`,
  `departmentToVisit` with no `purposeId`/`durationId`/`departmentId`
- **THEN** the invitation is created with exactly the submitted free-text
  values, identical to today's behavior

#### Scenario: Submission with an id overwrites free text with the catalog value
- **WHEN** a caller submits `departmentId` referencing an active department,
  along with a `departmentToVisit` string that does not match that
  department's name
- **THEN** the invitation is created with `departmentToVisit` set to the
  referenced department's actual name, not the client-supplied string

#### Scenario: Unknown or cross-tenant id is rejected
- **WHEN** a caller submits an id (`purposeId`, `durationId`, or
  `departmentId`) that does not resolve to an existing, active row in the
  resolved tenant's schema
- **THEN** the request is rejected with a validation error and no invitation
  is created

#### Scenario: Walk-in registration inherits the same optional fields
- **WHEN** a caller submits `POST /registrations/walk-in` with any of
  `purposeId`/`durationId`/`departmentId`
- **THEN** the same validation and free-text overwrite behavior applies,
  since it submits the identical `VisitDetailsSubmit` shape

#### Scenario: A supplied hostId or hostNameOrEmail is silently ignored
- **WHEN** a caller submits `POST /invitations` or `POST
  /registrations/walk-in` with `hostId` and/or `hostNameOrEmail` set (e.g. an
  un-updated client)
- **THEN** the invitation is created successfully, with those values ignored
  entirely — the invitation's host is never set from them, and no validation
  error is raised for supplying them

#### Scenario: Submission with no department succeeds and leaves it unset
- **WHEN** a caller submits `POST /invitations` or `POST
  /registrations/walk-in` with neither `departmentToVisit` nor
  `departmentId` set
- **THEN** the invitation is created successfully, with `departmentToVisit`
  null — no validation error is raised for omitting it, and no request-level
  default or placeholder value is substituted

#### Scenario: An unset department is later filled in via edit
- **WHEN** an invitation created with no department is subsequently edited
  via `PATCH /invitations/{id}/edit` to set `departmentToVisit`
- **THEN** the edit succeeds exactly as it would for any other eligible
  invitation, per the existing "Authorized Caller Edits Non-Personal
  Invitation Details" requirement
