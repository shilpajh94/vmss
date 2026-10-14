## ADDED Requirements

### Requirement: Reverting an Approval Restarts the Invitation's Workflow From Its First Step
When an invitation that has snapshotted approval steps has its approval
reverted (see the `invitations` capability's "An Approved, Not-Yet-Checked-In
Invitation Can Have Its Approval Reverted"), the system SHALL, in the same
transaction as the status change, reset every one of that invitation's steps
to `pending` — clearing each step's recorded actor, action time, and
delegation — and SHALL make the lowest-`stepOrder` step the invitation's
current pending step again, with its escalation and auto-approve times
computed relative to the moment of the revert. After the revert commits, the
system SHALL notify that first step's approver(s) via the existing
"awaiting approval" push. Steps SHALL be reset regardless of whether they
had been `approved`, `auto_approved`, or `skipped`. The set of steps, their
order, and their snapshotted approver identity and timing values SHALL NOT
change — revert re-runs the workflow captured at submission, it does not
re-snapshot the category's current rules. The invitation's resolved host
SHALL be left unchanged.

Because only an `approved` invitation can be reverted, a step rejection
remains terminal: an invitation denied by a rejected step can never be
reverted or re-opened.

#### Scenario: A fully approved three-step invitation restarts at step 1
- **WHEN** an invitation whose three steps are all `approved` has its
  approval reverted
- **THEN** all three steps are `pending` with no actor or action time, the
  invitation's current approval step is the lowest-`stepOrder` step, and
  that step's approver(s) receive an "awaiting approval" push

#### Scenario: The restarted workflow must be approved in order again
- **WHEN** a caller tries to approve step 2 of a reverted invitation before
  step 1 has been approved again
- **THEN** the request is rejected with 409, as for any out-of-order step

#### Scenario: Completing the restarted workflow re-approves the invitation
- **WHEN** every step of a reverted invitation is approved again in order
- **THEN** the invitation becomes `approved` and the approval notification
  is dispatched, exactly as on the first approval

#### Scenario: Blanket approve stays blocked for a reverted workflow-backed invitation
- **WHEN** a caller calls `POST /invitations/{id}/approve` on a reverted
  invitation that has approval steps
- **THEN** the request is rejected with 409 and the caller must approve
  through the step endpoint

#### Scenario: Delegations are cleared on revert
- **WHEN** a step had been delegated to a specific user before the
  invitation was approved, and the approval is then reverted
- **THEN** that step is `pending` with no delegate, and is actionable by its
  originally snapshotted approver again

#### Scenario: A rule edited after submission does not affect the restart
- **WHEN** the visitor category's approval workflow rules are changed after
  an invitation was submitted, and that invitation's approval is later
  reverted
- **THEN** the reset steps are the ones snapshotted at submission, unchanged
