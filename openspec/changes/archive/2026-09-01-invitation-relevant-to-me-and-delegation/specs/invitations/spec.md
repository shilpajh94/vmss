## ADDED Requirements

### Requirement: Caller Lists Invitations Relevant to Themselves via relevantToMe
`GET /invitations` SHALL accept a `relevantToMe` boolean query parameter.
WHEN `relevantToMe` is true, the system SHALL return invitations where the
authenticated caller is either (a) the user identified by that invitation's
`stepOrder` 0 host-identified `InvitationApprovalStep` (i.e. the snapshotted
host), or (b) the delegate assigned to any of that invitation's approval
steps (see the `approvals` capability's "Host Delegates the Step Following
Their Own to a Specific Person" requirement) — regardless of that step's or
the invitation's current status. This filter SHALL NOT require the caller
to hold `invitations:view`, and SHALL NOT be scoped by `X-Branch-ID` or the
caller's authorized branches: it is a personal worklist keyed to the
caller's own identity, not the branch-scoped admin listing the existing
"Employee Lists Invitations at Their Authorized Branches" requirement
describes. `relevantToMe` SHALL compose with the existing `status`,
`registrationType`, and `source` filters and with pagination/sorting,
narrowing the relevant-to-me set the same way those filters narrow the
branch-scoped list. A caller with no invitations where they are host or
delegate SHALL receive an empty, successfully-paginated result, not an
error.

#### Scenario: Host sees their own invitation without invitations:view
- **WHEN** the user identified as the host of an invitation (its
  `stepOrder` 0 step's `approverUserId`) requests `GET /invitations` with
  `relevantToMe=true`, and holds no `invitations:view` grant at that
  invitation's branch
- **THEN** the response includes that invitation

#### Scenario: Delegate sees the invitation they were delegated
- **WHEN** a user who has been delegated one of an invitation's approval
  steps requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response includes that invitation, whether or not the user
  holds `invitations:view` at its branch and regardless of that step's
  current status

#### Scenario: Caller who is neither host nor delegate sees nothing for that invitation
- **WHEN** a caller who is not the snapshotted host and has not been
  delegated any step of a given invitation requests `GET /invitations` with
  `relevantToMe=true`
- **THEN** that invitation is absent from the response, even if the caller
  holds `invitations:view` at its branch

#### Scenario: relevantToMe composes with status filtering
- **WHEN** a host requests `GET /invitations` with `relevantToMe=true` and
  `status=submitted`
- **THEN** the response includes only their relevant invitations that are
  currently `submitted`

#### Scenario: No relevant invitations returns an empty page, not an error
- **WHEN** a caller who is neither host nor delegate on any invitation
  requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response is a successful, empty, correctly-paginated result

#### Scenario: X-Branch-ID is ignored when relevantToMe is set
- **WHEN** a caller requests `GET /invitations` with both `relevantToMe=true`
  and an `X-Branch-ID` header
- **THEN** the response includes the caller's relevant invitations across
  every branch, not narrowed to the named branch
