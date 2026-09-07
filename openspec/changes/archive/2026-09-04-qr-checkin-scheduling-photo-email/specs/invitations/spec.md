## MODIFIED Requirements

### Requirement: QR Check-In Endpoint Transitions an Eligible Visitor to Checked-In
An invitation's check-in lifecycle SHALL be tracked by a `checkInStatus`
value of `unused`, `checked_in`, or `checked_out`, defaulting to `unused`.
`PATCH /api/v2/invitations/qr/{token}/check-in` SHALL transition an
invitation whose `checkInStatus` is `unused` or `checked_out` to
`checked_in`, recording `checkedInAt`, subject to the invitation being
`approved`, not watchlist-blocked (unless overridden), not scanned before
its scheduled visit date, and not expired (`expiresAt` has not already
passed). "Not scanned before its scheduled visit date" means: WHEN the
invitation has a `preferredVisitDate` set, THEN a scan is rejected if the
current date (tenant-local calendar day) is earlier than `preferredVisitDate`
— the comparison is date-only, so a scan is accepted at any time of day on
or after that date, up until `expiresAt`. WHEN the invitation has no
`preferredVisitDate` set, THEN this check is skipped entirely and only the
existing `expiresAt` gate applies. Calling this endpoint for an invitation
whose `checkInStatus` is already `checked_in` SHALL be rejected with 409 and
SHALL NOT change `checkInStatus` — the caller MUST call the check-out
endpoint instead. This endpoint does not toggle between check-in and
check-out; each action has its own endpoint (see "QR Check-Out Endpoint
Transitions a Checked-In Visitor to Checked-Out"). Repeated entry/exit
cycles are otherwise unrestricted — a visitor may enter and exit as many
times as the visit requires (e.g. leaving for lunch and returning, or moving
between buildings on a multi-building site); there is no terminal state
short of the invitation's own expiry.

#### Scenario: First scan checks the visitor in
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is `unused`, and the invitation is otherwise eligible
- **THEN** `checkInStatus` becomes `checked_in`, `checkedInAt` is recorded,
  and the response indicates a successful check-in

#### Scenario: Re-entry after a prior check-out succeeds
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is `checked_out`, and the invitation is otherwise eligible
- **THEN** `checkInStatus` becomes `checked_in` again, `checkedInAt` is
  updated, and the response indicates a successful check-in

#### Scenario: Calling check-in while already checked in is rejected
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is already `checked_in`
- **THEN** the request is rejected with 409, `checkInStatus` is unchanged,
  and the response indicates the caller must use the check-out endpoint
  instead

#### Scenario: Entry scan after expiry is rejected
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is `unused` or `checked_out` and whose `expires_at` has already passed
- **THEN** the request is rejected as expired and `checkInStatus` is
  unchanged

#### Scenario: Entry scan before the scheduled visit date is rejected
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is `unused` or `checked_out`, whose `preferredVisitDate` is set, and whose
  `preferredVisitDate` is later than the current tenant-local calendar date
- **THEN** the request is rejected as too early, `checkInStatus` is
  unchanged, and the rejection is distinguishable from the expiry-rejection
  case

#### Scenario: Entry scan on the scheduled visit date succeeds regardless of time of day
- **WHEN** this endpoint is called for an invitation whose `preferredVisitDate`
  equals the current tenant-local calendar date, at any time of day, and the
  invitation is otherwise eligible
- **THEN** the check-in succeeds — the scheduled-date check is date-only and
  does not additionally require a specific time of day

#### Scenario: Entry scan with no scheduled visit date set falls back to expiry-only gating
- **WHEN** this endpoint is called for an invitation whose `preferredVisitDate`
  is not set, and the invitation is otherwise eligible and not expired
- **THEN** the check-in succeeds exactly as it did before this change — the
  scheduled-date check is skipped entirely

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
`visitorCategoryId`, primary contact name, primary contact photo URL,
purpose of visit, expiry/submission timestamps) without the per-row
visitor/vehicle detail the single-invitation tracking lookup returns.

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

## ADDED Requirements

### Requirement: Invitation Creation Notifies the Resolved Host via Email
When an invitation is created and resolves to a host (`hostId` present), the
system SHALL dispatch an informational email to that host's registered email
address stating that an invitation naming them as host was received,
asynchronously and without delaying the creation response, following the
same retry-with-backoff behavior as the visitor's existing confirmation
email. This is in addition to, not a replacement for, the existing
submission push notification sent to the host when they are the first
approval step (see "Invitation Submission Notifies the Approval Workflow's
First Approver(s) via Push") — that push only fires when the host is also
step 0's approver and the invitation is not auto-approved, whereas this
email fires on every creation with a resolved host regardless of approval
routing or auto-approve outcome. An invitation with no resolved host SHALL
skip this email dispatch without failing the creation request.

#### Scenario: Creation with a resolved host sends the host an email
- **WHEN** an invitation is created and its host resolves to a user with a
  registered email address
- **THEN** that host receives an email stating an invitation naming them was
  received, dispatched asynchronously without delaying the creation response

#### Scenario: Creation response does not wait on the host email
- **WHEN** an invitation is created with a resolved host
- **THEN** the API responds with the invitation details before the host
  email has necessarily been delivered

#### Scenario: No resolved host means no host email, and creation still succeeds
- **WHEN** an invitation is created and its host does not resolve (no
  `hostId`)
- **THEN** creation succeeds exactly as it would today, and no host email is
  dispatched

#### Scenario: Host email delivery failure is retried and logged, not surfaced to the caller
- **WHEN** the email provider is unavailable for a host-notification dispatch
- **THEN** the system retries with backoff and, if retries are exhausted,
  logs the failure with enough context to identify and manually resend it,
  without affecting the already-returned creation response

#### Scenario: Auto-approved creation still sends the host email
- **WHEN** an invitation is created and auto-approved per the Company's
  auto-approve setting, and it resolves to a host
- **THEN** the host still receives the creation-notification email, since
  this email is independent of the submission-push logic that only fires for
  non-auto-approved, first-step-host invitations
