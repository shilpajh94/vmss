## MODIFIED Requirements

### Requirement: Visit-Confirmation Email Embeds the QR Code in a Dedicated Scannable Block
The approval/visit-confirmation email SHALL display the invitation's
check-in QR code inline in the email body, in a visually separate "Your
check-in pass" block. The block SHALL contain:
- the QR image, encoding the same encrypted check-in token issued at
  approval, rendered at no less than 180×180 CSS pixels and not scaled
  beyond the phone viewport;
- the tracking ID in text directly under the QR image;
- one sentence instructing the visitor to show the code at reception or
  the security gate.

The QR image SHALL have a white quiet-zone margin, so it stays scannable in
dark-mode mail clients. The QR SHALL NOT also be sent as a file attachment.
The plain-text part SHALL tell the visitor to open the email with images
enabled to see their QR code, and SHALL give the tracking ID as the
fallback to quote at reception. Tracking-only, denial, edit, submission,
host-assigned, and POC-assigned emails SHALL NOT include a QR code.

#### Scenario: Approved visitor can scan the QR straight from the email body
- **WHEN** an invitation is approved and its primary contact prefers email
- **THEN** the email body shows a "Your check-in pass" block containing the
  QR image with the tracking ID underneath, and the message has no
  attachment

#### Scenario: Inline QR encodes the issued check-in token
- **WHEN** the inline QR image in a visit-confirmation email is decoded
- **THEN** it yields exactly the check-in token persisted for that
  invitation at approval

#### Scenario: Non-approval emails carry no QR
- **WHEN** a tracking-only, denial, edit, submission, host-assigned, or
  POC-assigned email is rendered
- **THEN** it contains no check-in pass block and no inline QR image

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
event today. WHEN the invitation is `approved`, the reschedule email SHALL
embed the invitation's existing check-in QR inline, in the same "Your
check-in pass" block as the confirmation email. A reschedule does not
re-approve the visit or issue a new token, so this is the same QR image
and token already issued. WHEN the invitation is still `submitted`, the
email SHALL carry no QR and SHALL state that a pass will be sent once the
visit is approved. The reschedule email SHALL carry no file attachment.
Dispatch SHALL happen asynchronously (a background task), never inline in
the request path, and only after the reschedule is committed. A request
rejected because the invitation is not in a reschedulable status, or
because the caller lacks branch access, SHALL NOT dispatch any
notification.

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

#### Scenario: Successful reschedule notifies the primary contact by SMS when preferred
- **WHEN** a caller successfully reschedules an invitation whose primary
  contact's `preferredContactMethod` is `sms`
- **THEN** a text message is dispatched to the primary contact's phone
  number instead of an email, stating the same tracking ID and new
  date/time

#### Scenario: Rejected reschedule (ineligible status) dispatches no notification
- **WHEN** a caller attempts to reschedule an invitation that is not
  currently `submitted` or `approved` (e.g. already `checked_in`), and the
  request is rejected with 409
- **THEN** no reschedule notification is dispatched

#### Scenario: Rejected reschedule (no branch access) dispatches no notification
- **WHEN** a caller without branch access to the invitation attempts to
  reschedule it, and the request is rejected with 403
- **THEN** no reschedule notification is dispatched

### Requirement: Reschedule and Edit Emails for an Approved Visit Confirm the Existing Pass Stays Valid
WHEN an edit notification email is dispatched for an invitation whose
status is `approved`, the email SHALL state that the check-in QR pass sent
at approval remains valid. WHEN the invitation is not yet approved, the
email SHALL instead state that a QR pass will be sent once the visit is
approved. The edit email SHALL carry no QR code. For the reschedule email,
see "Reschedule Dispatches a Notification to the Primary Contact", which
embeds the QR itself for an approved visit.

#### Scenario: Editing an approved visit reminds the visitor their pass still works
- **WHEN** an approved invitation is edited and its edit email is rendered
- **THEN** the email states that the previously sent QR pass is still valid,
  and contains no QR image

#### Scenario: Editing a pending visit says the pass comes later
- **WHEN** a `submitted` invitation is edited and its edit email is rendered
- **THEN** the email states that a QR pass will be sent once the visit is
  approved

#### Scenario: Rescheduling an approved visit reminds the visitor their pass still works
- **WHEN** an approved invitation is rescheduled and its reschedule email is
  rendered
- **THEN** the email shows the same check-in QR pass issued at approval (the
  persisted token, never a re-issued one) with the new date and time, and
  carries no attachment

#### Scenario: Rescheduling a pending visit says the pass comes later
- **WHEN** a `submitted` invitation is rescheduled and its reschedule email
  is rendered
- **THEN** the email states that a QR pass will be sent once the visit is
  approved

## ADDED Requirements

### Requirement: Visit-Confirmation Dispatch Is Verified Against a Real Mail Catcher With an Inline-Only QR
The system SHALL be provably capable of delivering the visit-confirmation
notification through actual SMTP to a reachable mail catcher, not only
asserted against a fake/recording sender. The delivered notification SHALL
carry the check-in QR code as an inline image rendered in the body, and
SHALL carry no file attachment.

#### Scenario: Confirmation email arrives with the QR embedded inline and nothing attached
- **WHEN** the confirmation dispatch task runs for a created invitation
  using the real SMTP-backed sender
- **THEN** the message observed through the mail catcher's API is addressed
  to the primary contact with the expected subject, contains an inline PNG
  part whose `Content-ID` its HTML part references inside the check-in pass
  block, and lists zero attachments

## REMOVED Requirements

### Requirement: Visit-Confirmation Dispatch Is Verified Against a Real Mail Catcher
**Reason**: It asserts a QR-code PNG attachment. The confirmation email no
longer carries one, because the QR is shown inline only.
**Migration**: Replaced by "Visit-Confirmation Dispatch Is Verified Against
a Real Mail Catcher With an Inline-Only QR", which asserts the inline
`Content-ID` part and zero attachments. The Mailpit test is updated to
match.
