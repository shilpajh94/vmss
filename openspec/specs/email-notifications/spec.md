# email-notifications Specification

## Purpose

Renders every outbound notification email from a branded HTML template
instead of a plain-text f-string, so an invitation-related email (creation,
submission, approval, denial, reschedule, edit, host assignment) reads as a
professional, information-complete message rather than an unstyled one-liner.

## Requirements

### Requirement: Every Notification Email Is Rendered From a Branded HTML Template
The system SHALL render every outbound email from an HTML template
composed of a shared Visimio base layout and a per-type content block.
That covers visit confirmation, tracking-only (received), denial,
reschedule, edit, submission fan-out to the owning role, host assignment,
point-of-contact assignment, the verification-code email, and the daily
snapshot email. The base layout SHALL consist of, in order:
- a dark header band carrying the tenant's logo when one is configured,
  otherwise the Visimio logo (mark plus wordmark legible on the dark band)
  as an inline image with alt text "Visimio";
- an accent rule under the header;
- a content card with, where the type defines one, a short uppercase status
  pill coloured by the email's tone, followed by a heading, an optional
  greeting, and the type's content sections;
- a footer stating who sent the message ("Sent by {company}", defaulting to
  "Visimio") and that it is automated and must not be replied to, a
  "Powered by Visimio" mark, and "© {current year} Visimio".

The layout SHALL render legibly both in a desktop mail client (content
capped at 600px wide) and on a phone (content fluid to the viewport width,
with no horizontal scrolling). Each rendered email SHALL carry a
plain-text fallback part (multipart `text/plain` + `text/html`). No
template SHALL interpolate an identity-document number. The
verification-code template is the only template that SHALL contain a
one-time code, and only the code being delivered to that recipient. The
From header SHALL carry the display name "Visimio" (configurable) in
front of the sender address.

#### Scenario: Approval email renders from the HTML template with a plain-text fallback
- **WHEN** an invitation is approved and its approval email is dispatched
- **THEN** a mail client that renders HTML shows the Visimio layout
  (header with logo, accent rule, status pill, heading, content sections,
  footer), and a client that cannot falls back to an equivalent plain-text
  version carrying the same information

#### Scenario: Visimio branding is shown when the tenant has no logo
- **WHEN** any email is rendered for a tenant whose Company profile has no
  logo URL
- **THEN** the header shows the Visimio logo image with alt text "Visimio",
  the footer reads "Powered by Visimio" and "© {current year} Visimio",
  and the text "VisitorPass" appears nowhere in the email

#### Scenario: Tenant logo replaces the wordmark when configured
- **WHEN** the tenant's Company profile has a logo URL and any email is
  rendered
- **THEN** the header band shows that logo, with the company name as its
  alt text, and the footer still reads "Powered by Visimio"

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

### Requirement: Each Notification Type Carries Accurate, Type-Specific Content
Each notification type SHALL render with the tone, status pill, heading,
and sections defined below. A detail row SHALL be omitted entirely when
its value is absent, and SHALL never render as an empty or "None" value.
A section whose rows are all absent SHALL be omitted with its title. Copy
SHALL name the actual visitor, host, or tracking ID involved, never a
generic placeholder such as "an invitation". The email's subject line
SHALL match its heading.

"Visit details" means these rows: date & time; place of visit, which is
the resolved building, then branch name, then branch address and city,
joined into one line; department; expected duration; and purpose.

| Type | Tone | Pill | Heading | Sections, in order |
|---|---|---|---|---|
| Visit confirmation | success (green) | Confirmed | Your visit is confirmed | Lead; tracking-ID highlight box; Visit details; Your point of contact (name + phone/email — invitation POC, else resolved host, else branch front desk); **check-in QR pass**; "Before you arrive" checklist (arrive ~10 min early, bring photo ID, show QR at reception/gate, keep this email); "Need to change your plans?" callout with the branch front-desk contact |
| Tracking-only (received) | pending (amber) | Pending approval | We've received your visit request | Lead; tracking-ID highlight box; "What happens next" three-step timeline (Request submitted ✓ / Under review — current / Confirmation — QR on approval); "Your request" rows (requested date & time, place of visit, purpose); status-lookup note quoting the tracking ID |
| Denial | danger (red) | Not approved | Your visit request wasn't approved | Lead; red "Reason given" callout (when a reason exists); "What you can do" checklist (contact the front desk — with its contact when known; submit a new request); tracking-ID follow-up line |
| Reschedule | info (blue) | Rescheduled | Your visit has been rescheduled | Lead; previous → new date & time; Visit details; **check-in QR pass** when the invitation is approved, otherwise a note that the pass follows approval; "Can't make the new time?" callout with front-desk contact |
| Edit | info (blue) | Details updated | Your visit details have changed | Lead; Visit details plus point of contact; note that the existing pass stays valid (approved) or follows approval (pending) |
| Submission to role | pending (amber) | Action needed | New visit request awaiting triage | Lead naming the visitor; Visit details plus visitor name; portal next step quoting the tracking ID |
| Host assigned | brand (teal) | You're the host | You've been named host for a visit | Lead naming the visitor; Visit details plus visitor name and visitor contact; portal next step quoting the tracking ID |
| POC assigned | brand (teal) | Point of contact | You're the point of contact for a visit | Lead naming the visitor; Visit details plus visitor name, phone, email; portal next step quoting the tracking ID |
| Verification code | brand (teal) | — (no pill, no greeting) | Your verification code | Lead; dashed code box ("Verification code" label, code in a monospace font); expiry line (expires in N minutes, single use); "Keep it private" callout |
| Daily snapshot | brand (teal) | Daily snapshot | Daily branch rollup — {date} | Tenant-wide totals; one row per branch with the same figures the rollup endpoint returns |

A tone SHALL set the pill's background and text colour, the accent colour
of its callouts and highlight boxes, and any tone-coloured headings. The
text of every tone colour SHALL meet WCAG AA contrast (4.5:1) against its
background.

#### Scenario: Confirmation email shows when, where and who
- **WHEN** a confirmation email is rendered for an approved invitation at
  branch "Technopark Campus" (address "Phase 1, Trivandrum"), department
  "Engineering" in building "Tower A", on 2026-10-14 at 10:30, with POC
  "Priya Nair" (+91 90000 11122)
- **THEN** the email shows "Wed, 14 Oct 2026 · 10:30 AM", a place of visit
  reading "Tower A · Technopark Campus · Phase 1, Trivandrum", department
  "Engineering", and a point-of-contact block naming Priya Nair with her
  phone number

#### Scenario: Declined visit renders in the red theme
- **WHEN** a denial email is rendered with reason "Visitor not on the
  expected list"
- **THEN** its pill reads "Not approved" in the danger tone, the reason
  appears in a red "Reason given" callout, and the email contains a "What
  you can do" checklist and a line quoting the tracking ID

#### Scenario: Received email shows the approval timeline
- **WHEN** a tracking-only email is rendered
- **THEN** its pill reads "Pending approval" in the amber tone, the tracking
  ID sits in a highlight box, and a three-step "What happens next" list
  marks "Request submitted" done and "Under review" as the current step

#### Scenario: An absent value omits its row
- **WHEN** an email is rendered for an invitation with no expected duration,
  no department, and no resolvable building
- **THEN** the details contain no "Duration" or "Department" row, the place
  of visit shows only the branch name and address, and no row shows an
  empty value or the text "None"

#### Scenario: Subject matches heading
- **WHEN** any email is rendered
- **THEN** its subject line equals its rendered heading text

#### Scenario: Host-assigned email names the visitor and the next step
- **WHEN** a host-assigned email is rendered for visitor "Meera Krishnan",
  tracking ID `INV-B8490B0B`, and purpose "Interview"
- **THEN** the email's eyebrow is "You're the host", its lead sentence
  states the recipient is now host for Meera Krishnan's visit and will be
  notified on check-in, its detail table lists Visitor, Tracking ID, and
  Purpose, and its closing paragraph tells the host to search tracking ID
  `INV-B8490B0B` in the portal

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

### Requirement: Front-Desk Contact Comes From the Visit's Branch
Where an email offers a front-desk contact, it SHALL use the invitation
branch's contact phone, falling back to the branch contact email. Where
the branch has neither, it SHALL fall back to the tenant Company's phone,
then the Company email. When none of these exists, it SHALL show the
generic line "Please contact the front desk on arrival." and SHALL NOT
show an empty contact.

#### Scenario: Branch contact preferred over company contact
- **WHEN** a denial email is rendered for an invitation whose branch has
  contact phone "+91 80000 22233", and whose Company has a different phone
- **THEN** the "What you can do" checklist shows "+91 80000 22233"

### Requirement: Email Images Are Referenced by URL, Never Attached or Embedded
WHEN the public email-asset base URL is configured, every email's images
SHALL be referenced by absolute `https://` URLs under that base: the
Visimio header logo and, where the type shows one, the check-in QR. The
delivered message SHALL contain no attachment parts and no inline
(`Content-ID`) image parts. It SHALL consist of a `text/plain` and a
`text/html` alternative only. WHEN the base URL is not configured, the
system SHALL log a `WARNING` once per process and fall back as follows:
the header shows a styled "Visimio" text wordmark (no image), and the QR
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
- **THEN** the header shows the text wordmark "Visimio", the QR is an
  inline `cid:` image, and a `WARNING` naming the missing setting is logged

### Requirement: Visitor Visit Emails Always Name a Point of Contact
The confirmation, reschedule and edit emails SHALL always render a "Your
point of contact" block. It SHALL use the first available of:
1. the invitation's point of contact (name, and phone or email when it is
   a person);
2. the resolved host (display name, and phone or email);
3. the visit branch's contact person (display name, and phone or email);
4. the branch's front-desk contact phone or email, else the Company's
   phone or email, labelled "Front desk";
5. the line "Reception at {branch name}" (or "Reception" when the branch
   is unknown) with no contact detail.

Names SHALL pass the trustworthy-display-name rule. A candidate whose name
is not trustworthy is skipped in favour of the next one.

#### Scenario: No POC or host falls back to the branch contact person
- **WHEN** a confirmation email is rendered for an invitation with no POC
  and no host, at a branch whose contact person is "Anil Menon"
  (+91 90000 55566)
- **THEN** the point-of-contact block names Anil Menon with that phone
  number

#### Scenario: Nothing configured still shows reception
- **WHEN** a confirmation email is rendered for an invitation with no POC,
  no host, a branch "Main Branch" with no contact person or contact
  details, and a Company with no phone or email
- **THEN** the point-of-contact block reads "Reception at Main Branch"

#### Scenario: Invitation POC wins
- **WHEN** the invitation has POC "Priya Nair" and a resolved host
- **THEN** the block names Priya Nair, not the host
