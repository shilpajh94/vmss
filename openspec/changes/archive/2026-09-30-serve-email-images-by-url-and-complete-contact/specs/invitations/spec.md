## ADDED Requirements

### Requirement: Check-In QR Images Are Served From a Signed Public URL
The system SHALL expose an unauthenticated, rate-limited endpoint (60 per
minute per IP):

`GET /api/v1/public/email-assets/{tenant_id}/qr/{invitation_id}.png?exp={unix}&sig={hmac}`

It returns the invitation's persisted check-in QR as `image/png`. The
signature SHALL be an HMAC over the tenant id, the invitation id and
`exp`, keyed by a server-side secret. `exp` SHALL be 7 days after the
invitation's `expires_at` at the time the email is rendered. The endpoint
SHALL respond:
- 403 when the signature doesn't match;
- 410 when `exp` has passed;
- 404 when the tenant, invitation or QR record doesn't exist.

The response SHALL carry `Cache-Control: private, max-age=86400` and SHALL
never reveal the token as text. The image SHALL encode exactly the token
persisted at approval. The endpoint SHALL NOT accept a tenant or
invitation id that isn't covered by the signature.

The Visimio header logo SHALL be served at
`GET /api/v1/public/email-assets/visimio-logo.png` with long-lived public
caching.

#### Scenario: Valid signed URL returns the QR
- **WHEN** a mail client fetches the QR URL from a confirmation email before
  it expires
- **THEN** the response is 200 `image/png`, and decoding it yields the
  invitation's persisted check-in token

#### Scenario: Tampered URL is rejected
- **WHEN** the `invitation_id` in a signed URL is replaced with another
  invitation's id
- **THEN** the response is 403 and no image is returned

#### Scenario: Expired URL is gone
- **WHEN** the URL is fetched after its `exp`
- **THEN** the response is 410

### Requirement: Visit-Confirmation Dispatch Is Verified Against a Real Mail Catcher With URL Images
The system SHALL be provably capable of delivering the visit-confirmation
notification through actual SMTP to a reachable mail catcher, with the
email-asset base URL configured, as a message with no attachments and no
inline parts. Its QR image URL SHALL be fetchable and return the
invitation's QR.

#### Scenario: Delivered confirmation has no attachment strip and a working QR URL
- **WHEN** the confirmation dispatch task runs using the real SMTP sender
  with the base URL configured
- **THEN** the message observed through the mail catcher's API lists zero
  attachments and zero inline parts, and fetching the QR `<img src>` from
  its HTML returns 200 `image/png`

## MODIFIED Requirements

### Requirement: Visit-Confirmation Email Embeds the QR Code in a Dedicated Scannable Block
The approval/visit-confirmation email, and the reschedule email of an
approved invitation, SHALL display the invitation's check-in QR code in
the email body, in a visually separate "Your check-in pass" block. The
image SHALL be referenced by its signed public URL (see "Check-In QR
Images Are Served From a Signed Public URL"). It SHALL be embedded inline
only in the unconfigured-base-URL fallback. The block SHALL contain:
- the QR image, encoding the same encrypted check-in token issued at
  approval, rendered at no less than 180×180 CSS pixels and not scaled
  beyond the phone viewport;
- the tracking ID in text directly under the QR image;
- one sentence instructing the visitor to show the code at reception or
  the security gate.

The QR SHALL have a white quiet-zone margin. It SHALL NOT be sent as a file
attachment. The plain-text part SHALL tell the visitor to open the email
with images shown to see their QR code, and SHALL give the tracking ID as
the fallback. Tracking-only, denial, edit, submission, host-assigned, and
POC-assigned emails SHALL NOT include a QR code.

#### Scenario: Approved visitor can scan the QR straight from the email body
- **WHEN** an invitation is approved and its primary contact prefers email
- **THEN** the email body shows a "Your check-in pass" block whose QR image
  loads from the signed URL, with the tracking ID underneath, and the
  message has no attachment

#### Scenario: Inline QR encodes the issued check-in token
- **WHEN** the QR image referenced by a visit-confirmation email is fetched
  and decoded
- **THEN** it yields exactly the check-in token persisted for that
  invitation at approval

#### Scenario: Non-approval emails carry no QR
- **WHEN** a tracking-only, denial, edit, submission, host-assigned, or
  POC-assigned email is rendered
- **THEN** it contains no check-in pass block and no QR image

## REMOVED Requirements

### Requirement: Visit-Confirmation Dispatch Is Verified Against a Real Mail Catcher With an Inline-Only QR
**Reason**: The QR is no longer an inline part. It's referenced by a
signed URL, and the delivered message carries no image parts at all.
**Migration**: Replaced by "Visit-Confirmation Dispatch Is Verified Against
a Real Mail Catcher With URL Images".
