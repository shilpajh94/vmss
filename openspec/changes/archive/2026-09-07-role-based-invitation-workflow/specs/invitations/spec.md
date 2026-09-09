## MODIFIED Requirements

### Requirement: Visit Details Optionally Accept Catalog IDs Alongside Free Text
`VisitDetailsSubmit` (used by both `POST /invitations` and `POST
/registrations/walk-in`) SHALL accept optional `purposeId`, `durationId`, and
`departmentId` fields alongside its existing `purposeOfVisit`,
`expectedDuration`, `departmentToVisit` free-text fields. When any id is
supplied, the system SHALL validate it against the corresponding
catalog/`Department` record, scoped to the resolved tenant, and SHALL
overwrite the paired free-text field with that record's canonical display
value before persisting, regardless of what free-text value the request also
supplied for that field. When an id is omitted, its paired free-text field is
accepted and stored exactly as submitted, unchanged from today's behavior.
`VisitDetailsSubmit` SHALL NOT accept `hostId` or `hostNameOrEmail` from
either channel — the host is never client-supplied at creation (see "Every
New Invitation Is Owned by the Tenant's Default Host Role at Creation"); a
request that includes either field SHALL have it ignored rather than
rejected, so an un-updated client does not start failing outright.

#### Scenario: Submission with no ids behaves exactly as before
- **WHEN** a caller submits `purposeOfVisit`, `expectedDuration`,
  `departmentToVisit` with no `purposeId`/`durationId`/`departmentId`
- **THEN** the invitation is created with exactly the submitted free-text
  values, identical to today's behavior

#### Scenario: Submission with an id overwrites free text with the catalog value
- **WHEN** a caller submits `departmentId` referencing an active department,
  along with a `departmentToVisit` string that does not match that
  department's name
- **THEN** the invitation is created with `departmentToVisit` set to the
  referenced department's actual name, not the client-supplied string

#### Scenario: Unknown or cross-tenant id is rejected
- **WHEN** a caller submits an id (`purposeId`, `durationId`, or
  `departmentId`) that does not resolve to an existing, active row in the
  resolved tenant's schema
- **THEN** the request is rejected with a validation error and no invitation
  is created

#### Scenario: Walk-in registration inherits the same optional fields
- **WHEN** a caller submits `POST /registrations/walk-in` with any of
  `purposeId`/`durationId`/`departmentId`
- **THEN** the same validation and free-text overwrite behavior applies,
  since it submits the identical `VisitDetailsSubmit` shape

#### Scenario: A supplied hostId or hostNameOrEmail is silently ignored
- **WHEN** a caller submits `POST /invitations` or `POST
  /registrations/walk-in` with `hostId` and/or `hostNameOrEmail` set (e.g. an
  un-updated client)
- **THEN** the invitation is created successfully, with those values ignored
  entirely — the invitation's host is never set from them, and no validation
  error is raised for supplying them

### Requirement: Invitation Output Surfaces the Resolved Host as hostId
`InvitationOut` and `InvitationDetailOut` SHALL include `hostId`, set to the
invitation's resolved host user id once one has been assigned, and null
before that. A host is assigned exclusively by delegating the invitation's
ownership step (`stepOrder` 0) to a specific person — see the `approvals`
capability's "Current Step's Authorized Approver Delegates It to a Specific
Person" and "Delegating the Ownership Step Also Resolves the Invitation's
Host" — never by anything supplied at creation. `hostNameOrEmail` continues
to be surfaced alongside `hostId`, set to that same delegate's display name
once resolved, and null before that (this capability no longer accepts a
client-supplied `hostNameOrEmail` at creation to fall back to — see "Visit
Details Optionally Accept Catalog IDs Alongside Free Text").

#### Scenario: Resolved host is surfaced as hostId
- **WHEN** an invitation whose ownership step has been delegated to a
  specific person is fetched via `GET /invitations` (list) or `GET
  /invitations/{id}` (detail)
- **THEN** the response includes `hostId` set to that person's id, alongside
  `hostNameOrEmail` set to their display name

#### Scenario: Unresolved host leaves hostId null
- **WHEN** an invitation whose ownership step has not yet been delegated to
  a specific person is fetched (still pending for the owning role, or
  already acted on directly by a role-holder without delegating)
- **THEN** the response includes `hostId` and `hostNameOrEmail` as null

### Requirement: Caller Lists Invitations Relevant to Themselves via relevantToMe
`GET /invitations` SHALL accept a `relevantToMe` boolean query parameter.
WHEN `relevantToMe` is true, the system SHALL return invitations where the
authenticated caller is any of:
(a) the invitation's resolved host (its `hostId`, once the ownership step has
been delegated to them — see "Invitation Output Surfaces the Resolved Host as
hostId") — regardless of that step's or the invitation's current status;
(b) the delegate assigned to any of that invitation's approval steps (see
the `approvals` capability's "Current Step's Authorized Approver Delegates
It to a Specific Person") — regardless of that step's or the invitation's
current status; or
(c) currently authorized, via branch-scoped role assignment at the
invitation's branch or company-wide, to act on the invitation's current
pending `InvitationApprovalStep` because that step is role-identified and
names a role the caller holds, and no delegate has yet been assigned to
that step — i.e., the caller is one of the role-holders who could act on
the currently-pending step right now, per the `approvals` capability's
role-match authorization rule.
Clause (c) only ever matches while the invitation is `submitted` with an
un-delegated, role-identified step currently pending; once that step is
delegated, acted on, or the invitation leaves `submitted`, a caller who
only ever qualified under (c) (never under (a) or (b)) no longer sees that
invitation via `relevantToMe`. Since every newly submitted invitation's
`stepOrder` 0 step is role-identified for the tenant's default host role
(rather than sometimes host-identified as before), clause (c) is what makes
that invitation visible to every front-office holder before anyone
delegates it — clause (a) does not apply until a delegation actually
happens. This filter SHALL NOT require the caller to hold `invitations:view`,
and SHALL NOT be scoped by `X-Branch-ID` or the caller's authorized branches:
it is a personal worklist keyed to the caller's own identity and current
approval authority, not the branch-scoped admin listing the "Employee Lists
Invitations at Their Authorized Branches" requirement above describes.
`relevantToMe` SHALL compose with the existing `status`, `registrationType`,
and `source` filters and with pagination/sorting. A caller matching none of
(a)/(b)/(c) for any invitation SHALL receive an empty, successfully-paginated
result, not an error.

#### Scenario: Host sees their own invitation without invitations:view
- **WHEN** the user an invitation's ownership step was delegated to (its
  resolved `hostId`) requests `GET /invitations` with `relevantToMe=true`,
  and holds no `invitations:view` grant at that invitation's branch
- **THEN** the response includes that invitation

#### Scenario: Every front-office holder sees a freshly submitted invitation before anyone delegates it
- **WHEN** a user who holds the tenant's default host role at an invitation's
  branch, and to whom that invitation's `stepOrder` 0 step has not yet been
  delegated, requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response includes that invitation, via clause (c)

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

#### Scenario: A role-holder no longer sees the invitation once someone else's delegation is assigned
- **WHEN** an invitation's current pending step (role-identified, matching a
  role the caller holds) is delegated to a different, specific user
- **THEN** the caller — who is not that delegate — no longer sees the
  invitation via `relevantToMe=true`, since clause (c) requires no delegate
  be assigned

#### Scenario: A role-holder who is not currently authorized on the pending step sees nothing for it
- **WHEN** a user holds a role that does not match the invitation's current
  pending step's `approverRoleId` (e.g. the pending step is for a different
  role, or the invitation is not currently `submitted`)
- **THEN** that invitation is absent from the user's `relevantToMe=true`
  response, unless they separately qualify as its host or a delegate

#### Scenario: Caller who is neither host nor delegate sees nothing for that invitation
- **WHEN** a caller who is not the resolved host, has not been delegated
  any step, and does not hold the role of any invitation's current pending
  step requests `GET /invitations` with `relevantToMe=true`
- **THEN** that invitation is absent from the response, even if the caller
  holds `invitations:view` at its branch

#### Scenario: relevantToMe composes with status filtering
- **WHEN** a host requests `GET /invitations` with `relevantToMe=true` and
  `status=submitted`
- **THEN** the response includes only their relevant invitations that are
  currently `submitted`

#### Scenario: No relevant invitations returns an empty page, not an error
- **WHEN** a caller who does not match (a), (b), or (c) for any invitation
  requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response is a successful, empty, correctly-paginated result

#### Scenario: X-Branch-ID is ignored when relevantToMe is set
- **WHEN** a caller requests `GET /invitations` with both `relevantToMe=true`
  and an `X-Branch-ID` header
- **THEN** the response includes the caller's relevant invitations across
  every branch, not narrowed to the named branch

## REMOVED Requirements

### Requirement: Invitation Creation Notifies the Resolved Host via Email
**Reason**: An invitation's host is never resolved at creation anymore — it
is only ever resolved by delegating the ownership step to a specific person,
after submission (see "Every New Invitation Is Owned by the Tenant's Default
Host Role at Creation" and the `approvals` capability's "Delegating the
Ownership Step Also Resolves the Invitation's Host"). The creation-time
condition this requirement depended on ("resolves to a host") can no longer
occur, so the requirement is void rather than modified.
**Migration**: Callers relying on a creation-time host email should instead
rely on: (1) "Invitation Submission Notifies the Owning Role via Email"
(new, in this same change) for the immediate fan-out to the tenant's default
host role, and (2) the `approvals` capability's "Delegating the Ownership
Step Also Resolves the Invitation's Host" for the email the actual host
receives once known.

### Requirement: Invitation Submission Notifies the Approval Workflow's First Approver(s) via Push
**Reason**: `stepOrder` 0 is no longer ever host-identified at submission
time (a host can never resolve at creation anymore), so the old
requirement's host-identified-vs-role-identified branching at step 0 can no
longer occur — its "Submission with a host-identified first step" scenario
describes a case that is now impossible.
**Migration**: See "Submission Notifies the Owning Role via Push" below,
which replaces this requirement in full — step 0 is now always
role-identified for the tenant's default host role, so the push behavior
simplifies to the existing role-fan-out branch only.

## ADDED Requirements

### Requirement: Every New Invitation Is Owned by the Tenant's Default Host Role at Creation
Every invitation submitted for approval (not auto-approved) SHALL have its
`stepOrder` 0 approval step created as role-identified for the tenant's
default host role (the standard `reception` role, unless a tenant has
reconfigured which role serves this purpose), unconditionally — regardless
of whether the invitation's category has any configured
`ApprovalWorkflowRule` rows. This replaces the prior behavior where
`stepOrder` 0 was host-identified when a client-supplied host resolved to a
user, and absent entirely when it did not. The category's own configured
rule chain (if any) keeps its rules' `stepOrder` values unchanged (by
convention starting at 1), unaffected by this default ownership step. This
requirement is defined in full in the `approvals` capability's "Submission
Snapshots the Category's Workflow Plus an Unconditional Ownership Step"; this entry
exists so the `invitations` capability's own requirements (push/email
fan-out, `relevantToMe`) can reference it without a forward dependency on
`approvals`.

#### Scenario: A newly submitted invitation always has a stepOrder 0 role step
- **WHEN** any invitation is submitted (not auto-approved), for a category
  with any number (including zero) of active `ApprovalWorkflowRule` rows
- **THEN** it has a `stepOrder` 0 `InvitationApprovalStep`, role-identified
  for the tenant's default host role, `pending`, ahead of any of the
  category's own configured steps

### Requirement: Submission Notifies the Owning Role via Push
WHEN `create_invitation` leaves an invitation `submitted` (not auto-approved),
the system SHALL dispatch a push notification to the newly-created
`stepOrder` 0 step's approver(s): every user holding that step's role (the
tenant's default host role) at the invitation's branch — except when that
role is the tenant's standard `admin` role (matched by name,
case-insensitively), which SHALL NOT receive a push notification. Every
submitted invitation has a `stepOrder` 0 step (see "Every New Invitation Is
Owned by the Tenant's Default Host Role at Creation"), so this dispatch is
unconditional for any non-auto-approved invitation.

#### Scenario: Submission notifies every holder of the owning role
- **WHEN** an invitation is submitted
- **THEN** every user holding the tenant's default host role at the
  invitation's branch receives a push notification that a new invitation
  awaits their triage

#### Scenario: Submission with an Admin-role owning role sends no push
- **WHEN** an invitation is submitted and a tenant has reconfigured its
  default host role to the tenant's standard `admin` role
- **THEN** no push notification is dispatched to anyone for the `stepOrder`
  0 step

### Requirement: Invitation Submission Notifies the Owning Role via Email
WHEN an invitation is submitted (not auto-approved), the system SHALL
dispatch an informational email to every active user holding the tenant's
default host role at the invitation's branch, stating that a new invitation
awaits triage — the tracking ID, visitor's name, and purpose of visit — in
addition to the existing push notification to the same recipients (see
"Invitation Submission Notifies the Approval Workflow's First Approver(s)
via Push"). This is a new, additive email channel: it does not replace or
delay the visitor's own existing submission/auto-approval notification, and
a recipient with no reachable email address is simply skipped for this
dispatch without failing the triggering request.

#### Scenario: Submission emails every holder of the owning role
- **WHEN** an invitation is submitted, and the tenant's default host role has
  two active users at the invitation's branch
- **THEN** both users receive an email stating a new invitation awaits
  triage, dispatched asynchronously without delaying the creation response

#### Scenario: A role-holder with no email is skipped without failing the dispatch
- **WHEN** one of the role's holders at the branch has no usable email
  address
- **THEN** that user is skipped for this email, the remaining holders still
  receive it, and the triggering request is unaffected

#### Scenario: Auto-approved creation sends no owning-role email
- **WHEN** an invitation is created and auto-approved per the Company's
  auto-approve setting (no approval steps are snapshotted at all)
- **THEN** no owning-role email is dispatched, consistent with "Auto-Approved
  Invitations Do Not Trigger a Submission Push"

### Requirement: Authorized Caller Edits Non-Personal Invitation Details
An authenticated, branch-scoped caller holding a new `invitations:edit`
permission at the invitation's branch SHALL be able to change, via `PATCH
/invitations/{id}/edit`, any of: `purposeOfVisit` (and `purposeId`),
`preferredVisitDate`, `preferredVisitTime`, `expectedDuration` (and
`durationId`), `departmentToVisit` (and `departmentId`), location/building,
and `additionalNotes` — on an invitation currently `submitted` or `approved`.
This endpoint SHALL NOT accept or change: the primary contact's or any
visitor's personal fields (name, email, phone, ID proof, photo),
`visitorCategoryId` (locked after creation — changing it would require
re-deriving the approval workflow, which this change does not support), or
the host (`hostId`/`hostNameOrEmail`) — host reassignment stays exclusively
the job of the `approvals` capability's delegation mechanism, so there is
exactly one way to change who the host is, not two. A request naming an
invitation that is not currently `submitted` or `approved` SHALL be rejected
with 409, following the same atomic-conditional-UPDATE pattern as the
existing `reschedule`/`extend` endpoints, and SHALL NOT change any field. An
unknown invitation id SHALL be rejected with 404; a caller without branch
access to an existing invitation SHALL be rejected with 403. A successful
edit SHALL dispatch a notification to the primary contact (and, if a host is
currently resolved, to the host) stating which visit details changed — the
same channel-routing rule (`preferredContactMethod`) the existing reschedule
notification already follows.

#### Scenario: Authorized edit changes multiple visit-detail fields at once
- **WHEN** a caller with `invitations:edit` at the invitation's branch edits
  a `submitted` invitation's `preferredVisitDate`, `expectedDuration`, and
  `additionalNotes` in one request
- **THEN** all three fields are updated, the invitation's other fields are
  unchanged, and the primary contact receives a notification describing the
  change

#### Scenario: Visitor personal fields and visitor category are rejected
- **WHEN** a request to `PATCH /invitations/{id}/edit` includes any of the
  primary contact's or a visitor's name/email/phone/ID-proof/photo fields, or
  `visitorCategoryId`
- **THEN** the request is rejected with a validation error and no field is
  changed

#### Scenario: Host fields are rejected
- **WHEN** a request to `PATCH /invitations/{id}/edit` includes `hostId` or
  `hostNameOrEmail`
- **THEN** the request is rejected with a validation error and no field is
  changed — host reassignment must go through the delegation endpoint
  instead

#### Scenario: Edit rejected for an ineligible status
- **WHEN** a caller attempts to edit an invitation that is `denied`,
  `checked_in`, or `checked_out`
- **THEN** the request is rejected with 409 and no field is changed

#### Scenario: Caller lacks invitations:edit
- **WHEN** a caller without `invitations:edit` at the invitation's branch
  attempts this endpoint
- **THEN** the request is rejected with 403 and no field is changed

#### Scenario: Unknown invitation id is rejected with 404
- **WHEN** a caller names an invitation id that does not exist
- **THEN** the request is rejected with 404

#### Scenario: Edit while a host is resolved also notifies the host
- **WHEN** an authorized edit succeeds on an invitation whose ownership step
  has already been delegated to a specific host
- **THEN** both the primary contact and the resolved host receive a
  notification describing the change

### Requirement: Approval Notification Email Includes Full Visit and Host Detail
The email dispatched when an invitation is approved (directly, as the final
step of a workflow, or via a resolved-host approval step) SHALL be rendered
from the new branded HTML template (see the `email-notifications`
capability) and SHALL include: the tracking ID, visit date/time, expected
duration, location/building/department to visit, purpose of visit, and — the
gap this change closes — the resolved host's name and at least one
point-of-contact channel (the host's phone or email, whichever is on file)
when a host has been resolved by that point. WHEN no host has been resolved
by the time of approval (the owning role approved directly without
delegating), the email SHALL instead surface the branch's general front-desk
contact channel in the host/point-of-contact section, rather than omitting
that section or naming no one.

#### Scenario: Approval email with a resolved host includes their contact details
- **WHEN** an invitation whose ownership step was delegated to a specific
  host is approved
- **THEN** the visitor's approval email includes that host's name and at
  least one reachable contact channel, alongside the full visit detail

#### Scenario: Approval email with no resolved host falls back to the front-desk contact
- **WHEN** an invitation is approved directly by a holder of the tenant's
  default host role, without ever being delegated to a specific person
- **THEN** the visitor's approval email includes the branch's general
  front-desk contact channel in place of a named host, alongside the full
  visit detail
