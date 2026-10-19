## ADDED Requirements

### Requirement: An Archived Invitation Is Rescheduled Back Into Approval
A caller holding `invitations:reschedule` at the invitation's branch SHALL
be able to reschedule an `archived` invitation through
`PATCH /invitations/{id}/reschedule`. The new `preferredVisitDate` SHALL be
today or later in the visit timezone. An earlier date SHALL be rejected
with 422 and leave the invitation unchanged. On success the system SHALL:

- set `status` to `submitted` and clear `approvedAt`;
- record the new date and time, the previous date and time,
  `rescheduledAt` and an incremented `rescheduleCount`, exactly as for any
  other reschedule;
- set `expiresAt` to 23:59:59 of the new visit date in the visit timezone;
- reset every approval step to `pending` and re-activate the first one, so
  a workflow-backed invitation goes through its whole workflow again. An
  invitation with no approval steps must be approved through
  `POST /invitations/{id}/approve`. The Company's auto-approve setting
  SHALL NOT approve it automatically;
- keep `archivedAt` as a record of the earlier archive;
- write an `invitation_rescheduled` audit entry and dispatch the same
  notifications as rescheduling a `submitted` invitation. The primary
  contact's email carries no QR and states that a pass will follow
  approval. The resolved host, if any, gets a push. The newly active
  step's approver gets a push, as on an approval revert.

The QR pass issued at the original approval SHALL be kept. It SHALL NOT
admit the visitor while the invitation is `submitted`. When the invitation
is approved again, the approval notification SHALL carry that same pass.
The transition SHALL be atomic: of two concurrent reschedules for the same
archived invitation, exactly one SHALL succeed, and the other SHALL receive
409.

#### Scenario: Rescheduling an archived invitation sends it for re-approval
- **WHEN** an authorized caller reschedules an `archived` invitation to a
  future date
- **THEN** the response is 200, `status` is `submitted`, `approvedAt` is
  null, `preferredVisitDate` is the new date, `expiresAt` is the end of that
  day in the visit timezone, and `archivedAt` is unchanged

#### Scenario: Workflow restarts from the first step
- **WHEN** an archived invitation whose visitor category has a two-step
  approval workflow is rescheduled
- **THEN** both steps are `pending`, the first step is active, and its
  approver receives a push notification

#### Scenario: Auto-approve tenant still requires re-approval
- **WHEN** the Company has auto-approve enabled and an archived invitation
  with no approval steps is rescheduled
- **THEN** it stays `submitted` until someone approves it

#### Scenario: Past date is rejected
- **WHEN** a caller reschedules an archived invitation to yesterday's date
  in the visit timezone
- **THEN** the request is rejected with 422, the invitation stays
  `archived`, and no notification is dispatched

#### Scenario: Re-approval restores the original pass
- **WHEN** a rescheduled-from-archived invitation is approved again
- **THEN** its `status` is `approved`, and the approval notification
  carries the same QR token that was issued originally, which now admits
  the visitor on the new date

#### Scenario: Caller lacks invitations:reschedule
- **WHEN** a caller without `invitations:reschedule` at the invitation's
  branch reschedules an archived invitation
- **THEN** the request is rejected with 403 and the invitation stays
  `archived`

### Requirement: An Archived Invitation Does Not Admit the Visitor
Every check-in path SHALL reject an `archived` invitation with 409: QR
scan, staff check-in, and public tracking-ID check-in. The response detail
SHALL state that the invitation is archived and must be rescheduled. The
rejection SHALL leave `status` and `checkInStatus` unchanged. Extending
expiry, issuing or reprinting a badge, reverting approval, approving and
denying SHALL each be rejected with 409 for an `archived` invitation. The
only way to bring a no-show back is to reschedule it (or edit its date).

#### Scenario: QR scan of an archived pass is rejected
- **WHEN** a visitor scans the QR pass of an `archived` invitation
- **THEN** check-in is rejected with 409 saying the invitation is archived,
  and the invitation stays `archived` with `checkInStatus` `unused`

#### Scenario: Staff check-in of an archived invitation is rejected
- **WHEN** staff check in an `archived` invitation by tracking ID
- **THEN** the request is rejected with 409 saying the invitation is
  archived and must be rescheduled

#### Scenario: Expiry cannot be extended on an archived invitation
- **WHEN** a caller extends the expiry of an `archived` invitation
- **THEN** the request is rejected with 409 and `expiresAt` is unchanged

### Requirement: Invitation List Filters and Surfaces Archived and Auto Check-Out State
`archived` SHALL be an accepted value of the `status` filter on
`GET /invitations`, and the filter SHALL return only archived invitations.
The invitation list row, the invitation detail, the tracking lookup and
the check-in and check-out responses SHALL include two fields:

- `archivedAt`: the time of the latest archive, or null;
- `checkedOutAutomatically`: `true` only when the latest check-out was
  made by the sweep.

Both fields SHALL be additive. No existing field changes type or meaning.

#### Scenario: Filtering by archived
- **WHEN** a caller with `invitations:view-all` requests
  `GET /invitations?status=archived`
- **THEN** only invitations whose `status` is `archived` are returned, each
  with a non-null `archivedAt`

#### Scenario: Auto check-out is visible on the detail
- **WHEN** a caller fetches an invitation that the sweep checked out
- **THEN** the detail shows `status` `checked_out`,
  `checkedOutAutomatically` `true` and `checkedOutByUserId` null

#### Scenario: Unknown status value is still rejected
- **WHEN** a caller requests `GET /invitations?status=expired`
- **THEN** the request is rejected with a validation error

## MODIFIED Requirements

### Requirement: QR Check-Out Endpoint Transitions a Checked-In Visitor to Checked-Out
`PATCH /api/v2/invitations/qr/{token}/check-out` SHALL transition an
invitation whose `checkInStatus` is `checked_in` to `checked_out`,
recording `checkedOutAt`. This transition SHALL NOT be subject to the
expiry check that governs check-in, so a visit that legitimately continues
past `expiresAt` can still be closed out until the automatic check-out
sweep closes it ("Expired Check-Ins Are Checked Out Automatically" in the
`visit-lifecycle-sweep` capability). A check-out through this endpoint
SHALL leave `checkedOutAutomatically` `false`. Calling this endpoint for an
invitation whose `checkInStatus` is `unused` or `checked_out` SHALL be
rejected with 409 and SHALL NOT change `checkInStatus`. That includes an
invitation the sweep has already checked out.

#### Scenario: Checking out a checked-in visitor succeeds
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is `checked_in`
- **THEN** `checkInStatus` becomes `checked_out`, `checkedOutAt` is
  recorded, `checkedOutAutomatically` is `false`, and the response
  indicates a successful check-out

#### Scenario: Check-out succeeds even after expiry
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is `checked_in` and whose `expires_at` has already passed, before the
  sweep has reached it
- **THEN** the check-out succeeds exactly as it would before expiry

#### Scenario: Calling check-out on a visitor who isn't checked in is rejected
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is `unused` or `checked_out`
- **THEN** the request is rejected with 409 and `checkInStatus` is
  unchanged

#### Scenario: Check-out after the sweep already closed the visit is rejected
- **WHEN** this endpoint is called for an invitation the sweep has already
  checked out automatically
- **THEN** the request is rejected with 409 and `checkedOutAt` and
  `checkedOutAutomatically` are unchanged

### Requirement: Reschedule Dispatches a Notification to the Primary Contact
WHEN a caller successfully reschedules an invitation via `PATCH
/invitations/{id}/reschedule`, the system SHALL dispatch a reschedule
notification to the primary contact, stating the invitation's tracking ID
and its new `preferredVisitDate`/`preferredVisitTime`. The notification
SHALL be sent via the primary contact's `preferredContactMethod`: `email`
sends an email and `sms` sends a text. This is the same channel-routing
rule the creation, approval, and denial notifications already follow.
Group registrations are notified the same way as individual ones, since
only the primary contact is ever notified for any invitation lifecycle
event today. The reschedulable statuses SHALL be `submitted`, `approved`
and `archived`. An `archived` invitation SHALL leave the reschedule as
`submitted` ("An Archived Invitation Is Rescheduled Back Into Approval").
WHEN the invitation is `approved`, the reschedule email SHALL embed the
invitation's existing check-in QR inline, in the same "Your check-in pass"
block as the confirmation email. A reschedule of an approved invitation
does not re-approve the visit or issue a new token, so this is the same QR
image and token already issued. WHEN the invitation is `submitted` after
the reschedule (including one rescheduled from `archived`), the email SHALL
carry no QR and SHALL state that a pass will be sent once the visit is
approved. The reschedule email SHALL carry no file attachment. Dispatch
SHALL happen asynchronously (a background task), never inline in the
request path, and only after the reschedule is committed. A request
rejected because the invitation is not in a reschedulable status, because
the new date is in the past for an archived invitation, or because the
caller lacks branch access, SHALL NOT dispatch any notification.

#### Scenario: Successful reschedule notifies the primary contact by email
- **WHEN** a caller with `invitations:reschedule` at the invitation's branch
  successfully reschedules an `approved` invitation whose primary contact's
  `preferredContactMethod` is `email`
- **THEN** an email is dispatched to the primary contact's email address,
  stating the tracking ID, the previous and new date/time, and embedding the
  same check-in QR (same token) that was issued at approval, with no
  attachment

#### Scenario: Rescheduling a pending visit says the pass comes later
- **WHEN** a `submitted` invitation is rescheduled and its reschedule email
  is rendered
- **THEN** the email contains no QR and states that a check-in pass will be
  sent once the visit is approved

#### Scenario: Rescheduling an archived visit says the pass comes later
- **WHEN** an `archived` invitation is rescheduled and its reschedule email
  is rendered
- **THEN** the email contains no QR and states that a check-in pass will be
  sent once the visit is approved

#### Scenario: Successful reschedule notifies the primary contact by SMS when preferred
- **WHEN** a caller successfully reschedules an invitation whose primary
  contact's `preferredContactMethod` is `sms`
- **THEN** a text message is dispatched to the primary contact's phone
  number instead of an email, stating the same tracking ID and new
  date/time

#### Scenario: Rejected reschedule (ineligible status) dispatches no notification
- **WHEN** a caller attempts to reschedule an invitation that is not
  currently `submitted`, `approved` or `archived` (e.g. already
  `checked_in`), and the request is rejected with 409
- **THEN** no reschedule notification is dispatched

#### Scenario: Rejected reschedule (no branch access) dispatches no notification
- **WHEN** a caller without branch access to the invitation attempts to
  reschedule it, and the request is rejected with 403
- **THEN** no reschedule notification is dispatched

### Requirement: Authorized Caller Edits Non-Personal Invitation Details
An authenticated, branch-scoped caller holding a new `invitations:edit`
permission at the invitation's branch SHALL be able to change, via `PATCH
/invitations/{id}/edit`, any of: `purposeOfVisit` (and `purposeId`),
`preferredVisitDate`, `preferredVisitTime`, `expectedDuration` (and
`durationId`), `departmentToVisit` (and `departmentId`), location/building,
and `additionalNotes` — on an invitation currently `submitted`, `approved`
or `archived`. For an `archived` invitation:

- an edit that does not change `preferredVisitDate` SHALL leave it
  `archived`;
- an edit that changes `preferredVisitDate` SHALL require a date of today
  or later in the visit timezone, rejecting an earlier date with 422. On
  success it SHALL return the invitation to approval exactly as a
  reschedule from `archived` does: `status` `submitted`, `approvedAt`
  cleared, approval steps reset with the first re-activated, and
  `expiresAt` set to the end of the new visit day.

This endpoint SHALL NOT accept or change: the primary contact's or any
visitor's personal fields (name, email, phone, ID proof, photo),
`visitorCategoryId` (locked after creation — changing it would require
re-deriving the approval workflow, which this change does not support), or
the host (`hostId`/`hostNameOrEmail`) — host reassignment stays exclusively
the job of the `approvals` capability's delegation mechanism, so there is
exactly one way to change who the host is, not two. A request naming an
invitation that is not currently `submitted`, `approved` or `archived`
SHALL be rejected with 409, following the same atomic-conditional-UPDATE
pattern as the existing `reschedule`/`extend` endpoints, and SHALL NOT
change any field. An unknown invitation id SHALL be rejected with 404; a
caller without branch access to an existing invitation SHALL be rejected
with 403. A successful edit SHALL dispatch a notification to the primary
contact (and, if a host is currently resolved, to the host) stating which
visit details changed — the same channel-routing rule
(`preferredContactMethod`) the existing reschedule notification already
follows.

#### Scenario: Authorized edit changes multiple visit-detail fields at once
- **WHEN** a caller with `invitations:edit` at the invitation's branch edits
  a `submitted` invitation's `preferredVisitDate`, `expectedDuration`, and
  `additionalNotes` in one request
- **THEN** all three fields are updated, the invitation's other fields are
  unchanged, and the primary contact receives a notification describing the
  change

#### Scenario: Editing an archived invitation without changing its date
- **WHEN** a caller with `invitations:edit` changes only the
  `additionalNotes` of an `archived` invitation
- **THEN** the notes are updated and the invitation stays `archived`

#### Scenario: Editing an archived invitation's date sends it for re-approval
- **WHEN** a caller with `invitations:edit` changes an `archived`
  invitation's `preferredVisitDate` to a future date
- **THEN** the invitation becomes `submitted` with `approvedAt` cleared, its
  approval steps restart from the first, and `expiresAt` is the end of the
  new visit day

#### Scenario: Editing an archived invitation to a past date is rejected
- **WHEN** a caller changes an `archived` invitation's `preferredVisitDate`
  to a date before today in the visit timezone
- **THEN** the request is rejected with 422 and no field is changed

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
