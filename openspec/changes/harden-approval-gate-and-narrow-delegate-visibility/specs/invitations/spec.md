## MODIFIED Requirements

### Requirement: Caller Lists Invitations Relevant to Themselves via relevantToMe
`GET /invitations` SHALL accept a `relevantToMe` boolean query parameter.
WHEN `relevantToMe` is true, the system SHALL return invitations where the
authenticated caller is any of:
(a) the invitation's resolved host (its `hostId`, once any of its approval
steps has been delegated to them — see "Invitation Output Surfaces the
Resolved Host as hostId") — regardless of that step's or the invitation's
current status;
(b) the delegate assigned to any of that invitation's approval steps (see
the `approvals` capability's "Current Step's Authorized Approver Delegates
It to a Specific Person") — regardless of that step's or the invitation's
current status;
(c) currently holds, via branch-scoped role assignment at the invitation's
branch or company-wide, the role that the invitation's current pending
`InvitationApprovalStep` names (that step being role-identified), AND that
step has no delegate assigned — i.e., the caller is one of the role-holders
who could act on the currently-pending step right now, per the `approvals`
capability's role-match authorization rule. Unlike the prior version of
this clause, visibility under (c) SHALL stop the moment that step is
delegated to a specific person: once a role-identified step (at any
`stepOrder`) has a delegate assigned, a caller who only ever qualified
under (c) for that step — and who is not the delegate, the resolved host,
or someone who personally acted on a step — no longer sees the invitation
via `relevantToMe`. The one carve-out is clause (e) below, which keeps
every holder of the tenant's default host role visible regardless of
delegation;
(d) has personally acted on (approved or rejected, i.e. is the
`actedByUserId` of) any of the invitation's approval steps, regardless of
that step's or the invitation's current status. Unlike (c), clause (d)
never drops off: once a caller has approved or rejected a step, that
invitation stays in their `relevantToMe` list for its entire lifecycle —
e.g. an individual Reception user, having approved the invitation's
`stepOrder` 0 ownership step personally, keeps seeing it through every
later, differently-role-identified step and after final approval/denial,
not just while their own step was current. Clause (d) is keyed to the
specific person who acted, not to a role: another holder of that role who
never personally acted on that invitation does not gain visibility from
(d) — only (c) (while undelegated) or (e) (for the default host role)
covers them; or
(e) currently holds, via branch-scoped role assignment at the invitation's
branch or company-wide, the tenant's default host role (e.g. `reception`)
— regardless of the invitation's current step, that step's delegation
state, or the invitation's overall status. Unlike (c), clause (e) never
drops off and is never narrowed by delegation: the default host role owns
front-office intake for every invitation for its entire lifecycle, so every
one of its holders keeps permanent visibility, the same permanence clause
(d) gives an individual actor, but granted to the whole role rather than
to whoever happened to act.
This filter SHALL NOT require the caller to hold `invitations:view`,
and SHALL NOT be scoped by `X-Branch-ID` or the caller's authorized branches:
it is a personal worklist keyed to the caller's own identity and current
approval authority, not the branch-scoped admin listing the "Employee Lists
Invitations at Their Authorized Branches" requirement above describes.
`relevantToMe` SHALL compose with the existing `status`, `registrationType`,
and `source` filters and with pagination/sorting. A caller matching none of
(a)/(b)/(c)/(d)/(e) for any invitation SHALL receive an empty,
successfully-paginated result, not an error.

#### Scenario: Host sees their own invitation without invitations:view
- **WHEN** the user an invitation's ownership step was delegated to (its
  resolved `hostId`) requests `GET /invitations` with `relevantToMe=true`,
  and holds no `invitations:view` grant at that invitation's branch
- **THEN** the response includes that invitation

#### Scenario: Every front-office holder sees a freshly submitted invitation before anyone delegates it
- **WHEN** a user who holds the tenant's default host role at an invitation's
  branch, and to whom that invitation's `stepOrder` 0 step has not yet been
  delegated, requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response includes that invitation, via clauses (c) and (e)

#### Scenario: A role-holder keeps seeing the invitation once someone else's delegation is assigned
- **WHEN** an invitation's `stepOrder` 0 step is delegated to a specific
  host, the invitation is later fully approved, and a user who holds the
  tenant's default host role at that invitation's branch — but who never
  personally acted on any step, was never delegated any step, and is not
  the resolved host — requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response includes that invitation, via clause (e), which
  neither depends on delegation state nor drops off once the invitation
  leaves `submitted` — unlike a holder of a non-default role, who loses
  visibility the moment their role's step is delegated (see "A
  non-default-role holder loses visibility once the step is delegated to
  someone else")

#### Scenario: Delegate sees the invitation they were delegated
- **WHEN** a user who has been delegated one of an invitation's approval
  steps requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response includes that invitation, whether or not the user
  holds `invitations:view` at its branch and regardless of that step's
  current status

#### Scenario: A role-holder sees an invitation whose current step needs their role
- **WHEN** a user who holds, via `UserBranchRole` at an invitation's branch,
  the `approverRoleId` role of that invitation's current pending
  role-identified step (and that step has no delegate assigned) requests
  `GET /invitations` with `relevantToMe=true`
- **THEN** the response includes that invitation, even though the user is
  neither the invitation's host nor a delegate — this closes the gap where
  such a user could only find the invitation via the branch-wide list

#### Scenario: A non-default-role holder loses visibility once the step is delegated to someone else
- **WHEN** an invitation's current pending step, role-identified for a role
  that is not the tenant's default host role, is delegated to a different,
  specific user, and the caller — who holds that same role, but is not the
  delegate, the resolved host, or someone who has personally acted on any
  step — requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response does NOT include that invitation: clause (c) no
  longer applies once the step has a delegate, and no other clause matches
  this caller

#### Scenario: A role-holder loses visibility once the step is actually approved or rejected, unless they were the one who acted
- **WHEN** an invitation's current pending step, role-identified for a role
  the caller holds, is approved or rejected by a different holder of that
  role (or its delegate, or an override-permission holder)
- **THEN** the caller — who only ever qualified under clause (c) for that
  step, never as its host, its delegate, the one who acted, or a default
  host role holder — no longer sees the invitation via `relevantToMe=true`,
  since that step is no longer the current pending step and clauses (d) and
  (e) do not apply to them

#### Scenario: The caller who personally approved a step keeps seeing the invitation forever, via clause (d)
- **WHEN** a caller personally approves an invitation's current pending,
  role-identified step, and a later step (role-identified for a different
  role the caller does not hold) subsequently becomes current, is itself
  approved, and the invitation is fully approved
- **THEN** the caller continues to see the invitation via
  `relevantToMe=true` throughout — while the later step is current, after
  it is approved, and once the invitation itself is `approved` — because
  clause (d) does not depend on any step being current, delegated, or on
  the invitation's own status

#### Scenario: Approving your own step also grants delegation authority over the very next step
- **WHEN** the caller from the previous scenario, instead of waiting, calls
  `POST /invitations/{id}/approval-steps/{stepId}/delegate` on the
  next step (now current, role-identified for a role the caller does not
  hold), naming a person who holds that step's role at the invitation's
  branch
- **THEN** the delegation succeeds (see the `approvals` capability's
  "Current Step's Authorized Approver Delegates It to a Specific Person",
  clause (d)) — the same clause (d) actor privilege that keeps the
  invitation visible to the caller also lets them route its next step
  onward

#### Scenario: A role-holder who is not currently authorized on the pending step sees nothing for it
- **WHEN** a user holds a role that does not match the invitation's current
  pending step's `approverRoleId` (e.g. the pending step is for a different
  role, or the invitation is not currently `submitted`), and does not hold
  the tenant's default host role
- **THEN** that invitation is absent from the user's `relevantToMe=true`
  response, unless they separately qualify as its host or a delegate

#### Scenario: Caller who is neither host, delegate, nor actor sees nothing for that invitation
- **WHEN** a caller who is not the resolved host, has not been delegated
  any step, has not personally acted on any step, does not hold the
  tenant's default host role, and does not hold the role of any
  invitation's current pending undelegated step requests
  `GET /invitations` with `relevantToMe=true`
- **THEN** that invitation is absent from the response, even if the caller
  holds `invitations:view` at its branch

#### Scenario: relevantToMe composes with status filtering
- **WHEN** a host requests `GET /invitations` with `relevantToMe=true` and
  `status=submitted`
- **THEN** the response includes only their relevant invitations that are
  currently `submitted`

#### Scenario: No relevant invitations returns an empty page, not an error
- **WHEN** a caller who does not match (a), (b), (c), (d), or (e) for any
  invitation requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response is a successful, empty, correctly-paginated result

#### Scenario: X-Branch-ID is ignored when relevantToMe is set
- **WHEN** a caller requests `GET /invitations` with both `relevantToMe=true`
  and an `X-Branch-ID` header
- **THEN** the response includes the caller's relevant invitations across
  every branch, not narrowed to the named branch
