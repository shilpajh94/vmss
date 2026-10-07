## Why

A review of the emails from `redesign-notification-email-templates` in
Mailpit found five problems:
- The verification-code email and the daily snapshot email are still bare
  plain-text one-liners.
- The confirmation email doesn't reliably show the visit's date and time,
  where to go, or who to contact. Location is only the branch name, and the
  building, address and point of contact are missing.
- Every email uses the same neutral teal styling, so a declined visit looks
  just like a confirmed one.
- The confirmation email sends the QR twice, inline and again as an
  attachment.
- A rescheduled visit's email has no QR at all.

The product is also being renamed from **VisitorPass** to **Visimio**,
with a new logo. The emails still say VisitorPass and show the old text
wordmark.

Reference designs are the screenshots in `assets/` (`ref-otp.png`,
`ref-received.png`, `ref-not-approved.png`) and the new logo
(`assets/visimio-logo-source.png`).

**Depends on:** `redesign-notification-email-templates` being archived
first. This change modifies requirements that change adds.

## What Changes

- **Status-themed emails.** Each email gets a tone that colours its status
  pill, accent callout and key highlights:
  - success (green) for confirmed;
  - pending (amber) for received / awaiting approval and for action needed
    on staff triage;
  - danger (red) for not approved;
  - info (blue) for rescheduled and details updated;
  - brand (teal) for host / point-of-contact assignment and the
    verification code.
- **Richer, reference-matched layouts:**
  - **Confirmed:** tracking-ID highlight box; visit details (date and
    time, place of visit as building · branch · address, department,
    duration, purpose); a point-of-contact block with name and phone/email;
    the inline QR pass; a "Before you arrive" checklist; and a "Need to
    change your plans?" callout with the branch front-desk contact.
  - **Received:** amber "Pending approval" pill; tracking-ID box; a
    three-step "What happens next" timeline (submitted ✓ → under review →
    confirmation); and request details.
  - **Not approved:** red pill; red "Reason given" callout; a "What you
    can do" checklist; and a tracking-ID follow-up line.
  - **Rescheduled:** blue pill; previous → new date and time; full visit
    details; and, for an approved visit, the **inline QR pass**.
  - **Details updated, host assigned, POC assigned, triage:** the same
    detail set (including place of visit), each in its own tone.
- **Verification-code email** gets a proper template: heading, lead, a
  dashed code box in a monospace font, an expiry line ("expires in **5
  minutes** and can only be used once"), and a "Keep it private" callout.
  This is the one template allowed to contain the OTP.
- **Daily snapshot email** gets a proper template: a per-branch table of
  the same figures the plain-text version carries.
- **QR is inline only.** The `visit-qr.png` **attachment is removed**
  from the confirmation email, and the rescheduled email of an approved
  visit now embeds the same QR inline. The plain text says "open this
  email with images enabled to see your QR" rather than "attached".
  **BREAKING** (email contents): recipients no longer get a file
  attachment. Mail clients that block images show the tracking-ID fallback
  instead.
- **Visimio branding:**
  - The header shows the Visimio logo (mark plus white wordmark),
    embedded inline via `cid:`.
  - The footer reads "Sent by {company}" and "Powered by Visimio", with
    "© {year} Visimio".
  - The sender display name is "Visimio", configurable.
  - The API's default `app_name` / OpenAPI title becomes "Visimio API".
  - A tenant's own Company logo still replaces the header logo when one is
    configured.

Out of scope: SMS/WhatsApp copy, which stays as short one-liners. Internal
identifiers (`vmss_api` package, `vmss:` Redis keys, DB/schema names) are
not renamed.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `email-notifications`: The layout requirement adds status tones, the
  Visimio brand and the per-type section structure. The per-type content
  table is replaced with the richer set, including the place of visit and
  point of contact. The PII rule gains the verification-code exception.
  The requirement to use a branded template now covers the OTP and
  snapshot emails.
- `invitations`: The confirmation email's QR block drops the attachment.
  The reschedule notification embeds the inline QR for an approved visit,
  reversing "no QR on reschedule". The mail-catcher verification asserts
  inline-only.
- `identity-verification`: The emailed code is rendered from the branded
  verification template, with a plain-text part.
- `reports`: The scheduled snapshot email is rendered from a branded
  template, with a plain-text part.

## Impact

- `src/vmss_api/core/email_templates/`: base layout (tones, logo,
  footer), macros (highlight box, timeline, checklist, tone callout), all 8
  invitation templates rewritten, plus new `verification_code.*` and
  `daily_snapshot.*`. New static asset `core/email_assets/visimio-logo-email.png`,
  generated from the source logo.
- `src/vmss_api/core/emailing.py`: every templated send attaches the logo
  as an inline image. `From` carries a display name
  (`SMTP_FROM_NAME`, default "Visimio").
- `src/vmss_api/invitations/tasks.py`: location via
  `InvitationRepository.get_location` (building, branch, address);
  POC/host contact; branch front-desk contact; QR inline for confirmation
  and approved reschedule; no attachment.
- `src/vmss_api/identity_verification/{service,senders}.py`: render the
  template. The sender gains `html_body` and `inline_images`.
- `src/vmss_api/reports/tasks.py`: render the snapshot template.
- `src/vmss_api/core/config.py`, `.env.example`: `SMTP_FROM_NAME`, and
  the `app_name` default.
- Tests: rendering tests per template and tone, the OTP template, the
  snapshot template, Mailpit round trips (no attachment, inline QR on
  confirmation and reschedule, logo CID), and existing subject/text
  assertions.
- Docs: `docs/features/notifications.md`, `invitations.md`, and
  `identity_verification.md` / `reports.md`.
