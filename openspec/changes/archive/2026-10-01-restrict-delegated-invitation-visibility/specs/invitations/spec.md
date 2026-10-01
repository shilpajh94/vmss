## MODIFIED Requirements

### Requirement: Employee Lists Invitations at Their Authorized Branches
The system SHALL let an authenticated caller holding `invitations:view-all`
list invitations, paginated, sorted, and filterable by `status`,
`registrationType`, and `source`. A request supplying `X-Branch-ID` SHALL be
narrowed to that one branch, rejected with 404/403 the same way other
branch-scoped endpoints reject an unknown or unauthorized branch id. A
request omitting `X-Branch-ID` SHALL return invitations across every branch
the caller holds `invitations:view-all` at, rejected with 403 only if that
set is empty. Holding `invitations:view` alone (without
`invitations:view-all`) SHALL NOT grant access to this branch-wide listing:
such a caller (e.g. a `host`) finds their own work only through
`relevantToMe=true` ("Caller Lists Invitations Relevant to Themselves via
relevantToMe"). Each row in the response SHALL include enough detail to
identify and triage the invitation (tracking ID, registration type, source,
status, `visitorCategoryId`, primary contact name, primary contact photo
URL, purpose of visit, expiry/submission timestamps) without the per-row
visitor/vehicle detail the single-invitation tracking lookup returns.

#### Scenario: Caller with company-wide access lists across all their branches
- **WHEN** a caller with `invitations:view-all` granted company-wide requests
  `GET /invitations` without an `X-Branch-ID` header
- **THEN** the response includes invitations from every branch, paginated
  per the requested page/pageSize

#### Scenario: X-Branch-ID narrows the result to one branch
- **WHEN** a caller with `invitations:view-all` at a specific branch requests
  `GET /invitations` with that branch's `X-Branch-ID`
- **THEN** the response includes only that branch's invitations

#### Scenario: Unauthorized branch id rejected
- **WHEN** a caller requests `GET /invitations` with an `X-Branch-ID` for a
  branch they do not hold `invitations:view-all` at
- **THEN** the system returns 403 and no invitation data

#### Scenario: Caller lacks permission everywhere
- **WHEN** a caller with no `invitations:view-all` grant at any branch
  requests `GET /invitations` without an `X-Branch-ID` header
- **THEN** the system returns 403

#### Scenario: A host holding only invitations:view cannot use the branch-wide listing
- **WHEN** a caller holding the `host` role (which grants `invitations:view`
  but not `invitations:view-all`) at a branch requests `GET /invitations`
  without `relevantToMe`, with or without that branch's `X-Branch-ID`
- **THEN** the system returns 403 and no invitation data, even though
  invitations exist at that branch

#### Scenario: Reception, Security, and Admin keep the branch-wide listing
- **WHEN** a caller holding the `reception`, `security`, or `admin` role at
  a branch requests `GET /invitations` without `relevantToMe`
- **THEN** the response includes every invitation at that branch, since
  each of those roles grants `invitations:view-all`

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
  status, `visitorCategoryId`, primary contact name, primary contact photo
  URL, purpose of visit, and expiry/submission timestamps, and does not
  include the per-visitor or per-vehicle detail that `GET /invitations/track`
  returns for a single invitation

#### Scenario: List row surfaces the primary contact's photo URL when one was captured
- **WHEN** a caller lists invitations via `GET /invitations` and an
  invitation's primary contact has a stored photo
- **THEN** that row includes a resolvable URL for the photo, matching the
  URL the tracking/detail endpoints return for the same invitation

#### Scenario: List row omits the photo field when no photo was captured
- **WHEN** a caller lists invitations via `GET /invitations` and an
  invitation's primary contact has no stored photo
- **THEN** that row's photo URL field is null, and the row is otherwise
  unaffected

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
step has no delegate assigned, AND that role is not a delegation-only role
— i.e., the caller is one of the role-holders who could act on the
currently-pending step right now purely by holding its role, per the
`approvals` capability's role-match authorization rule. A delegation-only
role (today: `host`) is one whose steps no role-holder may act on or be
notified about until the step is delegated to one specific person; clause
(c) SHALL NOT match a step identified by such a role, whether or not it is
delegated, so an unassigned `host` step is never broadcast to every
holder of the `host` role. Visibility under (c) SHALL also stop the moment
a (non-delegation-only) step is delegated to a specific person: once a
role-identified step (at any `stepOrder`) has a delegate assigned, a
caller who only ever qualified under (c) for that step — and who is not
the delegate, the resolved host, or someone who personally acted on a step
— no longer sees the invitation via `relevantToMe`. The one carve-out is
clause (e) below, which keeps every holder of the tenant's default host
role visible regardless of delegation;
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
(d) — only (c) (while undelegated, for a non-delegation-only role) or (e)
(for the default host role) covers them; or
(e) currently holds, via branch-scoped role assignment at the invitation's
branch or company-wide, the tenant's default host role (e.g. `reception`)
— regardless of the invitation's current step, that step's delegation
state, or the invitation's overall status. Unlike (c), clause (e) never
drops off and is never narrowed by delegation: the default host role owns
front-office intake for every invitation for its entire lifecycle, so every
one of its holders keeps permanent visibility, the same permanence clause
(d) gives an individual actor, but granted to the whole role rather than
to whoever happened to act.
This filter SHALL NOT require the caller to hold `invitations:view` or
`invitations:view-all`, and SHALL NOT be scoped by `X-Branch-ID` or the
caller's authorized branches: it is a personal worklist keyed to the
caller's own identity and current approval authority, not the
branch-scoped listing the "Employee Lists Invitations at Their Authorized
Branches" requirement above describes. The same (a)–(e) rule SHALL also
decide which invitations a caller without `invitations:view-all` may open
via `GET /invitations/{id}` ("Invitation Detail Is Visible Only to
Branch-Wide Viewers and Participants").
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
  role-identified step — that role not being delegation-only (e.g. a
  `security` step), and that step having no delegate assigned — requests
  `GET /invitations` with `relevantToMe=true`
- **THEN** the response includes that invitation, even though the user is
  neither the invitation's host nor a delegate — this closes the gap where
  such a user could only find the invitation via the branch-wide list

#### Scenario: An unassigned host-role step is not broadcast to every host
- **WHEN** an invitation's `stepOrder` 0 step (default host role) is
  delegated to host X, X approves it, and the invitation's `stepOrder` 1
  step — role-identified for the `host` role, with no delegate assigned —
  becomes the current pending step, and a different user Y who holds the
  `host` role at that invitation's branch (but is not the resolved host,
  was never delegated a step, never acted on a step, and does not hold the
  default host role) requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response does NOT include that invitation: clause (c) never
  matches a delegation-only role's step, and no other clause matches Y

#### Scenario: The delegate and Reception still see an unassigned host-role step
- **WHEN** the invitation from the previous scenario is in the same state
  (its `host`-role `stepOrder` 1 step current and undelegated), and either
  X (the resolved host who approved `stepOrder` 0) or a holder of the
  default host role requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response includes that invitation — for X via clauses (a)
  and (d), for the default host role holder via clause (e)

#### Scenario: Approve-and-delegate never exposes the next host step to other hosts
- **WHEN** a Reception user approves an invitation's `stepOrder` 0 step
  without delegating it, the `host`-role `stepOrder` 1 step becomes current
  and undelegated, and — before or after that Reception user delegates
  `stepOrder` 1 to host X — a different `host`-role holder Y requests
  `GET /invitations` with `relevantToMe=true`
- **THEN** the response does NOT include that invitation for Y at either
  point, while it does include it for X once X is delegated (clause (b))

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
  tenant's default host role, and does not hold the (non-delegation-only)
  role of any invitation's current pending undelegated step requests
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

## ADDED Requirements

### Requirement: Invitation Detail Is Visible Only to Branch-Wide Viewers and Participants
`GET /invitations/{id}` SHALL return the invitation's full detail only when
the authenticated caller either (1) holds `invitations:view-all` at the
invitation's branch (or company-wide), or (2) is a participant in that
invitation — i.e. matches any of clauses (a)–(e) of "Caller Lists
Invitations Relevant to Themselves via relevantToMe" for it, evaluated
against the invitation's current state. A participant SHALL be served the
detail whether or not they hold `invitations:view` at its branch. A caller
who is neither SHALL receive 404 (the same response as for a nonexistent
invitation id, so the invitation's existence is not disclosed) if they hold
`invitations:view` at the invitation's branch, and 403 if they hold no
invitation-viewing grant there at all. Which detail fields are included
(e.g. documents gated on `documents:view`) SHALL be unchanged by this
requirement.

#### Scenario: Reception opens any invitation at their branch
- **WHEN** a caller holding the `reception` role at an invitation's branch
  requests `GET /invitations/{id}` for it, at any stage and whether or not
  any step is delegated
- **THEN** the system returns 200 with the invitation's detail

#### Scenario: The assigned user opens the invitation delegated to them
- **WHEN** a host to whom one of an invitation's approval steps has been
  delegated requests `GET /invitations/{id}` for it
- **THEN** the system returns 200 with the invitation's detail

#### Scenario: A delegate without invitations:view still opens their invitation
- **WHEN** a user holding no `invitations:view` or `invitations:view-all`
  grant at an invitation's branch, but to whom one of its steps has been
  delegated, requests `GET /invitations/{id}` for it
- **THEN** the system returns 200 with the invitation's detail

#### Scenario: An uninvolved host cannot open a delegated invitation
- **WHEN** an invitation's step is delegated to host X, and a different
  user Y holding the `host` role at the same branch — not the resolved
  host, never delegated a step, never acted on a step, not a default host
  role holder — requests `GET /invitations/{id}` for it
- **THEN** the system returns 404 and no invitation data

#### Scenario: An uninvolved host cannot open an unassigned host-role step's invitation
- **WHEN** an invitation's current pending step is role-identified for the
  `host` role with no delegate assigned, and a `host`-role holder at that
  branch who does not otherwise participate requests
  `GET /invitations/{id}` for it
- **THEN** the system returns 404 and no invitation data

#### Scenario: Security and Admin keep branch-wide detail access
- **WHEN** a caller holding the `security` or `admin` role at an
  invitation's branch requests `GET /invitations/{id}` for an invitation
  they do not otherwise participate in
- **THEN** the system returns 200 with the invitation's detail

#### Scenario: A caller with no viewing grant is still rejected with 403
- **WHEN** a caller who holds neither `invitations:view` nor
  `invitations:view-all` at an invitation's branch, and does not
  participate in it, requests `GET /invitations/{id}` for it
- **THEN** the system returns 403

#### Scenario: Detail from another tenant is never reachable
- **WHEN** a caller authenticated for tenant A requests
  `GET /invitations/{id}` with the id of an invitation that exists only in
  tenant B's schema
- **THEN** the system returns 404
