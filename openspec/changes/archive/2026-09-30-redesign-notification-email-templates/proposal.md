## Why

The notification emails still use the first-cut layout (bright-blue header,
bare key/value rows, one-line copy such as "You've been named host of an
invitation") and don't match the VisitorPass product styling the web portal
uses. The visit-confirmation email only ships its check-in QR as a `.png`
attachment, so on most phone mail clients the visitor has to open or
download the attachment before the gate can scan it. A design mock of the
target look also shows a real content defect. The greeting interpolates the
recipient's stored `full_name` as-is, and for some users (e.g.
SSO-provisioned ones whose IdP sent no `name` claim) that is an opaque
identifier, which produced "Hi ccbb9a1e3047…".

## What Changes

- Replace `core/email_templates/base.html` with the VisitorPass layout from
  the approved mock. It has a navy (`#0f172a`) header with the wordmark or
  tenant logo, a cyan accent rule, a white card with a status "eyebrow"
  pill, a heading, a greeting, lead copy, a bordered detail table with
  zebra rows, a next-steps paragraph, and a muted footer ("Sent by
  {company}", "automated message, please don't reply", "Powered by
  VisitorPass"). It stays table-based with inline styles and is
  mobile-friendly: a 600px max width, fluid below that.
- Rewrite all 8 notification templates with accurate, type-specific copy:
  eyebrow, heading, greeting, lead sentence, detail rows, and next-step
  guidance. The templates are visit confirmation, tracking-only
  (received), denial, reschedule, edit, submission-to-role (triage), host
  assigned, and POC assigned. Each detail row renders only when its value
  exists.
- Embed the check-in QR code **inline in the body** of the visit-confirmation
  email, in its own "Your check-in pass" block. The block shows the QR at a
  scannable size, the tracking ID under it, and a "show this at the
  entrance" instruction. The image is referenced through a `cid:` inline
  image part so it renders without remote-image loading. The existing
  `visit-qr.png` attachment is kept as a download/print fallback.
- Personalise every greeting with a real display name, and fall back to a
  neutral greeting ("Hello,") when no trustworthy name exists. That covers a
  blank name, a name equal to the email, or an opaque identifier-looking
  value.
- Format dates and times for humans, e.g. "Wed, 14 Oct 2026 · 10:30 AM",
  instead of the raw ISO `date`/`time` values templates print today.
- Rewrite the plain-text fallback bodies so they carry the same information
  as the HTML versions (today several omit the date or next steps).
- Extend the `EmailSender` interface so a caller can pass inline
  (`cid:`-referenced) images. This is additive: existing `attachment=`
  call sites are unchanged.

Out of scope: OTP emails (`identity_verification/senders.py`) and the
scheduled report email (`reports/tasks.py`), which are plain-text and have
separate owners. SMS copy is also out of scope. The rule that
reschedule/edit emails carry no QR code is unchanged; those emails now tell
the visitor their existing pass is still valid.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `email-notifications`: The branded-layout requirement now specifies the
  VisitorPass layout structure, per-type content, the greeting-name
  fallback, human-readable date/time formatting, and parity between the
  plain-text and HTML versions. It adds the requirement that inline
  images be supported through the sender interface.
- `invitations`: The approval/confirmation email embeds the QR inline in a
  dedicated scannable block, and still attaches the PNG. Reschedule and edit
  emails of an already-approved invitation state that the existing QR stays
  valid.

## Impact

- `src/vmss_api/core/email_templates/*.html`: all 9 files rewritten.
- `src/vmss_api/core/email_rendering.py`: registers the date/time and
  greeting-name Jinja filters.
- `src/vmss_api/core/emailing.py`: `EmailSender.send` gains an optional
  `inline_images` parameter, and `SmtpEmailSender` builds a
  `multipart/related` HTML part.
- `src/vmss_api/invitations/tasks.py`: builds the richer context (recipient
  name, visitor name, branch/building, `is_approved`), passes the QR as an
  inline image, and rewrites the plain-text bodies.
- `src/vmss_api/invitations/notifications.py`: re-exports the inline-image
  helper.
- Tests: `invitations` notification-task tests, the mail-catcher
  integration test (asserts the inline `Content-ID` part), and new
  rendering tests per template.
- No DB migration, no API contract change, and no new dependency (Jinja2
  and the stdlib `email` package are already used).
