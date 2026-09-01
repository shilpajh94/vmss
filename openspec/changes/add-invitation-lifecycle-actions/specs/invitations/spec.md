## ADDED Requirements

### Requirement: Authenticated Detail Lookup by Invitation ID
A caller holding `invitations:view` SHALL be able to retrieve a single
invitation's full detail — everything `GET /invitations/track` returns plus its
branch, source, creator, and the full lifecycle state introduced by this
capability (denial, check-in/out, badge, watchlist-override fields) — by its
invitation id. Branch authorization follows the same pattern
`POST /invitations/{id}/approve` already uses: an unknown id SHALL be rejected
with 404, and a caller who lacks `invitations:view` at the invitation's own
branch SHALL be rejected with 403 without revealing whether the id exists.

#### Scenario: Detail lookup returns full lifecycle state
- **WHEN** a caller with `invitations:view` at the invitation's branch requests
  `GET /invitations/{id}`
- **THEN** the response includes the invitation's branch, source, creator, and
  every denial/check-in/check-out/badge/watchlist-override field currently set
  on it

#### Scenario: Unknown invitation id is rejected with 404
- **WHEN** a caller requests `GET /invitations/{id}` for an id that does not
  exist
- **THEN** the system returns 404

#### Scenario: Caller lacks branch access to an existing invitation
- **WHEN** a caller with `invitations:view` only at a different branch requests
  `GET /invitations/{id}` for an invitation at another branch
- **THEN** the request is rejected with 403, not 404

### Requirement: A Submitted Invitation Can Be Denied With a Reason
A caller holding `invitations:deny` at the invitation's branch SHALL be able to
transition a `submitted` invitation to `denied`, supplying a mandatory reason
that is recorded with a timestamp. The system SHALL then dispatch a denial
notification (tracking ID, denied status, and the reason) to the primary
contact, asynchronously, the same dispatch-after-commit pattern
`POST /invitations/{id}/approve` uses. Denying an invitation that is not
currently `submitted` SHALL be rejected with 409, leaving its status unchanged.
An unknown invitation id SHALL be rejected with 404, and a caller lacking
branch access to an existing invitation SHALL be rejected with 403.

#### Scenario: Denial transitions status and dispatches a notification
- **WHEN** a caller with `invitations:deny` at the invitation's branch denies a
  `submitted` invitation with a reason
- **THEN** the invitation's status becomes `denied`, the reason and a denial
  timestamp are recorded, and a denial notification is dispatched to the
  primary contact

#### Scenario: Missing reason is rejected
- **WHEN** a caller attempts to deny an invitation without supplying a reason
- **THEN** the request is rejected with a validation error and the
  invitation's status is unchanged

#### Scenario: Denying a non-submitted invitation is rejected
- **WHEN** a caller attempts to deny an invitation whose status is not
  `submitted` (e.g. already `approved` or `denied`)
- **THEN** the request is rejected with 409 and no notification is dispatched

#### Scenario: Caller lacks invitations:deny
- **WHEN** a caller without `invitations:deny` attempts to deny a `submitted`
  invitation
- **THEN** the request is rejected with 403 and the invitation is unchanged

### Requirement: An Approved Invitation Can Be Checked In
A caller holding `invitations:checkin` at the invitation's branch SHALL be able
to transition an `approved` invitation to `checked_in`, recording who performed
the check-in and when. Checking in an invitation that is not currently
`approved` SHALL be rejected with 409. Checking in an invitation whose
`watchlistFlagged` is `true` and has not been cleared via
`POST /invitations/{id}/watchlist-override` SHALL be rejected with 409 — see
"A Watchlist-Flagged Invitation Blocks Check-In Until Overridden". The endpoint
SHALL accept an `Idempotency-Key` header (api-conventions.md §3): a retried
request with the same key and tenant context SHALL return the original
response rather than re-performing the transition or dispatching a second
notification.

#### Scenario: Check-in transitions status and records who and when
- **WHEN** a caller with `invitations:checkin` at the invitation's branch
  checks in an `approved`, non-flagged invitation
- **THEN** the invitation's status becomes `checked_in`, and the check-in
  timestamp and performing user are recorded

#### Scenario: Checking in a non-approved invitation is rejected
- **WHEN** a caller attempts to check in an invitation whose status is not
  `approved` (e.g. `submitted`, already `checked_in`, or `denied`)
- **THEN** the request is rejected with 409 and the invitation is unchanged

#### Scenario: Retried check-in with the same idempotency key is not duplicated
- **WHEN** a caller retries `PATCH /invitations/{id}/check-in` with the same
  `Idempotency-Key` header and tenant context as an earlier successful request
- **THEN** the invitation is checked in exactly once, and both requests
  receive the same response body

#### Scenario: Caller lacks invitations:checkin
- **WHEN** a caller without `invitations:checkin` attempts to check in an
  `approved` invitation
- **THEN** the request is rejected with 403 and the invitation is unchanged

### Requirement: A Checked-In Invitation Can Be Checked Out
A caller holding `invitations:checkout` at the invitation's branch SHALL be
able to transition a `checked_in` invitation to `checked_out`, recording who
performed the check-out and when, closing the visit. Checking out an
invitation that is not currently `checked_in` SHALL be rejected with 409. The
endpoint SHALL accept an `Idempotency-Key` header with the same retry-safety
guarantee as check-in.

#### Scenario: Check-out transitions status and records who and when
- **WHEN** a caller with `invitations:checkout` at the invitation's branch
  checks out a `checked_in` invitation
- **THEN** the invitation's status becomes `checked_out`, and the check-out
  timestamp and performing user are recorded

#### Scenario: Checking out a non-checked-in invitation is rejected
- **WHEN** a caller attempts to check out an invitation whose status is not
  `checked_in`
- **THEN** the request is rejected with 409 and the invitation is unchanged

#### Scenario: Retried check-out with the same idempotency key is not duplicated
- **WHEN** a caller retries `PATCH /invitations/{id}/check-out` with the same
  `Idempotency-Key` header and tenant context as an earlier successful request
- **THEN** the invitation is checked out exactly once, and both requests
  receive the same response body

#### Scenario: Caller lacks invitations:checkout
- **WHEN** a caller without `invitations:checkout` attempts to check out a
  `checked_in` invitation
- **THEN** the request is rejected with 403 and the invitation is unchanged

### Requirement: Visit Date/Time Can Be Rescheduled Before Check-In
A caller holding `invitations:reschedule` at the invitation's branch SHALL be
able to change an invitation's `preferredVisitDate`/`preferredVisitTime` while
its status is `submitted` or `approved`. Rescheduling an invitation whose
status is `checked_in`, `checked_out`, or `denied` SHALL be rejected with 409,
since the visit has already started, ended, or been rejected.

#### Scenario: Reschedule updates date and time before check-in
- **WHEN** a caller with `invitations:reschedule` at the invitation's branch
  reschedules a `submitted` or `approved` invitation to a new date/time
- **THEN** the invitation's `preferredVisitDate`/`preferredVisitTime` reflect
  the new values and its status is unchanged

#### Scenario: Rescheduling after check-in is rejected
- **WHEN** a caller attempts to reschedule an invitation whose status is
  `checked_in`, `checked_out`, or `denied`
- **THEN** the request is rejected with 409 and the invitation's date/time are
  unchanged

#### Scenario: Caller lacks invitations:reschedule
- **WHEN** a caller without `invitations:reschedule` attempts to reschedule an
  eligible invitation
- **THEN** the request is rejected with 403 and the invitation is unchanged

### Requirement: An Active Visit's Expiry Can Be Extended
A caller holding `invitations:extend` at the invitation's branch SHALL be able
to push an invitation's `expiresAt` forward while its status is `approved` or
`checked_in`. The new expiry SHALL be strictly later than the current one;
otherwise the request SHALL be rejected with a validation error. Extending an
invitation whose status is `submitted`, `checked_out`, or `denied` SHALL be
rejected with 409.

#### Scenario: Extension pushes expiry forward for an active visit
- **WHEN** a caller with `invitations:extend` at the invitation's branch
  extends an `approved` or `checked_in` invitation to a later expiry
- **THEN** the invitation's `expiresAt` is updated to the new value

#### Scenario: A new expiry that is not later than the current one is rejected
- **WHEN** a caller submits a new expiry that is equal to or earlier than the
  invitation's current `expiresAt`
- **THEN** the request is rejected with a validation error and `expiresAt` is
  unchanged

#### Scenario: Extending an ineligible invitation is rejected
- **WHEN** a caller attempts to extend an invitation whose status is
  `submitted`, `checked_out`, or `denied`
- **THEN** the request is rejected with 409 and `expiresAt` is unchanged

#### Scenario: Caller lacks invitations:extend
- **WHEN** a caller without `invitations:extend` attempts to extend an
  eligible invitation
- **THEN** the request is rejected with 403 and `expiresAt` is unchanged

### Requirement: A Badge Can Be Printed for an Approved or Active Visit
A caller holding `invitations:badge` at the invitation's branch SHALL be able
to issue a printable badge for an invitation whose status is `approved` or
`checked_in`, generating a human-readable badge number and a rendered badge
image (visitor name, tracking ID, a QR code encoding the tracking ID, and the
expiry) retrievable via a returned URL. Issuing a badge for an invitation whose
status is `submitted`, `denied`, or `checked_out` SHALL be rejected with 409.
Issuing a badge for an invitation that already has one SHALL be rejected with
409 directing the caller to the reprint endpoint instead. The endpoint SHALL
accept an `Idempotency-Key` header with the same retry-safety guarantee as
check-in.

#### Scenario: Badge issuance returns a badge number and retrievable image
- **WHEN** a caller with `invitations:badge` at the invitation's branch
  requests a badge for an `approved` or `checked_in` invitation with no badge
  yet issued
- **THEN** the response includes a generated badge number, the issuance
  timestamp, and a URL from which the rendered badge image can be retrieved

#### Scenario: Issuing a badge for an ineligible invitation is rejected
- **WHEN** a caller attempts to issue a badge for an invitation whose status
  is `submitted`, `denied`, or `checked_out`
- **THEN** the request is rejected with 409 and no badge is issued

#### Scenario: Issuing a second badge is rejected in favor of reprint
- **WHEN** a caller attempts to issue a badge for an invitation that already
  has one
- **THEN** the request is rejected with 409 and no second badge number is
  generated

#### Scenario: Caller lacks invitations:badge
- **WHEN** a caller without `invitations:badge` attempts to issue a badge for
  an eligible invitation
- **THEN** the request is rejected with 403 and no badge is issued

### Requirement: A Badge Can Be Reprinted
A caller holding `invitations:badge` SHALL be able to reprint an
already-issued badge, re-rendering it from the invitation's current data (so a
reprint after a reschedule or extension reflects the updated values) and
incrementing a reprint counter. Reprinting an invitation with no badge issued
yet SHALL be rejected with 409 directing the caller to the issuance endpoint
instead.

#### Scenario: Reprint re-renders and increments the counter
- **WHEN** a caller with `invitations:badge` reprints an invitation that
  already has a badge issued
- **THEN** the badge is re-rendered, its retrieval URL and reprint count are
  updated, and the original badge number is unchanged

#### Scenario: Reprint reflects data changed since original issuance
- **WHEN** an invitation's expiry was extended or its visit was rescheduled
  after its badge was first issued, and the caller then reprints it
- **THEN** the re-rendered badge reflects the current expiry/visit date, not
  the values captured at original issuance

#### Scenario: Reprinting with no badge issued yet is rejected
- **WHEN** a caller attempts to reprint a badge for an invitation with no
  badge issued yet
- **THEN** the request is rejected with 409 and no badge is generated

#### Scenario: Caller lacks invitations:badge
- **WHEN** a caller without `invitations:badge` attempts to reprint a badge
- **THEN** the request is rejected with 403

### Requirement: A Watchlist-Flagged Invitation Blocks Check-In Until Overridden
An invitation carries a `watchlistFlagged` marker (set by means outside this
capability's scope — no automatic watchlist matching is introduced here).
WHEN `watchlistFlagged` is `true`, `PATCH /invitations/{id}/check-in` SHALL be
rejected with 409 until a caller holding `invitations:watchlist-override`
clears it via `POST /invitations/{id}/watchlist-override`, supplying a
mandatory reason. The system SHALL record who overrode the flag, when, and
why. Overriding an invitation that is not currently flagged SHALL be rejected
with 409. Overriding does not itself perform check-in — it only clears the
block so a subsequent `PATCH /invitations/{id}/check-in` call can succeed.

#### Scenario: Check-in is blocked while the flag is set
- **WHEN** a caller attempts to check in an `approved` invitation whose
  `watchlistFlagged` is `true` and has not been overridden
- **THEN** the request is rejected with 409 and the invitation remains
  `approved`

#### Scenario: Override clears the flag and records who, when, and why
- **WHEN** a caller with `invitations:watchlist-override` overrides a
  flagged invitation with a reason
- **THEN** the flag is cleared and the override timestamp, actor, and reason
  are recorded, but the invitation's status is unchanged

#### Scenario: Check-in succeeds after an override
- **WHEN** a previously-flagged invitation has been overridden and a caller
  with `invitations:checkin` then checks it in
- **THEN** the check-in succeeds exactly as it would for a never-flagged
  invitation

#### Scenario: Overriding a non-flagged invitation is rejected
- **WHEN** a caller attempts to override an invitation whose
  `watchlistFlagged` is not currently `true`
- **THEN** the request is rejected with 409

#### Scenario: Missing reason is rejected
- **WHEN** a caller attempts to override a flagged invitation without
  supplying a reason
- **THEN** the request is rejected with a validation error and the flag
  remains set

#### Scenario: Caller lacks invitations:watchlist-override
- **WHEN** a caller without `invitations:watchlist-override` attempts to
  override a flagged invitation
- **THEN** the request is rejected with 403 and the flag remains set
