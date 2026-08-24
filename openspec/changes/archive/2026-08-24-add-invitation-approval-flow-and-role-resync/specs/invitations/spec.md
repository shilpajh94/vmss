## MODIFIED Requirements

### Requirement: Employee Creates a Fully Completed Invitation in a Single Call
The system SHALL let an authenticated, branch-scoped employee holding
`invitations:create` create a complete invitation — `registrationType`,
primary contact with ID proof, an ordered co-visitor list (group
registrations only) each with their own ID proof, visit details, carried
items, vehicles, and consent — in one `multipart/form-data` call, submitting
each visitor's and the primary contact's ID proof as a separate file part
matched by order, and generating a human-readable tracking ID immediately.
The invitation's initial status is resolved from the tenant's auto-approve
setting rather than always being `submitted` — see "Invitation Creation's
Initial Approval State Follows the Company's Auto-Approve Setting" below.
Since nothing in the payload identifies a branch, the system SHALL resolve
the target branch from the `X-Branch-ID` header; a request supplying
neither the header nor any other branch signal SHALL be rejected with 400.

#### Scenario: Invitation creation returns a tracking ID with the invitation already complete
- **WHEN** an employee with `invitations:create` at their authorized branch
  creates an invitation with the full payload and ID-proof files
- **THEN** the response includes a tracking ID and a status resolved per
  the company's auto-approve setting, with no further action required to
  complete the visit record when that status is `approved`

#### Scenario: Caller lacks permission
- **WHEN** a user without `invitations:create` attempts to create an
  invitation
- **THEN** the system returns 403 and creates no invitation record

#### Scenario: Missing branch signal is rejected
- **WHEN** a caller submits `POST /invitations` with no `X-Branch-ID` header
- **THEN** the request is rejected with 400, since the system has no other
  way to determine which branch the invitation belongs to

### Requirement: Visit Confirmation With QR Code Is Dispatched on Creation
When an invitation is created, the system SHALL dispatch a visit-
confirmation notification to the primary contact via their preferred
contact method (email or SMS), asynchronously and without delaying the
creation response, and SHALL retry transient delivery failures with
backoff up to a configured limit. Whether that notification includes a QR
code depends on the invitation's resulting status — see "Invitation
Creation's Initial Approval State Follows the Company's Auto-Approve
Setting" below; a QR code is never included until the invitation is
`approved`.

#### Scenario: Creation response does not wait on delivery
- **WHEN** an invitation is created
- **THEN** the API responds with the invitation details before the
  confirmation has necessarily been delivered

#### Scenario: Delivery failure is retried and eventually surfaced
- **WHEN** the email/SMS provider is unavailable for a confirmation dispatch
- **THEN** the system retries with backoff and, if retries are exhausted,
  logs the failure with enough context to identify and manually resend the
  confirmation

## ADDED Requirements

### Requirement: Invitation Creation's Initial Approval State Follows the Company's Auto-Approve Setting
The system SHALL resolve a newly created invitation's initial status from
the tenant's `Company.autoApprovePreRegisteredVisitors` setting: `approved`
when it is enabled, or `submitted` (awaiting approval) when it is disabled
or when no `Company` profile is configured yet for the tenant. WHEN the
resulting status is `approved`, the system SHALL dispatch the approval
notification — the tracking ID and a QR code encoding it — to the primary
contact. WHEN the resulting status is `submitted`, the system SHALL
dispatch a tracking-only notification — the tracking ID and current
status, with no QR code — and SHALL NOT dispatch the QR-bearing
notification until the invitation is later approved (see "A Submitted
Invitation Can Be Manually Approved").

#### Scenario: Auto-approve enabled creates an already-approved invitation
- **WHEN** the tenant's `Company.autoApprovePreRegisteredVisitors` is
  `true` and an employee creates an invitation
- **THEN** the invitation's status is `approved`, its `approvedAt`
  timestamp is set, and the dispatched notification includes the tracking
  ID and a QR code

#### Scenario: Auto-approve disabled creates an awaiting-approval invitation
- **WHEN** the tenant's `Company.autoApprovePreRegisteredVisitors` is
  `false` and an employee creates an invitation
- **THEN** the invitation's status is `submitted`, its `approvedAt` is
  unset, and the dispatched notification includes only the tracking ID and
  current status — no QR code

#### Scenario: No configured company profile defaults to awaiting approval
- **WHEN** an invitation is created for a tenant with no `Company` profile
  configured yet
- **THEN** the invitation is treated the same as auto-approve disabled —
  status `submitted`, tracking-only notification, no QR code

### Requirement: A Submitted Invitation Can Be Manually Approved
A caller holding `invitations:approve` at the invitation's own branch SHALL
be able to transition a `submitted` invitation to `approved`, recording an
`approvedAt` timestamp, and the system SHALL then dispatch the approval
notification (tracking ID + QR code) to the primary contact — the same
notification an auto-approved invitation receives at creation. Approving an
invitation that is not currently `submitted` SHALL be rejected with 409,
leaving its status unchanged. An invitation id that does not exist at all
SHALL be rejected with 404. A caller who lacks branch access to an
invitation that does exist SHALL be rejected with 403 — the same
branch-authorization behavior `POST /invitations` itself already applies
when resolving a branch it doesn't otherwise know from the request.

#### Scenario: Manual approval transitions status and dispatches the QR notification
- **WHEN** a caller with `invitations:approve` at the invitation's branch
  approves a `submitted` invitation
- **THEN** the invitation's status becomes `approved`, `approvedAt` is set,
  and the approval notification (tracking ID + QR code) is dispatched to
  the primary contact

#### Scenario: Approving an already-approved invitation is rejected
- **WHEN** a caller attempts to approve an invitation whose status is
  already `approved`
- **THEN** the request is rejected with 409 and no second notification is
  dispatched

#### Scenario: Caller lacks invitations:approve
- **WHEN** a caller without `invitations:approve` attempts to approve a
  `submitted` invitation
- **THEN** the request is rejected with 403, the invitation's status is
  unchanged, and no notification is dispatched

#### Scenario: Unknown invitation id is rejected with 404
- **WHEN** a caller names an invitation id that does not exist
- **THEN** the request is rejected with 404

#### Scenario: Caller lacks branch access to an existing invitation
- **WHEN** a caller with `invitations:approve` only at a different branch
  attempts to approve an invitation that exists at another branch
- **THEN** the request is rejected with 403, not 404 — the invitation's
  existence is not hidden, only the caller's access to act on it is denied
