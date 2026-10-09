## MODIFIED Requirements

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

## ADDED Requirements

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
