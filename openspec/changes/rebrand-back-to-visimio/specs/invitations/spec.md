## ADDED Requirements

### Requirement: Retired Guestify Logo URL Still Resolves
The Visimio header logo SHALL be served at `GET /api/v1/public/email-assets/visimio-logo.png` with long-lived public caching, and emails rendered from this point on SHALL reference that URL. The path `GET /api/v1/public/email-assets/guestify-logo.png` SHALL keep answering 200 `image/png` with the same image, so emails already delivered while the product was named Guestify never show a broken image.

#### Scenario: New emails reference the Visimio logo URL
- **WHEN** any email is rendered with the email-asset base URL configured
- **THEN** its header `<img>` points to `{base}/api/v1/public/email-assets/visimio-logo.png`, and a GET on that URL returns 200 `image/png` with long-lived public caching

#### Scenario: Retired Guestify logo URL still resolves
- **WHEN** a mail client opens an email sent during the Guestify period and fetches `/api/v1/public/email-assets/guestify-logo.png`
- **THEN** the response is 200 `image/png` with bytes identical to the Visimio logo, not a 404

#### Scenario: New emails never use the retired URL
- **WHEN** any email type is rendered
- **THEN** no `<img>` in it references `guestify-logo.png`
