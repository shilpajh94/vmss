## MODIFIED Requirements

### Requirement: Invitation Has an Expiry-Bound Tracking Identity
Every created invitation SHALL receive a system-generated, human-readable
tracking ID (displayable and speakable, e.g. for a phone lookup) and an
expiry timestamp set at creation time, neither of which the request body can
override.

The expiry timestamp SHALL be 23:59:59 on the invitation's
`preferredVisitDate`, measured in the **visit timezone**, and SHALL NOT
depend on when the invitation was submitted. The visit timezone SHALL be the
first valid IANA zone name among: the company's configured default timezone,
the tenant's timezone, and `UTC`. A configured value that isn't a valid IANA
zone name SHALL be skipped in favour of the next option, not rejected with
an error.

Whenever `preferredVisitDate` changes (reschedule, or an edit that sets
`preferredVisitDate` to a different date), the system SHALL recalculate the expiry to the end of
the new visit day in the visit timezone, whatever the invitation's approval
status. Approving an invitation SHALL also set the expiry to the end of its
visit day. Only an explicit staff expiry extension MAY set the expiry to any
other value.

#### Scenario: Tracking ID is generated, not client-supplied
- **WHEN** an invitation is created
- **THEN** the response includes a system-generated tracking ID and an
  expiry timestamp, regardless of any value the request body supplied

#### Scenario: Expiry is the end of the visit day, not a fixed duration from submission
- **WHEN** an invitation (staff pre-registration or visitor walk-in) is
  created at 2026-09-25 14:53 IST with `preferredVisitDate` 2026-10-02 and
  `preferredVisitTime` 11:00, and the visit timezone is `Asia/Kolkata`
- **THEN** `expiresAt` is 2026-10-02 23:59:59 in `Asia/Kolkata`
  (2026-10-02T18:29:59Z)

#### Scenario: Company timezone takes precedence over tenant timezone
- **WHEN** the company's default timezone is `Asia/Kolkata`, the tenant's
  timezone is `UTC`, and an invitation is created for 2026-10-02
- **THEN** `expiresAt` is 2026-10-02T18:29:59Z, not 2026-10-02T23:59:59Z

#### Scenario: Missing or invalid company timezone falls back to the tenant timezone
- **WHEN** the company's default timezone is unset or isn't a valid IANA zone
  name, the tenant's timezone is `Asia/Kolkata`, and an invitation is created
  for 2026-10-02
- **THEN** `expiresAt` is 2026-10-02T18:29:59Z and the request succeeds

#### Scenario: No valid timezone configured falls back to UTC
- **WHEN** neither the company's default timezone nor the tenant's timezone
  is a valid IANA zone name, and an invitation is created for 2026-10-02
- **THEN** `expiresAt` is 2026-10-02T23:59:59Z and the request succeeds

#### Scenario: Rescheduling a submitted invitation moves its expiry
- **WHEN** a `submitted` invitation for 2026-10-02 is rescheduled to
  2026-10-20, with the visit timezone `Asia/Kolkata`
- **THEN** `expiresAt` becomes 2026-10-20 23:59:59 in `Asia/Kolkata`

#### Scenario: Rescheduling an approved invitation moves its expiry
- **WHEN** an `approved` invitation for 2026-10-02 is rescheduled to
  2026-10-05, with the visit timezone `Asia/Kolkata`
- **THEN** `expiresAt` becomes 2026-10-05 23:59:59 in `Asia/Kolkata`

#### Scenario: Editing the visit date moves the expiry
- **WHEN** an invitation is edited and the edit request sets
  `preferredVisitDate` from 2026-10-02 to 2026-10-03
- **THEN** `expiresAt` becomes 2026-10-03 23:59:59 in the visit timezone

#### Scenario: Editing other fields leaves the expiry unchanged
- **WHEN** an invitation is edited and the edit request either omits
  `preferredVisitDate` or resends the invitation's current date unchanged
- **THEN** `expiresAt` is unchanged, including a value previously set by a
  staff expiry extension

#### Scenario: Existing open invitations are realigned
- **WHEN** an invitation created before this change has a non-terminal
  `status` (`pending`, `submitted`, `approved`, or `checked_in`), a set
  `preferredVisitDate`, and an `expiresAt` still equal to its submission
  time + 7 days
- **THEN** after the deployment's migrations run, its `expiresAt` is the end
  of its `preferredVisitDate` in the visit timezone

#### Scenario: Terminal invitations are not realigned
- **WHEN** an invitation created before this change has `status` `denied`,
  `cancelled`, or `checked_out`
- **THEN** its `expiresAt` is unchanged by the deployment's migrations

#### Scenario: Staff-extended or already-aligned expiries are not realigned
- **WHEN** an existing open invitation's `expiresAt` is no longer its
  submission time + 7 days (a staff extension or a value already computed by
  the end-of-visit-day rule)
- **THEN** its `expiresAt` is unchanged by the deployment's migrations

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
current date (calendar day in the visit timezone, the same timezone used to
compute `expiresAt`) is earlier than `preferredVisitDate`. The comparison is
date-only, so a scan is accepted at any time of day on or after that date,
up until `expiresAt`. WHEN the
invitation has no `preferredVisitDate` set, THEN this check is skipped
entirely and only the existing `expiresAt` gate applies. Calling this
endpoint for an invitation whose `checkInStatus` is already `checked_in`
SHALL be rejected with 409 and SHALL NOT change `checkInStatus`; the caller
MUST call the check-out endpoint instead. This endpoint does not toggle
between check-in and check-out; each action has its own endpoint (see "QR
Check-Out Endpoint Transitions a Checked-In Visitor to Checked-Out").
Repeated entry/exit cycles are otherwise unrestricted. A visitor may enter
and exit as many times as the visit requires (e.g. leaving for lunch and
returning, or moving between buildings on a multi-building site); there is
no terminal state short of the invitation's own expiry.

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
  `preferredVisitDate` is later than the current calendar date in the visit
  timezone
- **THEN** the request is rejected as too early, `checkInStatus` is
  unchanged, and the rejection is distinguishable from the expiry-rejection
  case

#### Scenario: Entry scan on the scheduled visit date succeeds regardless of time of day
- **WHEN** this endpoint is called for an invitation whose `preferredVisitDate`
  equals the current calendar date in the visit timezone, at any time of
  day, and the invitation is otherwise eligible
- **THEN** the check-in succeeds. The scheduled-date check is date-only and
  does not additionally require a specific time of day

#### Scenario: Visit-date gate and expiry agree on the visit day
- **WHEN** the company's default timezone is `Asia/Kolkata`, the tenant's
  timezone is `UTC`, and an approved invitation for 2026-10-02 is scanned at
  2026-10-02 00:30 IST (2026-10-01T19:00Z)
- **THEN** the check-in succeeds, because the visit-timezone date is
  2026-10-02, even though the UTC date is still 2026-10-01

#### Scenario: Entry scan with no scheduled visit date set falls back to expiry-only gating
- **WHEN** this endpoint is called for an invitation whose `preferredVisitDate`
  is not set, and the invitation is otherwise eligible and not expired
- **THEN** the check-in succeeds exactly as it did before this change. The
  scheduled-date check is skipped entirely
