## ADDED Requirements

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
