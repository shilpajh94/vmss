## Purpose

Renders every outbound notification email from a branded HTML template
instead of a plain-text f-string, so an invitation-related email (creation,
submission, approval, denial, reschedule, edit, host assignment) reads as a
professional, information-complete message rather than an unstyled one-liner.

## ADDED Requirements

### Requirement: Every Notification Email Is Rendered From a Branded HTML Template
The system SHALL render every outbound notification email — visit
confirmation, tracking-only, approval, denial, reschedule, edit, submission
fan-out to the owning role, and host assignment — from an HTML template
composed of a shared base layout (the VMSS/VMMS product logo, consistent
header/footer, brand color) and a per-notification-type content block, in
place of today's plain-text `f-string` bodies. Each rendered email SHALL
also carry a plain-text fallback part (multipart `text/plain` +
`text/html`), for mail clients that do not render HTML. Templates SHALL NOT
interpolate any field this capability's PII rules classify as sensitive
(identity document numbers, raw OTP codes) directly into the body.

#### Scenario: Approval email renders from the HTML template with a plain-text fallback
- **WHEN** an invitation is approved and its approval email is dispatched
- **THEN** the recipient's mail client capable of rendering HTML shows the
  branded template (logo, styled layout), and a client that cannot falls
  back to an equivalent plain-text version carrying the same information

#### Scenario: A sensitive field is never interpolated into a template
- **WHEN** any notification email is rendered for an invitation whose
  visitor has an ID-proof number or an OTP was involved in producing it
- **THEN** the rendered email (HTML or plain-text part) contains neither
  value

### Requirement: Template Rendering Failure Falls Back to a Minimal Plain-Text Email
WHEN template rendering fails for any reason (e.g. a missing context field),
the system SHALL log the failure at `ERROR` with the notification type and
invitation id, and SHALL fall back to sending a minimal plain-text email
(tracking ID and a generic message directing the recipient to look up their
invitation) rather than failing to send anything at all.

#### Scenario: Rendering failure still results in a deliverable email
- **WHEN** the HTML template for a given notification type fails to render
  for an invitation
- **THEN** the recipient still receives a minimal plain-text email with the
  tracking ID, and the failure is logged at `ERROR` with enough context to
  diagnose which template and invitation were involved

### Requirement: Email Sending Remains Swappable Behind One Interface
Rendering an email from a template SHALL be a step that happens before
handing a fully-composed subject/HTML-body/plain-text-body to the existing
email-sending interface — introducing templates SHALL NOT require the
call sites that trigger notifications (invitation creation, approval,
denial, reschedule, edit, delegation) to change how they invoke email
dispatch, and SHALL NOT require a provider swap to touch template code.

#### Scenario: Provider swap does not require template changes
- **WHEN** the underlying email-sending implementation is swapped for a
  different provider
- **THEN** no notification template or the call sites that trigger emails
  need to change

## Non-Requirements (explicitly out of scope for this change)

- A UI for tenants to customize their own email templates — every tenant
  shares the same set of templates for now.
- Localization/translation of email content.
