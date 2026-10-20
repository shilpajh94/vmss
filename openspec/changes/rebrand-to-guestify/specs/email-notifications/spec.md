## MODIFIED Requirements

### Requirement: Every Notification Email Is Rendered From a Branded HTML Template
The system SHALL render every outbound email from an HTML template
composed of a shared Guestify base layout and a per-type content block.
That covers visit confirmation, tracking-only (received), denial,
reschedule, edit, submission fan-out to the owning role, host assignment,
point-of-contact assignment, the verification-code email, and the daily
snapshot email. The base layout SHALL consist of, in order:
- a dark header band carrying the tenant's logo when one is configured,
  otherwise the Guestify logo (the "G" pin mark plus a wordmark legible on
  the dark band) as an inline image with alt text "Guestify";
- an accent rule under the header;
- a content card with, where the type defines one, a short uppercase status
  pill coloured by the email's tone, followed by a heading, an optional
  greeting, and the type's content sections;
- a footer stating who sent the message ("Sent by {company}", defaulting to
  "Guestify") and that it is automated and must not be replied to, a
  "Powered by Guestify" mark, and "© {current year} Guestify".

The layout SHALL render legibly both in a desktop mail client (content
capped at 600px wide) and on a phone (content fluid to the viewport width,
with no horizontal scrolling). Each rendered email SHALL carry a
plain-text fallback part (multipart `text/plain` + `text/html`). No
template SHALL interpolate an identity-document number. The
verification-code template is the only template that SHALL contain a
one-time code, and only the code being delivered to that recipient. The
From header SHALL carry the display name "Guestify" (configurable) in
front of the sender address.

#### Scenario: Approval email renders from the HTML template with a plain-text fallback
- **WHEN** an invitation is approved and its approval email is dispatched
- **THEN** a mail client that renders HTML shows the Guestify layout
  (header with logo, accent rule, status pill, heading, content sections,
  footer), and a client that cannot falls back to an equivalent plain-text
  version carrying the same information

#### Scenario: Visimio branding is shown when the tenant has no logo
- **WHEN** any email is rendered for a tenant whose Company profile has no
  logo URL
- **THEN** the header shows the Guestify logo image with alt text "Guestify",
  the footer reads "Powered by Guestify" and "© {current year} Guestify",
  and neither "VisitorPass" nor "Visimio" appears anywhere in the email

#### Scenario: Tenant logo replaces the wordmark when configured
- **WHEN** the tenant's Company profile has a logo URL and any email is
  rendered
- **THEN** the header band shows that logo, with the company name as its
  alt text, and the footer still reads "Powered by Guestify"

#### Scenario: Layout fits a narrow phone screen
- **WHEN** any email is opened in a mail client with a viewport narrower
  than 600px
- **THEN** the card, detail sections, highlight boxes, and any QR block
  shrink to the viewport width, and no content requires horizontal
  scrolling

#### Scenario: A sensitive field is never interpolated into a template
- **WHEN** any email other than the verification-code email is rendered for
  an invitation whose visitor has an ID-proof number, or after an OTP was
  used to produce it
- **THEN** the rendered email (HTML or plain-text part) contains neither the
  ID-proof number nor any OTP

#### Scenario: From name defaults to Guestify
- **WHEN** an email is sent and no From display name is configured
- **THEN** the From header reads `Guestify <{sender address}>`

### Requirement: Email Images Are Referenced by URL, Never Attached or Embedded
WHEN the public email-asset base URL is configured, every email's images
SHALL be referenced by absolute `https://` URLs under that base: the
Guestify header logo and, where the type shows one, the check-in QR. The
delivered message SHALL contain no attachment parts and no inline
(`Content-ID`) image parts. It SHALL consist of a `text/plain` and a
`text/html` alternative only. WHEN the base URL is not configured, the
system SHALL log a `WARNING` once per process and fall back as follows:
the header shows a styled "Guestify" text wordmark (no image) with
"Gu" in the brand teal and "estify" in white, and the QR
is embedded as an inline `cid:` part, so the pass is never lost. The
tracking ID SHALL always appear as text under the QR, so a reader whose
client blocks remote images can still check in.

#### Scenario: Confirmation email has no attachment strip
- **WHEN** a confirmation email is delivered with the base URL configured
- **THEN** the message has zero attachments and zero inline parts, and its
  HTML contains `<img>` tags whose `src` values start with the configured
  base URL, for both the logo and the QR

#### Scenario: Verification-code email carries no image parts
- **WHEN** a verification-code email is delivered with the base URL
  configured
- **THEN** the message has zero attachments and zero inline parts, and the
  header logo is an absolute URL image

#### Scenario: Unconfigured base URL still delivers a usable pass
- **WHEN** a confirmation email is rendered with no base URL configured
- **THEN** the header shows the text wordmark "Guestify", the QR is an
  inline `cid:` image, and a `WARNING` naming the missing setting is logged
