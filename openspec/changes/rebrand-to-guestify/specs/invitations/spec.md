## MODIFIED Requirements

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

The Guestify header logo SHALL be served at
`GET /api/v1/public/email-assets/guestify-logo.png` with long-lived public
caching. Emails rendered from this point on SHALL reference that URL. The
retired path `GET /api/v1/public/email-assets/visimio-logo.png` SHALL keep
answering 200 `image/png` with the Guestify logo, so emails already
delivered under the old brand never show a broken image.

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

#### Scenario: New emails reference the Guestify logo URL
- **WHEN** any email is rendered with the email-asset base URL configured
- **THEN** its header `<img>` points to
  `{base}/api/v1/public/email-assets/guestify-logo.png`, and a GET on that
  URL returns 200 `image/png` with long-lived public caching

#### Scenario: Retired Visimio logo URL still resolves
- **WHEN** a mail client opens an email sent before the rebrand and
  fetches `/api/v1/public/email-assets/visimio-logo.png`
- **THEN** the response is 200 `image/png` carrying the Guestify logo, not
  a 404
