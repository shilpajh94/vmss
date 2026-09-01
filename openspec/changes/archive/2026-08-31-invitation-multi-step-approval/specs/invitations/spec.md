## MODIFIED Requirements

### Requirement: Employee Creates a Fully Completed Invitation in a Single Call
The system SHALL let an authenticated, branch-scoped employee holding
`invitations:create` create a complete invitation — `registrationType`, a
`visitorCategoryId` referencing an active `VisitorCategory` in the resolved
tenant, primary contact with ID proof, an ordered co-visitor list (group
registrations only) each with their own ID proof, visit details, carried
items, vehicles, and consent — in one `multipart/form-data` call, submitting
each visitor's and the primary contact's ID proof as a separate file part
matched by order, and generating a human-readable tracking ID immediately.
`visitorCategoryId` is mandatory; a request omitting it or naming a category
that does not exist, is inactive, or belongs to a different tenant SHALL be
rejected with a validation error before any invitation is created. The
invitation's initial status is resolved from the tenant's auto-approve
setting rather than always being `submitted` — see "Invitation Creation's
Initial Approval State Follows the Company's Auto-Approve Setting" below.
Since nothing in the payload identifies a branch, the system SHALL resolve
the target branch from the `X-Branch-ID` header; a request supplying
neither the header nor any other branch signal SHALL be rejected with 400.

#### Scenario: Invitation creation returns a tracking ID with the invitation already complete
- **WHEN** an employee with `invitations:create` at their authorized branch
  creates an invitation with the full payload, a valid `visitorCategoryId`,
  and ID-proof files
- **THEN** the response includes a tracking ID, the `visitorCategoryId` that
  was submitted, and a status resolved per the company's auto-approve
  setting, with no further action required to complete the visit record when
  that status is `approved`

#### Scenario: Caller lacks permission
- **WHEN** a user without `invitations:create` attempts to create an
  invitation
- **THEN** the system returns 403 and creates no invitation record

#### Scenario: Missing branch signal is rejected
- **WHEN** a caller submits `POST /invitations` with no `X-Branch-ID` header
- **THEN** the request is rejected with 400, since the system has no other
  way to determine which branch the invitation belongs to

#### Scenario: Missing visitor category is rejected
- **WHEN** a creation request omits `visitorCategoryId`
- **THEN** the system rejects the request with a 422 validation error and
  creates no invitation record

#### Scenario: Unknown, inactive, or cross-tenant visitor category is rejected
- **WHEN** a creation request's `visitorCategoryId` does not resolve to an
  active `VisitorCategory` in the resolved tenant's schema
- **THEN** the system rejects the request with a validation error and
  creates no invitation record

### Requirement: A Submitted Invitation Can Be Manually Approved
A caller holding `invitations:approve` at the invitation's own branch SHALL
be able to transition a `submitted` invitation to `approved` through this
endpoint only when the invitation has no approval steps snapshotted against
it (its `visitorCategoryId` had no active `ApprovalWorkflowRule` at
submission time) — recording an `approvedAt` timestamp, and the system
SHALL then dispatch the approval notification (tracking ID + QR code) to the
primary contact — the same notification an auto-approved invitation receives
at creation. Calling this endpoint for an invitation that does have
snapshotted approval steps SHALL be rejected with 409 and SHALL NOT change
the invitation's status: that invitation must be approved step by step
through `POST /invitations/{id}/approval-steps/{stepId}/approve`. Approving
an invitation that is not currently `submitted` SHALL be rejected with 409,
leaving its status unchanged. An invitation id that does not exist at all
SHALL be rejected with 404. A caller who lacks branch access to an
invitation that does exist SHALL be rejected with 403 — the same
branch-authorization behavior `POST /invitations` itself already applies
when resolving a branch it doesn't otherwise know from the request.

#### Scenario: Manual approval transitions status and dispatches the QR notification
- **WHEN** a caller with `invitations:approve` at the invitation's branch
  approves a `submitted` invitation whose category has no configured
  approval workflow (no snapshotted steps)
- **THEN** the invitation's status becomes `approved`, `approvedAt` is set,
  and the approval notification (tracking ID + QR code) is dispatched to
  the primary contact

#### Scenario: Blanket approve rejected for a workflow-backed invitation
- **WHEN** a caller calls `POST /invitations/{id}/approve` for an invitation
  that has one or more snapshotted `InvitationApprovalStep` rows
- **THEN** the request is rejected with 409, the invitation's status is
  unchanged, and no notification is dispatched — the caller must approve
  through the step endpoint instead

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

### Requirement: Public Lookup by Tracking ID Returns Everything Captured at Creation
Any caller SHALL be able to retrieve an invitation's full detail by
supplying its human-readable tracking ID, without authentication, subject to
rate limiting. The response SHALL include every field captured during
creation — including `visitorCategoryId`, visit details (purpose, host,
date, time, expected duration, department, additional notes), and carried
items (categories and description) — not only a subset. WHEN the invitation
has one or more snapshotted approval steps and its status is `submitted`,
the response SHALL additionally include the current pending step's
`stepOrder`, `approverRoleId`, and the total number of steps, so a caller
can be shown progress (e.g. "step 2 of 3") instead of a single undated
"awaiting approval" status. WHEN the invitation has no snapshotted steps, or
is no longer `submitted`, this step-progress information SHALL be omitted
(null) rather than fabricated.

#### Scenario: Valid tracking ID returns full detail
- **WHEN** a caller requests the tracking endpoint with a tracking ID that
  exists
- **THEN** the response includes the invitation's status, `visitorCategoryId`,
  `expectedDuration`, `departmentToVisit`, `additionalNotes`,
  `carriedItems`/`carriedItemsDescription`, and visitor/vehicle detail,
  matching exactly what was captured at creation

#### Scenario: Workflow-backed invitation exposes current step progress
- **WHEN** a caller looks up a `submitted` invitation that has snapshotted
  approval steps
- **THEN** the response includes the current pending step's `stepOrder`,
  `approverRoleId`, and the total step count

#### Scenario: Non-workflow invitation omits step progress
- **WHEN** a caller looks up an invitation with no snapshotted approval
  steps, or one that is no longer `submitted`
- **THEN** the response's step-progress fields are null

#### Scenario: Unknown tracking ID
- **WHEN** a caller requests the tracking endpoint with a tracking ID that
  does not exist
- **THEN** the system returns a not-found result

#### Scenario: Repeated lookups are throttled
- **WHEN** a caller exceeds the configured rate limit for the tracking
  endpoint
- **THEN** the system rejects further requests with the standard error
  envelope until the limit window resets

### Requirement: Employee Lists Invitations at Their Authorized Branches
The system SHALL let an authenticated caller holding `invitations:view` list
invitations, paginated, sorted, and filterable by `status`,
`registrationType`, and `source`. A request supplying `X-Branch-ID` SHALL be
narrowed to that one branch, rejected with 404/403 the same way other
branch-scoped endpoints reject an unknown or unauthorized branch id. A
request omitting `X-Branch-ID` SHALL return invitations across every branch
the caller holds `invitations:view` at, rejected with 403 only if that set
is empty. Each row in the response SHALL include enough detail to identify
and triage the invitation (tracking ID, registration type, source, status,
`visitorCategoryId`, primary contact name, purpose of visit, expiry/
submission timestamps) without the per-row visitor/vehicle detail the
single-invitation tracking lookup returns.

#### Scenario: Caller with company-wide access lists across all their branches
- **WHEN** a caller with `invitations:view` granted company-wide requests
  `GET /invitations` without an `X-Branch-ID` header
- **THEN** the response includes invitations from every branch, paginated
  per the requested page/pageSize

#### Scenario: X-Branch-ID narrows the result to one branch
- **WHEN** a caller with `invitations:view` at a specific branch requests
  `GET /invitations` with that branch's `X-Branch-ID`
- **THEN** the response includes only that branch's invitations

#### Scenario: Unauthorized branch id rejected
- **WHEN** a caller requests `GET /invitations` with an `X-Branch-ID` for a
  branch they are not authorized to view invitations at
- **THEN** the system returns 403 and no invitation data

#### Scenario: Caller lacks permission everywhere
- **WHEN** a caller with no `invitations:view` grant at any branch requests
  `GET /invitations` without an `X-Branch-ID` header
- **THEN** the system returns 403

#### Scenario: Filtering by status, registration type, and source
- **WHEN** a caller requests `GET /invitations` with `status`,
  `registrationType`, and/or `source` query parameters set
- **THEN** the response includes only invitations matching every supplied
  filter

#### Scenario: Sorting is validated against a whitelist
- **WHEN** a caller requests `GET /invitations` with a `sortBy` value that
  is not one of the endpoint's documented sortable fields
- **THEN** the system rejects the request with a validation error rather
  than passing the value through to the database

#### Scenario: List rows omit visitor and vehicle detail
- **WHEN** a caller lists invitations via `GET /invitations`
- **THEN** each row includes tracking ID, registration type, source,
  status, `visitorCategoryId`, primary contact name, purpose of visit, and
  expiry/submission timestamps, and does not include the per-visitor or
  per-vehicle detail that `GET /invitations/track` returns for a single
  invitation

## ADDED Requirements

### Requirement: Approval-Step Rejection Denies the Invitation
Rejecting any snapshotted `InvitationApprovalStep` SHALL immediately
transition its invitation to the existing `denied` terminal state —
recording a denial reason and `deniedAt` timestamp, and dispatching the
existing denial notification — the same outcome as calling
`POST /invitations/{id}/deny` directly. Rejection is terminal: no step,
including one earlier in the sequence, becomes actionable again, and the
invitation cannot subsequently be approved. This applies regardless of
which step in the sequence is rejected — a rejection at step 1 of 3 has the
same terminal effect as a rejection at step 3 of 3.

#### Scenario: Rejecting any step denies the invitation
- **WHEN** an approver rejects a pending `InvitationApprovalStep`, at any
  `stepOrder`
- **THEN** the invitation's status becomes `denied`, a denial reason and
  `deniedAt` are recorded, and the denial notification is dispatched

#### Scenario: A denied invitation cannot later be approved
- **WHEN** a caller attempts to approve any step, or call the blanket
  approve endpoint, on an invitation already `denied` by a step rejection
- **THEN** the request is rejected with 409 and the invitation's status is
  unchanged
