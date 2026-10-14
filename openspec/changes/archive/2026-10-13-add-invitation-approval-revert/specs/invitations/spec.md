## ADDED Requirements

### Requirement: An Approved, Not-Yet-Checked-In Invitation Can Have Its Approval Reverted
A caller holding `invitations:revert-approval` at the invitation's own branch
SHALL be able to revert an invitation's approval through
`PATCH /api/v1/invitations/{id}/revert-approval`, supplying a mandatory
`reason` of 1–500 characters (surrounding whitespace trimmed; empty or
whitespace-only rejected with 422). Revert SHALL succeed only when the
invitation's `status` is `approved` and its `checkInStatus` is `unused` —
i.e. the visitor has never been admitted. On success the system SHALL:

- transition `status` back to `submitted`, clear `approvedAt`, and record
  `approvalRevertedAt`, `approvalRevertedByUserId`, and
  `approvalRevertReason` (overwriting any values left by an earlier revert);
- return the updated invitation in the standard envelope, including those
  three fields;
- write an `invitation_approval_reverted` audit-log entry naming the actor
  and the invitation;
- dispatch an email to the primary contact stating that the visit's
  approval was withdrawn and that their pass will not admit them until the
  request is reviewed again;
- dispatch a push notification to the invitation's resolved host, if one
  exists — an invitation with no resolved host SHALL skip the push without
  failing the request.

The invitation's existing `expiresAt`, tracking ID, host, visit details, and
issued QR pass SHALL be left unchanged. Reverting an invitation in any other
state — `submitted`, `denied`, `checked_in`, `checked_out`, or `approved`
with a `checkInStatus` other than `unused` — SHALL be rejected with 409 and
SHALL NOT change the invitation or dispatch any notification. An unknown
invitation id SHALL be rejected with 404; a caller lacking the permission,
or holding it only at a different branch, SHALL be rejected with 403. The
transition SHALL be atomic: of two concurrent revert requests for the same
invitation, exactly one SHALL succeed and dispatch notifications, and the
other SHALL receive 409.

#### Scenario: Reverting a manually approved invitation
- **WHEN** a caller with `invitations:revert-approval` at the invitation's
  branch reverts an `approved` invitation with `checkInStatus` `unused`,
  giving a reason
- **THEN** the response is 200, `status` is `submitted`, `approvedAt` is
  null, `approvalRevertedAt`/`approvalRevertedByUserId`/
  `approvalRevertReason` are set, an `invitation_approval_reverted` audit
  entry is recorded, and the primary contact is emailed

#### Scenario: Reverting an auto-approved invitation
- **WHEN** an invitation that was auto-approved at creation (no approval
  steps) is reverted
- **THEN** it becomes `submitted` exactly like a manually approved one, and
  can then be approved through `POST /invitations/{id}/approve` or denied
  through `PATCH /invitations/{id}/deny`

#### Scenario: Reason is mandatory
- **WHEN** a revert request omits `reason`, or sends an empty or
  whitespace-only reason, or one longer than 500 characters
- **THEN** the request is rejected with 422 and the invitation is unchanged

#### Scenario: A checked-in or checked-out invitation cannot be reverted
- **WHEN** a caller attempts to revert an invitation whose status is
  `checked_in` or `checked_out`
- **THEN** the request is rejected with 409 and the invitation is unchanged

#### Scenario: An approved invitation whose visitor has already entered cannot be reverted
- **WHEN** a caller attempts to revert an invitation whose status is
  `approved` but whose `checkInStatus` is not `unused`
- **THEN** the request is rejected with 409 and the invitation is unchanged

#### Scenario: A submitted or denied invitation cannot be reverted
- **WHEN** a caller attempts to revert an invitation whose status is
  `submitted` or `denied`
- **THEN** the request is rejected with 409 and no notification is
  dispatched

#### Scenario: Caller lacks invitations:revert-approval
- **WHEN** a caller holding `invitations:approve` but not
  `invitations:revert-approval` attempts to revert an approved invitation
- **THEN** the request is rejected with 403 and the invitation stays
  `approved`

#### Scenario: Caller holds the permission only at another branch
- **WHEN** a caller with `invitations:revert-approval` only at branch A
  attempts to revert an approved invitation at branch B
- **THEN** the request is rejected with 403, not 404

#### Scenario: Unknown invitation id
- **WHEN** a caller names an invitation id that does not exist
- **THEN** the request is rejected with 404

#### Scenario: Concurrent reverts result in exactly one transition
- **WHEN** two otherwise-authorized revert requests for the same approved
  invitation are processed concurrently
- **THEN** exactly one succeeds and dispatches notifications, and the other
  is rejected with 409

#### Scenario: Revert notifies the host
- **WHEN** an invitation with a resolved host has its approval reverted
- **THEN** the host user receives a push notification stating the approval
  was reverted

#### Scenario: Revert of an invitation with no resolved host still succeeds
- **WHEN** an invitation whose host never resolved has its approval reverted
- **THEN** the request succeeds and no push notification is dispatched

#### Scenario: Revert is invisible to another tenant
- **WHEN** a caller authenticated against tenant A names the id of an
  approved invitation that exists only in tenant B
- **THEN** the request is rejected with 404 and tenant B's invitation is
  unchanged

### Requirement: A Reverted Invitation's Pass Does Not Admit the Visitor Until Re-Approved
While an invitation is `submitted` following an approval revert, every
check-in path — QR scan, staff check-in, and public tracking-ID check-in —
SHALL reject it exactly as it rejects any other not-yet-approved invitation,
even though the visitor still holds the QR pass issued at the original
approval. When the invitation is approved again (directly, or by completing
its restarted approval workflow), the system SHALL dispatch the approval
notification again carrying the same QR pass issued originally, and that
pass SHALL admit the visitor again.

#### Scenario: QR scan of a reverted invitation is rejected
- **WHEN** a visitor scans the QR pass of an invitation whose approval was
  reverted and which is still `submitted`
- **THEN** check-in is rejected and the invitation stays `submitted` with
  `checkInStatus` `unused`

#### Scenario: Re-approval restores the original pass
- **WHEN** a reverted invitation is approved again
- **THEN** its status becomes `approved`, `approvedAt` is set to the new
  approval time, the approval notification is dispatched with the same QR
  token as the original approval, and a scan of that pass is admitted

#### Scenario: Re-denial after revert
- **WHEN** a reverted invitation is denied with a reason
- **THEN** it becomes `denied` and the denial notification is dispatched,
  exactly as for any other submitted invitation
