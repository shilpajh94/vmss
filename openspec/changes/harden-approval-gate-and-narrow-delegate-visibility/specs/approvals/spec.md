## ADDED Requirements

### Requirement: A Step Cannot Be Delegated or Actioned While an Earlier Step Is Still Pending
For an invitation with snapshotted approval steps, a step at `stepOrder` N
SHALL be delegable, approvable, or rejectable only when it is the
invitation's current pending step — i.e., only when every step at a lower
`stepOrder` has already been approved (never merely delegated: delegation
alone does not change a step's `pending` status). In particular, no step
beyond the `stepOrder` 0 ownership step can be delegated, approved, or
rejected until that ownership step has itself been approved — whether
directly by a holder of the tenant's default host role, or by whoever that
role delegated the step to. This holds regardless of which authorization
clause a caller would otherwise satisfy: the invitation's resolved host
(delegation clause (a)), a caller who holds `invitations:approve-override`,
and a caller who personally approved the immediately preceding step
(delegation clause (d)) are all still subject to this ordering guarantee —
none of them can act on or delegate a step that is not yet current. A
caller attempting to delegate, approve, or reject a step that is not
currently the invitation's current pending step SHALL be rejected with 409,
and no step's or invitation's status, delegate, or host assignment SHALL
change as a result.

#### Scenario: Delegating the ownership step's delegate does not itself unlock the next step
- **WHEN** the `stepOrder` 0 ownership step has been delegated to a
  specific host, but that host has not yet approved it (the step remains
  `pending`), and the resolved host calls
  `POST /invitations/{id}/approval-steps/{stepId}/delegate` on the
  invitation's `stepOrder` 1 step
- **THEN** the request is rejected with 409, no delegation is recorded on
  `stepOrder` 1, and the invitation's `hostId` is unchanged

#### Scenario: An override-permission holder still cannot skip ahead of a pending earlier step
- **WHEN** a caller holding `invitations:approve` and
  `invitations:approve-override` at the invitation's branch calls the
  delegate endpoint on a `stepOrder` 1 step while the invitation's
  `stepOrder` 0 step is still `pending` (approved by no one, delegated or
  not)
- **THEN** the request is rejected with 409 and no delegation is recorded,
  even though the override permission would otherwise bypass the
  role/host/delegate match

#### Scenario: The ownership step's own delegate approving it unlocks the next step for delegation
- **WHEN** the `stepOrder` 0 ownership step, delegated to a specific host,
  is approved by that host, making `stepOrder` 1 the invitation's current
  pending step
- **THEN** a caller authorized on `stepOrder` 1 (its role-holder, the
  resolved host, the `stepOrder` 0 approver via clause (d), or an
  override-permission holder) may now delegate, approve, or reject it

#### Scenario: Reception approving the ownership step directly, without ever delegating it, also unlocks the next step
- **WHEN** a holder of the tenant's default host role approves the
  invitation's `stepOrder` 0 step directly (never having delegated it to
  anyone), making `stepOrder` 1 the current pending step
- **THEN** `stepOrder` 1 becomes delegable/actionable exactly as it would
  had `stepOrder` 0 instead been delegated then approved by its delegate —
  the guarantee is that `stepOrder` 0 was approved by someone, not that it
  was ever delegated
