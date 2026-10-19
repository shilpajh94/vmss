## ADDED Requirements

### Requirement: Denial, Approval Revert, and Reschedule Email the Responsible Staff
When an invitation is denied (directly, or through a rejected approval
step), has its approval reverted, or is rescheduled (including a reschedule
that moves an `archived` invitation back into approval), the system SHALL
send a staff lifecycle email to each of the invitation's **responsible
staff**. These are:

- the resolved host (`hostId`), when set;
- the point-of-contact user (`pocUserId`), when set.

The system SHALL work out the recipient set when the action succeeds, and
SHALL apply these rules:

- each person receives at most one email per action, even if they are both
  host and point of contact;
- the staff member who performed the action SHALL NOT receive the email;
- a recipient who is deactivated or deleted SHALL be skipped;
- a role-identified point of contact (`pocRoleId`) SHALL NOT receive an
  email. It is notified by push only, consistent with the existing rule
  that a role-identified point of contact never receives email.

These emails SHALL be in addition to the visitor's existing email or SMS and
the host's existing push for the same action, which are unchanged. They
SHALL be sent only after the action has been committed, and SHALL NOT delay
or fail the triggering request. A rejected action (409, 403, 404, 422) SHALL
NOT send any staff email.

A staff lifecycle email SHALL be skipped if, by the time it is sent, the
invitation no longer reflects the event:

- for a denial, the invitation is no longer `denied`;
- for a revert, the invitation is no longer `submitted` with
  `approvalRevertedAt` set;
- for a reschedule, the invitation is `denied`, `checked_in` or
  `checked_out`.

#### Scenario: Revert emails the host and the point of contact
- **WHEN** a reception user reverts the approval of an invitation whose
  host is user H and whose point of contact is user P
- **THEN** H and P each receive one staff lifecycle email stating that the
  approval was withdrawn, including the revert reason, and the visitor
  still receives the existing withdrawal email without the reason

#### Scenario: The actor is not emailed about their own action
- **WHEN** the invitation's host H reschedules it themselves, and its point
  of contact is user P
- **THEN** P receives a staff lifecycle email and H does not

#### Scenario: Host who is also point of contact gets one email
- **WHEN** an invitation is denied whose `hostId` and `pocUserId` are the
  same user
- **THEN** that user receives exactly one staff lifecycle email for the
  denial

#### Scenario: Denial via a rejected approval step emails the staff
- **WHEN** an approver rejects an invitation's current step, which denies
  the invitation
- **THEN** the invitation's host and point-of-contact user, excluding the
  rejecting approver, each receive a staff lifecycle email that includes
  the denial reason

#### Scenario: Role-identified point of contact receives no email
- **WHEN** an invitation whose point of contact is a role (no `pocUserId`)
  and which has no resolved host is denied
- **THEN** no staff lifecycle email is sent, and the request still succeeds

#### Scenario: Deactivated recipient is skipped
- **WHEN** an invitation is rescheduled whose host has been deactivated
- **THEN** no email is sent to that host, any other recipient is still
  emailed, and the request still succeeds

#### Scenario: A rejected action sends no staff email
- **WHEN** a revert is attempted on an invitation that is already
  `checked_in` and is rejected with 409
- **THEN** no staff lifecycle email is sent

#### Scenario: A redelivered email after a later change is skipped
- **WHEN** a revert's staff email is delivered a second time after the
  invitation has already been re-approved
- **THEN** no email is sent on that second delivery

### Requirement: Denial, Approval Revert, and Reschedule Push the Point of Contact
When an invitation is denied, has its approval reverted, or is rescheduled,
the system SHALL send a push notification to its point of contact:

- to the point-of-contact user, when `pocUserId` is set;
- to every user holding the point-of-contact role at the invitation's
  branch or company-wide, when `pocRoleId` is set.

The push SHALL NOT be sent to the staff member who performed the action, or
to the resolved host, who already receives the host push for the same
action. The push SHALL follow the existing rule that push payloads exclude
sensitive visitor data. An invitation with no point of contact SHALL skip
the push without failing the request.

#### Scenario: Point-of-contact user is pushed on reschedule
- **WHEN** an invitation with point-of-contact user P is rescheduled by a
  reception user
- **THEN** P receives a push stating the visit was rescheduled to the new
  date and time

#### Scenario: Point-of-contact role holders are pushed on denial
- **WHEN** an invitation whose point of contact is the "Security" role is
  denied, and two users hold that role at the invitation's branch
- **THEN** both users receive a push stating the visit was denied

#### Scenario: Host who is also point of contact is pushed once
- **WHEN** an invitation is reverted whose `hostId` and `pocUserId` are the
  same user
- **THEN** that user receives exactly one push for the revert

### Requirement: Invitation Expiry Extension Notifies the Host via Push
When `PATCH /invitations/{id}/extend` succeeds for an invitation with a
resolved host, the system SHALL send that host a push notification stating
the new expiry. An invitation with no resolved host SHALL skip the push
without failing the request. A rejected extension (409 or 422) SHALL NOT send
any push.

#### Scenario: Extension notifies the host
- **WHEN** a reception user extends the pass of an approved invitation
  with a resolved host
- **THEN** the host receives a push stating the visit's pass was extended
  and naming the new expiry

#### Scenario: Extension without a host still succeeds
- **WHEN** an invitation with no resolved host is extended
- **THEN** the extension succeeds and no push is sent

#### Scenario: Rejected extension sends no push
- **WHEN** an extension is rejected because the new expiry is not later
  than the current one
- **THEN** the response is 422 and no push is sent
