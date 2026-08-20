## MODIFIED Requirements

### Requirement: Employee Creates a Fully Completed Invitation in a Single Call
The system SHALL let an authenticated employee holding `invitations:create`
create a complete invitation — `registrationType`, primary contact with ID
proof, an ordered co-visitor list (group registrations only) each with their
own ID proof, visit details, carried items, vehicles, and consent — in one
`multipart/form-data` call, submitting each visitor's and the primary
contact's ID proof as a separate file part matched by order, and generating
a human-readable tracking ID immediately. There is no separate step to
complete afterward. Since nothing in the payload identifies a branch, the
system SHALL resolve the target branch from the `X-Branch-ID` header; a
request supplying neither the header nor any other branch signal SHALL be
rejected with 400.

#### Scenario: Invitation creation returns a tracking ID with the invitation already complete
- **WHEN** an employee with `invitations:create` at their authorized branch
  creates an invitation with the full payload and ID-proof files
- **THEN** the response includes a tracking ID and `status: submitted`, with
  no further action required to complete the visit record

#### Scenario: Caller lacks permission
- **WHEN** a user without `invitations:create` attempts to create an
  invitation
- **THEN** the system returns 403 and creates no invitation record

#### Scenario: Missing branch signal is rejected
- **WHEN** a caller submits `POST /invitations` with no `X-Branch-ID` header
- **THEN** the request is rejected with 400, since the system has no other
  way to determine which branch the invitation belongs to
