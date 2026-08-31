## MODIFIED Requirements

### Requirement: A Submitted Invitation Can Be Manually Approved
A caller holding `invitations:approve` at the invitation's own branch SHALL
be able to transition a `submitted` invitation to `approved` through this
endpoint only when the invitation has no approval steps snapshotted against
it (its `visitorCategoryId` had no active `ApprovalWorkflowRule` at
submission time, AND its host did not resolve to an active user at
submission time — see the `approvals` capability's "Submission Snapshots
the Category's Active Workflow Into Ordered Steps") — recording an
`approvedAt` timestamp, and the system SHALL then dispatch the approval
notification (tracking ID + QR code) to the primary contact — the same
notification an auto-approved invitation receives at creation. Calling this
endpoint for an invitation that does have snapshotted approval steps
(whether host-identified, role-identified, or both) SHALL be rejected with
409 and SHALL NOT change the invitation's status: that invitation must be
approved step by step through `POST /invitations/{id}/approval-
steps/{stepId}/approve`. Approving an invitation that is not currently
`submitted` SHALL be rejected with 409, leaving its status unchanged. An
invitation id that does not exist at all SHALL be rejected with 404. A
caller who lacks branch access to an invitation that does exist SHALL be
rejected with 403 — the same branch-authorization behavior `POST
/invitations` itself already applies when resolving a branch it doesn't
otherwise know from the request.

#### Scenario: Manual approval transitions status and dispatches the QR notification
- **WHEN** a caller with `invitations:approve` at the invitation's branch
  approves a `submitted` invitation whose category has no configured
  approval workflow and whose host did not resolve to a user (no
  snapshotted steps)
- **THEN** the invitation's status becomes `approved`, `approvedAt` is set,
  and the approval notification (tracking ID + QR code) is dispatched to
  the primary contact

#### Scenario: Blanket approve rejected for a workflow-backed invitation
- **WHEN** a caller calls `POST /invitations/{id}/approve` for an invitation
  that has one or more snapshotted `InvitationApprovalStep` rows
- **THEN** the request is rejected with 409, the invitation's status is
  unchanged, and no notification is dispatched — the caller must approve
  through the step endpoint instead

#### Scenario: Blanket approve rejected when only a host-approval step is snapshotted
- **WHEN** a caller calls `POST /invitations/{id}/approve` for an invitation
  whose category has zero active `ApprovalWorkflowRule` rows but whose host
  resolved to a user at submission (one snapshotted host-identified step)
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

## ADDED Requirements

### Requirement: Invitation Output Surfaces the Resolved Host as hostId
`InvitationOut` and `InvitationDetailOut` SHALL include `hostId`, set to the
invitation's resolved host user id when submission resolved `hostId` or
`hostNameOrEmail` to an active user, and null when it did not — alongside
the existing free-text `hostNameOrEmail`, unchanged.

#### Scenario: Resolved host is surfaced as hostId
- **WHEN** an invitation whose host resolved to an active user at
  submission is fetched via `GET /invitations` (list) or `GET
  /invitations/{id}` (detail)
- **THEN** the response includes `hostId` set to that user's id, alongside
  the existing `hostNameOrEmail`

#### Scenario: Unresolved host leaves hostId null
- **WHEN** an invitation created with only a free-text `hostNameOrEmail`
  that did not resolve to an active user is fetched
- **THEN** the response includes `hostId` as null, with `hostNameOrEmail`
  unchanged
