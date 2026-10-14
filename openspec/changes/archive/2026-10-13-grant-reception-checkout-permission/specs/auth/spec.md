## ADDED Requirements

### Requirement: Reception Holds the Staff Check-Out Permission by Default
The standard roles SHALL grant `invitations:checkout` by default to `admin`,
`reception`, and `security`, and SHALL NOT grant it to `host` or `visitor`.
When an existing tenant is upgraded to this release, its standard
`reception` role SHALL be granted `invitations:checkout` if it does not
already hold it. The upgrade SHALL NOT grant the permission to `host` or to
any custom role, and SHALL NOT remove any existing grant.

#### Scenario: A newly provisioned tenant's Reception role can check visitors out
- **WHEN** a new tenant is provisioned
- **THEN** its `admin`, `reception`, and `security` roles hold
  `invitations:checkout`, and its `host` and `visitor` roles do not

#### Scenario: Reception checks out a checked-in visitor
- **WHEN** a user holding only the `reception` role at a branch calls
  `PATCH /api/v2/invitations/{id}/check-out` for a `checked_in` invitation
  at that branch
- **THEN** the request succeeds, the invitation becomes `checked_out`, and
  it records that user as the one who checked it out (`checkedOutByUserId`
  on the invitation detail)

#### Scenario: Reception at a different branch is still rejected
- **WHEN** a user holding the `reception` role only at branch A calls the
  check-out endpoint for a `checked_in` invitation at branch B
- **THEN** the request is rejected with 403 and the invitation stays
  `checked_in`

#### Scenario: Host still cannot check visitors out
- **WHEN** a user holding only the `host` role calls the check-out endpoint
  for a `checked_in` invitation they host
- **THEN** the request is rejected with 403 and the invitation stays
  `checked_in`

#### Scenario: Upgrading an existing tenant backfills Reception
- **WHEN** an existing tenant's `reception` role lacks
  `invitations:checkout` and the tenant is upgraded to this release
- **THEN** its `reception` role holds `invitations:checkout` afterward, and
  its `host` role and any custom role are unchanged

#### Scenario: The upgrade is idempotent
- **WHEN** the upgrade that grants Reception `invitations:checkout` runs a
  second time against the same tenant
- **THEN** no duplicate grant is created and no error is raised
