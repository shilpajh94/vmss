## MODIFIED Requirements

### Requirement: Every Notification Email Is Rendered From a Branded HTML Template
The system SHALL render every outbound notification email from an HTML
template composed of a shared VisitorPass base layout and a
per-notification-type content block. That covers visit confirmation,
tracking-only, denial, reschedule, edit, submission fan-out to the owning
role, host assignment, and point-of-contact assignment. The base layout
SHALL consist of, in order:
- a dark header band carrying the tenant's logo when one is configured,
  otherwise the tenant's company name, otherwise the "VisitorPass"
  wordmark;
- an accent rule under the header;
- a content card with a short uppercase status label ("eyebrow"), a
  heading, a greeting, a lead paragraph, a bordered detail table, and a
  closing next-steps paragraph;
- a footer stating who sent the message and that it is automated and
  must not be replied to, and carrying a "Powered by VisitorPass" mark.

The layout SHALL render legibly both in a desktop mail client (content
capped at 600px wide) and on a phone (content fluid to the viewport width,
with no horizontal scrolling). Each rendered email SHALL also carry a
plain-text fallback part (multipart `text/plain` + `text/html`) for mail
clients that do not render HTML. Templates SHALL NOT interpolate any field
this capability's PII rules classify as sensitive (identity document
numbers, raw OTP codes) directly into the body.

#### Scenario: Approval email renders from the HTML template with a plain-text fallback
- **WHEN** an invitation is approved and its approval email is dispatched
- **THEN** a mail client that renders HTML shows the VisitorPass layout
  (header band, accent rule, eyebrow, heading, detail table, footer), and
  a client that cannot falls back to an equivalent plain-text version
  carrying the same information

#### Scenario: Tenant logo replaces the wordmark when configured
- **WHEN** the tenant's Company profile has a logo URL and any notification
  email is rendered
- **THEN** the header band shows that logo, with the company name as its
  alt text, instead of the text wordmark

#### Scenario: Layout fits a narrow phone screen
- **WHEN** any notification email is opened in a mail client with a viewport
  narrower than 600px
- **THEN** the card, detail table, and any QR block shrink to the viewport
  width, and no content requires horizontal scrolling

#### Scenario: A sensitive field is never interpolated into a template
- **WHEN** any notification email is rendered for an invitation whose
  visitor has an ID-proof number or an OTP was involved in producing it
- **THEN** the rendered email (HTML or plain-text part) contains neither
  value

## ADDED Requirements

### Requirement: Each Notification Type Carries Accurate, Type-Specific Content
Each notification type SHALL render the eyebrow, heading, lead sentence,
detail rows, and next-step guidance defined for it below. A detail row
SHALL be omitted entirely when its value is absent, and SHALL never render
as an empty or "None" value. Copy SHALL name the actual visitor, host, or
tracking ID involved, never a generic placeholder such as "an invitation".

| Type | Recipient | Eyebrow | Heading | Required detail rows | Next step |
|---|---|---|---|---|---|
| Visit confirmation | Primary contact | Visit confirmed | Your visit is confirmed | Tracking ID, date & time, duration, location (branch name), department, purpose | Present the QR pass at the entrance, arrive a few minutes early, and use the point-of-contact box to reach someone |
| Tracking-only | Primary contact | Request received | We've received your visit request | Tracking ID, status "Awaiting approval", requested date & time, purpose | You'll get a check-in QR pass by email once it's approved; track status with the tracking ID |
| Denial | Primary contact | Request declined | Your visit request wasn't approved | Tracking ID, reason | Contact the host or front desk if you believe this is a mistake |
| Reschedule | Primary contact | Visit rescheduled | Your visit has a new date | Tracking ID, previous date & time (when known), new date & time | If approved: your existing QR pass is still valid for the new date |
| Edit | Primary contact | Details updated | Your visit details have changed | Tracking ID and every current visit detail | If approved: your existing QR pass is still valid |
| Submission to role | Each role holder | Action needed | New visit request awaiting triage | Visitor, tracking ID, requested date & time, purpose | Open the portal and search the tracking ID to review and assign it |
| Host assigned | Host | You're the host | You've been named host for a visit | Visitor, tracking ID, date & time, purpose | Be available to receive the visitor; you'll be notified on check-in |
| POC assigned | Point of contact | Point of contact | You're the point of contact for a visit | Visitor, visitor phone/email, tracking ID, date & time, duration, department, purpose | The visitor may reach out to you about logistics |

The email's subject line SHALL match its heading.

#### Scenario: Host-assigned email names the visitor and the next step
- **WHEN** a host-assigned email is rendered for visitor "Meera Krishnan",
  tracking ID `INV-B8490B0B`, and purpose "Interview"
- **THEN** the email's eyebrow is "You're the host", its lead sentence
  states the recipient is now host for Meera Krishnan's visit and will be
  notified on check-in, its detail table lists Visitor, Tracking ID, and
  Purpose, and its closing paragraph tells the host to search tracking ID
  `INV-B8490B0B` in the portal

#### Scenario: An absent value omits its row
- **WHEN** an email is rendered for an invitation with no expected duration
  and no department
- **THEN** the detail table contains no "Duration" or "Department" row,
  and no row shows an empty value or the text "None"

#### Scenario: Subject matches heading
- **WHEN** any notification email is rendered
- **THEN** its subject line equals its rendered heading text

### Requirement: Greetings Use a Trustworthy Display Name or a Neutral Fallback
Every notification email SHALL open with a greeting addressed to the
recipient's display name: the primary contact's full name for
visitor-facing emails, and the user's full name for staff-facing emails.
WHEN that name is blank, is equal to the recipient's email address, or
looks like a machine identifier rather than a person's name, the greeting
SHALL fall back to "Hello," with no name. A machine identifier here means
a value of 16 or more characters with no whitespace, made up only of
hexadecimal digits, hyphens, or base64/URL-safe characters. The same rule
SHALL apply to any other person name that appears in the email copy
(e.g. a visitor or host name), which falls back to a neutral noun such as
"your visitor".

#### Scenario: Opaque identifier stored as a name is not shown
- **WHEN** a host-assigned email is rendered for a host whose stored full
  name is `ccbb9a1e304730e0512d912e18f6ce6591bee85c26e3cdb7b5d4b89a3549bb731a3a`
- **THEN** the greeting reads "Hello," and the identifier appears nowhere
  in the email

#### Scenario: Real name is used
- **WHEN** a visit-confirmation email is rendered for primary contact
  "Meera Krishnan"
- **THEN** the greeting reads "Hi Meera Krishnan,"

### Requirement: Dates and Times Are Rendered in a Human-Readable Form
Visit dates and times in notification emails (HTML and plain-text) SHALL
be rendered as a weekday, day, abbreviated month, and year, followed by a
12-hour time with AM/PM when a time is set. An example is
"Wed, 14 Oct 2026 · 10:30 AM". They SHALL NOT be rendered as raw ISO
values (`2026-10-14`, `10:30:00`). WHEN only a date is set, only the date
part SHALL render.

#### Scenario: Date and time are formatted
- **WHEN** an email is rendered for a visit on 2026-10-14 at 10:30
- **THEN** it shows "Wed, 14 Oct 2026 · 10:30 AM" and does not contain
  "2026-10-14" or "10:30:00"

#### Scenario: Date without time
- **WHEN** an email is rendered for a visit with a date but no time
- **THEN** only "Wed, 14 Oct 2026" is shown

### Requirement: Plain-Text Fallback Carries the Same Information as the HTML Body
The plain-text part of every notification email SHALL contain the same
greeting, lead sentence, detail values, and next-step guidance as its HTML
part, in the same order. It SHALL NOT be a shortened summary.

#### Scenario: Plain text includes date and next steps
- **WHEN** a reschedule email is rendered for an approved invitation
- **THEN** its plain-text part includes the tracking ID, the new
  formatted date and time, and the sentence stating the existing QR pass
  is still valid

### Requirement: The Sender Interface Supports Inline Images
The email-sending interface SHALL accept zero or more inline images, each
with bytes, a MIME type, and a content ID, that the HTML body references
via `cid:<content-id>`. It SHALL deliver them as related parts of the HTML
body so that mail clients display them without loading remote images.
This is additive. A caller passing no inline images SHALL produce the same
message structure as before, and a provider swap SHALL remain possible
without touching templates.

#### Scenario: Inline image is delivered as a related part
- **WHEN** an email is sent with an HTML body referencing `cid:visit-qr` and
  one inline PNG image with content ID `visit-qr`
- **THEN** the delivered message contains a PNG part whose `Content-ID`
  header is `<visit-qr>`, related to the HTML part, and the HTML part's
  image renders without any remote request

#### Scenario: Existing callers are unaffected
- **WHEN** an email is sent with no inline images
- **THEN** the delivered message is a `multipart/alternative` (plus any
  regular attachment) exactly as before this change
