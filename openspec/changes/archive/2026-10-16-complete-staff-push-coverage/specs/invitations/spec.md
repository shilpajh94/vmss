## ADDED Requirements

### Requirement: Approval, Check-In, Check-Out, Extension, and Edit Push the Point of Contact
When an invitation is approved (directly, or as the final step of a
multi-step workflow), checked in (by staff, by tracking id, by QR token or by
a kiosk device), checked out (by staff or by QR token), has its pass
extended, or has its details edited, the system SHALL send a push
notification to its point of contact, in addition to the host push already
sent for the same action:

- to the point-of-contact user, when `pocUserId` is set;
- to every user holding the point-of-contact role at the invitation's
  branch or company-wide, when `pocRoleId` is set.

The push SHALL NOT be sent to the staff member who performed the action, or
to the resolved host, who already receives the host push for the same
action. An action with no human actor (QR or kiosk check-in or check-out)
excludes only the host. A role fan-out push SHALL carry `reason:
"lifecycle_update"`, so a client doesn't label it a new assignment. The
push SHALL follow the existing rule that push payloads exclude sensitive
visitor data, and SHALL carry the same `action` value as the host push for
that action. An invitation with no point of contact SHALL skip the push
without failing the request. An action that is rejected (409, 410, 422 or
425), or an idempotent check-in that changes nothing, SHALL NOT send a
point-of-contact push.

When an edit itself names a new point of contact, that newly named point
of contact SHALL receive only the existing "named point of contact" push for
that edit, not an additional "details updated" push. The "details updated"
push SHALL go only to a point of contact that was already in place before
the edit.

#### Scenario: Point-of-contact user is pushed on check-in
- **WHEN** a visitor whose invitation has point-of-contact user P and a
  different resolved host H is checked in at reception by tracking ID
- **THEN** P receives a push stating the visitor checked in, and H still
  receives the existing host push

#### Scenario: Point-of-contact role holders are pushed on QR check-out
- **WHEN** an invitation whose point of contact is the "Security" role, with
  two holders at the invitation's branch, is checked out by QR token
- **THEN** both holders receive a push stating the visitor checked out, with
  `reason` set to `lifecycle_update`

#### Scenario: Point of contact is pushed on final-step approval
- **WHEN** an invitation with point-of-contact user P is approved because
  its last pending approval step was approved
- **THEN** P receives a push stating the invitation was approved

#### Scenario: Point of contact is pushed when the pass is extended
- **WHEN** a reception user extends the pass of an approved invitation with
  point-of-contact user P
- **THEN** P receives a push stating the pass was extended, naming the new
  expiry

#### Scenario: Existing point of contact is pushed when details are edited
- **WHEN** an invitation that already has point-of-contact user P is edited
  without changing its point of contact
- **THEN** P receives a push stating the visit details were updated

#### Scenario: Newly named point of contact is pushed once per edit
- **WHEN** an edit changes an invitation's point of contact from user P to
  user Q
- **THEN** Q receives only the "named point of contact" push, and P receives
  no push for that edit

#### Scenario: Actor who is the point of contact is not pushed
- **WHEN** point-of-contact user P checks the visitor out themself via the
  staff check-out endpoint
- **THEN** P receives no point-of-contact push for that check-out

#### Scenario: Host who is also point of contact is pushed once
- **WHEN** an invitation whose `hostId` and `pocUserId` are the same user is
  checked in
- **THEN** that user receives exactly one push for the check-in

#### Scenario: No point of contact means no push, and the action still succeeds
- **WHEN** an invitation with no point of contact is approved, checked in,
  checked out, extended or edited
- **THEN** the action succeeds and no point-of-contact push is sent

#### Scenario: Rejected action sends no point-of-contact push
- **WHEN** a check-in attempt for an invitation with a point of contact is
  rejected because the visit window has expired
- **THEN** the response is 410 and no point-of-contact push is sent
