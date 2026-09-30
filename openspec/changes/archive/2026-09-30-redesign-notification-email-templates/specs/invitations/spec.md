## MODIFIED Requirements

### Requirement: Visit-Confirmation Dispatch Is Verified Against a Real Mail Catcher
The system SHALL be provably capable of delivering the visit-confirmation
notification through actual SMTP to a reachable mail catcher, not only
asserted against a fake/recording sender. The delivered notification SHALL
include the QR code both as an inline image rendered in the body and as a
valid QR-code image attachment.

#### Scenario: Confirmation email arrives with a valid QR attachment
- **WHEN** the confirmation dispatch task runs for a created invitation
  using the real SMTP-backed sender
- **THEN** a message addressed to the invitation's primary contact, with the
  expected subject, and carrying a valid PNG attachment is observable
  through the mail catcher's own API

#### Scenario: Confirmation email arrives with the QR embedded inline
- **WHEN** the confirmation dispatch task runs for a created invitation
  using the real SMTP-backed sender
- **THEN** the message observed through the mail catcher contains an
  inline PNG part with a `Content-ID`, and its HTML part references that
  content ID in an `<img>` inside the check-in pass block

## ADDED Requirements

### Requirement: Visit-Confirmation Email Embeds the QR Code in a Dedicated Scannable Block
The approval/visit-confirmation email SHALL display the invitation's
check-in QR code inline in the email body, in a visually separate "Your
check-in pass" block placed after the lead paragraph and before the visit
detail table. The block SHALL contain:
- the QR image, encoding the same encrypted check-in token issued at
  approval, rendered at no less than 180×180 CSS pixels and not scaled
  beyond the phone viewport;
- the tracking ID in text directly under the QR image;
- one sentence instructing the visitor to show the code at the entrance
  or kiosk.

The QR image SHALL have a white quiet-zone margin so it remains scannable
in dark-mode mail clients. The same QR SHALL continue to be attached as a
PNG file, so the visitor can save or print it when their mail client
blocks inline images. The plain-text part SHALL state that the QR code is
attached. Tracking-only, denial, submission, host-assigned, and
POC-assigned emails SHALL NOT include a QR code.

#### Scenario: Approved visitor can scan the QR straight from the email body
- **WHEN** an invitation is approved and its primary contact prefers email
- **THEN** the email body shows a "Your check-in pass" block containing
  the QR image with the tracking ID underneath, and the same QR is also
  attached as a PNG file

#### Scenario: Inline QR encodes the issued check-in token
- **WHEN** the inline QR image in a visit-confirmation email is decoded
- **THEN** it yields exactly the check-in token persisted for that
  invitation at approval, the same value the attachment encodes

#### Scenario: Non-approval emails carry no QR
- **WHEN** a tracking-only, denial, submission, host-assigned, or
  POC-assigned email is rendered
- **THEN** it contains no check-in pass block, no inline QR image, and no
  QR attachment

### Requirement: Reschedule and Edit Emails for an Approved Visit Confirm the Existing Pass Stays Valid
WHEN a reschedule or edit notification email is dispatched for an
invitation whose status is `approved`, the email SHALL state that the
check-in QR pass sent at approval remains valid and should be used on the
visit day. WHEN the invitation is not yet approved, the email SHALL instead
state that a QR pass will be sent once the visit is approved. In both
cases the email SHALL carry no QR code, consistent with "Reschedule
Dispatches a Notification to the Primary Contact".

#### Scenario: Rescheduling an approved visit reminds the visitor their pass still works
- **WHEN** an approved invitation is rescheduled and its reschedule email is
  rendered
- **THEN** the email states that the previously sent QR pass is still valid
  for the new date, and contains no QR image or attachment

#### Scenario: Rescheduling a pending visit says the pass comes later
- **WHEN** a `submitted` invitation is rescheduled and its reschedule email
  is rendered
- **THEN** the email states that a QR pass will be sent once the visit is
  approved
