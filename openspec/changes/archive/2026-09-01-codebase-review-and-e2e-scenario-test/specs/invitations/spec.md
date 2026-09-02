## MODIFIED Requirements

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
when resolving a branch it doesn't otherwise know from the request. The
invitation's recorded `branchId` is already-persisted historical data, not
caller-supplied input, so branch authorization for approval SHALL succeed
based on that recorded id even if the branch has since been soft-deleted —
approval SHALL NOT fail with a branch-not-found error for an invitation
that otherwise exists and is `submitted`. The transition itself SHALL be
atomic: when two approval requests for the same invitation are processed
concurrently, exactly one SHALL succeed and exactly one approval
notification SHALL be dispatched — the other SHALL observe the same 409
"not currently submitted" outcome the sequential already-approved case
produces, never a duplicate transition or a duplicate notification.

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

#### Scenario: Approving an invitation whose branch was soft-deleted after submission
- **WHEN** a caller with `invitations:approve` at the invitation's recorded
  branch approves a `submitted` invitation whose `branchId` refers to a
  `Branch` that has since been soft-deleted
- **THEN** the approval succeeds exactly as it would have before the branch
  was deleted — the invitation's status becomes `approved`, `approvedAt` is
  set, and the approval notification is dispatched

#### Scenario: Concurrent approval requests result in exactly one transition
- **WHEN** two approval requests for the same `submitted` invitation are
  processed concurrently, both otherwise authorized
- **THEN** exactly one request transitions the invitation to `approved` and
  dispatches the approval notification, and the other is rejected with 409
  as if the invitation were already approved
