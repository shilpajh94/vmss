## Context

- Rendering: `core/email_rendering.py::render_email_html` loads
  `core/email_templates/<name>.html` (each one `{% extends "base.html" %}`
  with `subject` + `content` blocks) and returns `(subject, html)`. The
  Celery tasks in `invitations/tasks.py` build the plain-text `body` by
  hand next to it, and pass the render's subject to nothing: each task
  hardcodes its own subject string.
- Sending: `core/emailing.py::SmtpEmailSender.send(to, subject, body,
  html_body, attachment)` builds an `EmailMessage` with `set_content` and
  `add_alternative`, plus one optional `add_attachment`. There is no
  inline-image support.
- QR: `invitations/qr.py::generate_qr_png(token)` produces the PNG, and
  only `_send_approval_notification` attaches it.
- Design reference: the mock in the proposal, with the web portal's
  `design-theme` tokens. Primary `#0f172a`, secondary accent `#06b6d4`,
  admin accent `#0b8b84`, text muted `#64748b`, border `#e2e8f0`, subtle
  surface `#f8fafc`, Outfit (display) and Geist (body) fonts.
- `Invitation` has `branch_id` but no building. `department_to_visit` is a
  snapshotted string. `previous_preferred_visit_date/time` exist for
  reschedule.

## Goals / Non-Goals

**Goals:**
- One layout, with every type-specific decision (eyebrow, heading, copy,
  rows) living in that type's template. There are no `if type == …`
  branches in `base.html`.
- The subject, HTML, and plain text come from one source, so they can't
  drift.
- Inline QR that works in Gmail (web and app), Outlook desktop and web,
  and Apple Mail.

**Non-Goals:**
- A dark-mode-specific palette (mail clients' forced dark mode is only
  guarded against for QR legibility, see Risks).
- Localisation or per-tenant copy overrides.
- Changing when any notification fires, or its recipient or channel.

## Decisions

### 1. Email-safe markup: tables + inline styles + one `<style>` block
The layout uses nested `role="presentation"` tables with inline styles,
because Outlook's Word engine ignores flexbox/grid and most `<style>`
rules. A single `<style>` block in `<head>` carries only progressive
enhancements. These are a `@media (max-width:620px)` rule that sets the
card to `width:100% !important` and reduces padding, the web-font
`@import` for Outfit/Geist, and a `color-scheme: light` hint. The fallback
stack is `'Outfit', 'Segoe UI', Arial, sans-serif` (headings) and
`'Geist', 'Segoe UI', Arial, sans-serif` (body), so clients without web
fonts still look close. The card is `width="600"` plus
`style="max-width:600px;width:100%"`, which makes it fluid on phones even
where media queries are stripped (Gmail app).

*Alternative:* MJML or a CSS inliner (premailer). Rejected for now: it adds
a build step or dependency for 9 small templates. Revisit if the template
count grows.

### 2. Reusable Jinja macros instead of per-template markup
Add `core/email_templates/_macros.html` with `eyebrow(text)`,
`detail_table(rows)`, where `rows` is a list of `(label, value)` pairs and
`None`/empty values are skipped inside the macro, `qr_pass(cid,
tracking_id)`, and `note(text)`. Each type template becomes about 15
lines of copy plus macro calls. Skipping empty rows in one place is what
enforces the spec's "no empty/None row" rule for every type.

### 3. Plain text is rendered from a sibling `.txt` template
Each type gets `<name>.txt` next to `<name>.html`, extending `base.txt`.
`render_email(template_name, context) -> RenderedEmail(subject, html,
text)` renders both through the same context and the same filters.
`subject` stays a block in the `.html` template. Tasks stop hand-building
`body`/`subject` strings. The spec's rendering-failure fallback is
unchanged: on `TemplateRenderError` the task sends a minimal hardcoded
plain-text email (tracking ID + generic message) with no HTML. That
minimal text becomes a small `_fallback_text(invitation)` helper in
`tasks.py` rather than the per-task f-strings.

The `.txt` environment uses `autoescape=False`. The `.html` environment
keeps `select_autoescape(["html"])`.

*Alternative:* derive the text from the HTML (html2text). Rejected: it
adds a dependency and produces noisy output from table layouts.

### 4. Inline images via `multipart/related`
`EmailSender.send` gains `inline_images: Sequence[InlineImage] = ()`, where
`InlineImage` has `content: bytes`, `mime_type: str`, and `cid: str`.
`make_inline_image()` sits next to `make_attachment()`. In
`SmtpEmailSender`, after `add_alternative(html_body, subtype="html")`, it
fetches the HTML part (`message.get_payload()[-1]`) and calls
`html_part.add_related(content, maintype, subtype, cid=f"<{cid}>",
disposition="inline")`. The stdlib then builds
`multipart/mixed → [multipart/alternative → [text/plain,
multipart/related → [text/html, image/png]]], attachment`, which is the
standard structure all target clients render. The CID value is
`visit-qr@vmss`. The domain-style suffix avoids collisions and satisfies
Outlook.

*Alternatives:* a `data:` URI (blocked by Gmail and Outlook), or a hosted
image URL via storage signed links (blocked by default "load remote
images" settings, expires, and makes the pass depend on the storage
tier). Both rejected.

### 5. Keep the PNG attachment
The attachment remains as a fallback for clients that strip related parts
or block inline images, and for printing. It's the same bytes, so the QR
is generated once per dispatch and reused for both parts.

### 6. Name and date filters in the rendering environment
Registered on both Jinja environments:
- `display_name(value, email=None)`. Returns `None` when the value is
  blank, equals the email (case-insensitively), or matches
  `^[A-Za-z0-9_\-+/=]{16,}$` with no whitespace (opaque id, hex digest, or
  base64). Templates render
  `Hi {{ name }},` if the name is set, otherwise `Hello,`. For third-party
  names in copy, `{{ visitor_name | display_name or "your visitor" }}`.
- `visit_datetime(date, time=None)`. Returns `"Wed, 14 Oct 2026 · 10:30
  AM"`, or the date only. It uses `strftime` with no locale dependence:
  day and month names come from a fixed English tuple, so the container
  locale can't change output.

This fixes the "Hi ccbb9a1e…" defect in the mock without touching how
`User.full_name` is populated. Fixing the SSO `name` claim fallback
(`sso/service.py`) is separate, and is noted as an open question.

### 7. Context assembly
One helper, `_invitation_email_context(session, invitation, *,
recipient_name, recipient_email)`, in `tasks.py` builds the shared keys:
branding, tracking ID, visitor name, purpose, date/time, duration,
department, branch name (one `BranchRepository.get` call), `is_approved`,
and the previous date/time. Each task adds only its extras (QR cid, POC
box, denial reason, visitor phone/email). This replaces the near-duplicate
dicts in the 8 tasks. The branch lookup is one extra PK query per
dispatch. It isn't a loop, except in the submission fan-out, where the
context is built once before the recipient loop and only the greeting
name differs per recipient. The body is re-rendered per recipient, which
is cheap string rendering with no queries.

### 8. Subject comes from the template
Tasks use the rendered `subject` from `render_email`. The spec requires
subject = heading, so each `.html` template defines a `{% block heading %}`.
`base.html` renders it in both `<title>` and `<h1>` via
`self.heading()`, and `render_email` renders that block on its own as the
subject. It then passes the unescaped heading to the `.txt` template as
`heading`. A `{% set %}` was the first idea, but a block is what Jinja
reliably exposes to both the parent layout and a standalone render.

### 9. SMS keeps its own short body
`_dispatch` takes a separate required `sms_body` (the pre-existing
one-liners). The full plain-text email, with greeting, detail rows and
footer, would cost several SMS segments, and SMS copy is out of scope.

## Risks / Trade-offs

- [Forced dark mode inverts the QR, which then fails to scan] → The QR
  sits on an explicit white `bgcolor` cell with a 16px padding quiet zone,
  and the PNG itself keeps its white border (`qrcode` default `border=4`).
  Gmail and Outlook's dark mode leave image pixels alone.
- [Inline image stripped by a client] → The PNG attachment is still
  present, and the plain text says "your QR code is attached".
- [Web fonts not loaded (Outlook, Gmail)] → The fallback stack is chosen
  to keep metrics close. The layout doesn't depend on font width.
- [`display_name` false positive on a real single-token name ≥16 chars] →
  Real names rarely hit 16+ characters with no space. The cost of a false
  positive is only a neutral "Hello,", which is acceptable.
- [Existing tests assert hardcoded subjects/bodies] → They're updated in
  the same change. Subjects change text (e.g. "You've been named host" →
  "You've been named host for a visit"). That's not an API contract, but
  it's called out in the tasks so no test is silently deleted.

## Migration Plan

Code-only. Deploy the API and restart the Celery workers, since the
templates load at import. Rollback is a revert: no schema or data
changes, and emails already queued render with whichever template version
the worker has loaded.

## Open Questions

- Should the SSO provisioning path (`sso/service.py`) stop storing a
  non-name value in `full_name` (fall back to the email's local part)?
  This is independent of the email fix above and can be a follow-up
  change.
