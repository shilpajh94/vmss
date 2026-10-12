## ADDED Requirements

### Requirement: Actionable Emails Link Directly to the Relevant Portal Page
WHEN the portal base URL is configured, each email type below SHALL carry
exactly one call-to-action button whose link is an absolute URL under that
base. The button SHALL sit after the type's detail sections and before its
closing tracking-ID note. The plain-text part SHALL carry the same link as
a labelled line ("{label}: {url}") in the same position. The existing
tracking-ID note SHALL remain, because the reader enters that ID on the
page the link opens.

| Type | Recipient | Button label | Link path (appended to the base URL) |
|---|---|---|---|
| Tracking-only (received) | Visitor | Track your request | `/visitor/track` |
| Visit confirmation | Visitor | View your visit | `/visitor/track` |
| Reschedule | Visitor | View your visit | `/visitor/track` |
| Edit | Visitor | View your visit | `/visitor/track` |
| Denial | Visitor | Submit a new request | `/visitor/request` |
| Submission to role | Staff | Review request | `/staff/login` |
| Host assigned | Host | View visit | `/staff/login` |
| POC assigned | Point of contact | View visit | `/staff/login` |

A link SHALL be a fixed page path with no query string or per-invitation
segment. It SHALL NOT carry a tracking ID, invitation id, the visitor's
name, email, phone, ID-proof number, or any one-time code. The
submission-to-role button replaces the former "Open staff portal" button,
which linked to the portal root.

#### Scenario: Received email links to the track page
- **WHEN** a tracking-only email is rendered for tracking ID `INV-B8490B0B`
  with the portal base URL `https://visit.example.com`
- **THEN** the HTML part contains a "Track your request" button linking to
  `https://visit.example.com/visitor/track`, the plain-text part contains
  the line `Track your request: https://visit.example.com/visitor/track`,
  and the email still shows tracking ID `INV-B8490B0B`

#### Scenario: Host email links to the staff login
- **WHEN** a host-assigned email is rendered with the portal base URL
  `https://visit.example.com`
- **THEN** its "View visit" button links to
  `https://visit.example.com/staff/login`, and the email still contains
  the sentence quoting the tracking ID

#### Scenario: Submission email no longer links to the portal root
- **WHEN** a submission-to-role email is rendered with the portal base URL
  configured
- **THEN** it contains a "Review request" button linking to
  `{base}/staff/login`, and no button linking to the bare base URL

#### Scenario: Denial email offers a new request
- **WHEN** a denial email is rendered with the portal base URL configured
- **THEN** it contains a "Submit a new request" button linking to
  `{base}/visitor/request`

#### Scenario: Trailing slash in the base URL does not double up
- **WHEN** the portal base URL is configured as `https://visit.example.com/`
- **THEN** a rendered link reads `https://visit.example.com/visitor/request`,
  not `https://visit.example.com//visitor/request`

#### Scenario: Link never carries personal data
- **WHEN** any email in the table is rendered
- **THEN** no link in it contains the visitor's name, email address, phone
  number, ID-proof number, or any one-time code

### Requirement: Missing Portal URL Omits Links Without Blocking Delivery
The portal base URL SHALL be supplied per environment through deployment
configuration, never hard-coded. It SHALL count as not configured when it
is unset, blank, or not an absolute `http://`/`https://` URL (for example,
a deployment token the pipeline left unreplaced). Only the scheme and host
of the configured value SHALL be used, so a value pointing at a page
(e.g. `https://visit.example.com/staff/login`) yields the same links as the
bare origin. WHEN the portal base URL
is not configured, every email SHALL render
without a call-to-action button and without a link line in its plain-text
part. Otherwise it SHALL render as it did before this requirement. The
email SHALL still be sent. The system SHALL log a `WARNING` naming the
missing setting once per process, not once per email.

#### Scenario: Unconfigured base URL still sends the email
- **WHEN** a visit-confirmation email is dispatched with no portal base URL
  configured
- **THEN** the email is delivered with its QR pass and tracking ID, contains
  no call-to-action button, and a single `WARNING` naming the missing
  setting is logged even if several emails are sent

#### Scenario: A page URL is reduced to its origin
- **WHEN** the portal base URL is configured as
  `https://visit.example.com/staff/login`
- **THEN** a received email links to `https://visit.example.com/visitor/track`
  and a host-assigned email links to `https://visit.example.com/staff/login`

#### Scenario: Unreplaced deployment token sends no broken link
- **WHEN** the portal base URL holds the literal, unreplaced token
  `__STAFF_PORTAL_URL__`
- **THEN** emails are sent without a call-to-action button, and no link
  containing the token is rendered

### Requirement: Verification-Code Email Carries No Links
The verification-code email SHALL NOT contain any hyperlink or URL, in
either its HTML or its plain-text part. The only exception is the header
logo's image source. The recipient requested the code from a page they
already have open, and a code-plus-link email trains recipients to trust
the pattern phishing emails use.

#### Scenario: Code email is link-free even with the portal URL set
- **WHEN** a verification-code email is rendered with the portal base URL
  configured
- **THEN** its HTML contains no `<a href` element and its plain-text part
  contains no `http://` or `https://` URL

## MODIFIED Requirements

### Requirement: Template Rendering Failure Falls Back to a Minimal Plain-Text Email
WHEN template rendering fails for any reason (e.g. a missing context field),
the system SHALL log the failure at `ERROR` with the notification type and
invitation id, and SHALL fall back to sending a minimal plain-text email
(tracking ID and a generic message directing the recipient to look up their
invitation) rather than failing to send anything at all. WHEN the portal
base URL is configured, the fallback email SHALL also include, as a
labelled line, the same link the failed template would have carried
(per "Actionable Emails Link Directly to the Relevant Portal Page").

#### Scenario: Rendering failure still results in a deliverable email
- **WHEN** the HTML template for a given notification type fails to render
  for an invitation
- **THEN** the recipient still receives a minimal plain-text email with the
  tracking ID, and the failure is logged at `ERROR` with enough context to
  diagnose which template and invitation were involved

#### Scenario: Fallback email keeps the link
- **WHEN** a tracking-only email fails to render for tracking ID
  `INV-B8490B0B` with the portal base URL `https://visit.example.com`
- **THEN** the fallback plain-text email contains the tracking ID and
  `https://visit.example.com/visitor/track`
