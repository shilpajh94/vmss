## MODIFIED Requirements

### Requirement: Push Payloads Exclude Sensitive Visitor Data
A push notification payload SHALL be limited to what identifies the action to
a staff user (e.g. invitation tracking id, visitor's display name, action
type) and SHALL NOT include identity document numbers, raw OTP codes, or
other data `security-architecture.md` §2/§4 classifies as sensitive. An
invitation-related push payload SHALL additionally carry addressing
metadata so a client can distinguish how the recipient was targeted:
`assignedRoleId` (set when the recipient was reached because they hold a
given role at the invitation's branch, null otherwise), `assignedUserId`
(set when the recipient was reached as one specific named person — e.g. a
delegate or resolved host, null otherwise), and `reason`, one of
`role_assigned` (dispatched via role-at-branch fan-out) or `delegated`
(dispatched because the recipient was specifically delegated or named as
host). Exactly one of `assignedRoleId`/`assignedUserId` SHALL be set per
payload, matching how that particular push was addressed.

#### Scenario: Submission push omits ID proof data
- **WHEN** the system pushes a "new invitation awaiting your approval"
  notification
- **THEN** the payload includes the visitor's name and the invitation's
  tracking id, and never includes any identity-document number or storage key

#### Scenario: Role-fan-out push carries assignedRoleId and reason role_assigned
- **WHEN** the system pushes a notification to every holder of a role at a
  branch (e.g. invitation submission to the tenant's default host role)
- **THEN** each recipient's payload includes `assignedRoleId` set to that
  role's id, `assignedUserId` null, and `reason` set to `role_assigned`

#### Scenario: Delegation/host-assignment push carries assignedUserId and reason delegated
- **WHEN** the system pushes a notification to one specific named person
  (e.g. a step delegate, or a newly assigned host)
- **THEN** the payload includes `assignedUserId` set to that person's id,
  `assignedRoleId` null, and `reason` set to `delegated`
