## 1. Sender: inline image support

- [x] 1.1 In `core/emailing.py`, add an `InlineImage` protocol + `make_inline_image(content, mime_type, cid)`, and add `inline_images: Sequence[InlineImage] = ()` to `EmailSender.send` and `SmtpEmailSender.send`. Attach each image to the HTML part via `add_related(..., cid=f"<{cid}>", disposition="inline")` (design.md Decision 4). Ignore inline images when `html_body` is `None`.
- [x] 1.2 Re-export `InlineImage`/`make_inline_image` from `invitations/notifications.py`, and update the recording fake sender(s) used in tests to accept and record `inline_images`.
- [x] 1.3 Add unit tests building the `EmailMessage` both with and without an inline image. Assert the `multipart/related` structure, the `Content-ID: <visit-qr@vmss>` header, and that the message is unchanged when no images are passed.

## 2. Rendering: filters, text templates, single render call

- [x] 2.1 In `core/email_rendering.py`, add the `display_name` and `visit_datetime` filters (design.md Decision 6) with a locale-independent English day/month table, and register them on the HTML environment and on a new `autoescape=False` text environment.
- [x] 2.2 Add `render_email(template_name, context) -> RenderedEmail(subject, html, text)` that renders `<name>.html` (subject block + body) and `<name>.txt`, raising `TemplateRenderError` on any failure. Keep `render_email_html` as a thin wrapper only if something outside `invitations/tasks.py` still calls it; otherwise remove it.
- [x] 2.3 Unit tests for the filters: the hex/opaque id → `None`, a name equal to the email → `None`, blank → `None`, a real name → unchanged; date+time → `"Wed, 14 Oct 2026 · 10:30 AM"`, date-only, and `None` → `None`.

## 3. Templates

- [x] 3.1 Rewrite `base.html` to the VisitorPass layout: the navy header with logo / company name / "VisitorPass" wordmark, the `#06b6d4` accent rule, a 600px fluid card, the eyebrow + `<h1>` from a `heading` variable, a greeting, the content block, and a footer with "Sent by {company}", the automated-message line, and "Powered by VisitorPass". Use tables + inline styles plus a single `<style>` block with only the `@media (max-width:620px)` override and the font import (design.md Decision 1).
- [x] 3.2 Add `_macros.html` with `eyebrow`, `detail_table(rows)` (skips `None`/empty values), `qr_pass(cid, tracking_id)` (white bgcolor cell, ≥180px image, `max-width:100%`, tracking ID under it, the "show this at the entrance or kiosk" line), and `note`.
- [x] 3.3 Add `base.txt` (greeting, body block, footer lines) for the plain-text parts.
- [x] 3.4 Rewrite `visit_confirmation.html`/`.txt` per the spec table. Put the `qr_pass` block after the lead and before the details, followed by the POC/host/front-desk contact box. The text part says the QR is attached.
- [x] 3.5 Rewrite `tracking_only`, `denial`, `reschedule` (previous → new date, approved vs pending pass sentence), and `edit` (approved vs pending pass sentence) `.html`/`.txt`.
- [x] 3.6 Rewrite `submission_role`, `host_assigned`, and `poc_assigned` `.html`/`.txt`, matching the mock's host copy ("You're now the host for {visitor}'s visit…", "search for tracking ID …").
- [x] 3.7 In every template, set `heading` once and use it for both the subject block and the `<h1>` (design.md Decision 8).

## 4. Task wiring (`invitations/tasks.py`)

- [x] 4.1 Add `_invitation_email_context(session, invitation, *, recipient_name, recipient_email)`. It builds branding, tracking ID, visitor name, purpose, date/time, previous date/time, duration, department, branch name (one `BranchRepository(session).get(invitation.branch_id)`), and `is_approved`.
- [x] 4.2 Switch all 8 tasks to `render_email(...)`. Use the rendered subject/text, and on `TemplateRenderError` send `_fallback_text(invitation)` (tracking ID + generic look-up message) with no HTML, logging at `ERROR` as today.
- [x] 4.3 In `_send_approval_notification`, generate the QR PNG once. Pass it as `make_inline_image(qr_png, "image/png", "visit-qr@vmss")` and still as the `visit-qr.png` attachment. Put `qr_cid` in the context. Thread `inline_images` through `_dispatch`, where the SMS path ignores it.
- [x] 4.4 In the submission fan-out, build the shared context once before the loop and render per recipient with that recipient's name. No queries inside the loop.
- [x] 4.5 Pass the recipient's display name: the primary contact's full name for visitor emails, and `host`/`poc`/role-user `full_name` + `email` for staff emails.

## 5. Tests and docs

- [x] 5.1 Update the existing notification-task tests in `invitations/tests.py` (host, POC, edit, approval) for the new subjects/copy. Assert on key content, not full HTML.
- [x] 5.2 Add per-template rendering tests: each type's eyebrow/heading/subject equality, omitted empty rows (no "None"), the opaque-id greeting fallback (the exact hex from the mock), human-readable dates, and plain-text parity (tracking ID, date, next-step sentence present in text).
- [x] 5.3 Add a test that only `visit_confirmation` contains the `cid:` QR block, and that the reschedule/edit copy switches on `is_approved`.
- [x] 5.4 Extend `test_send_approval_notification_delivers_email_with_qr_via_mailpit` to assert the inline PNG part's `Content-ID`, the HTML `<img src="cid:visit-qr@vmss">`, and that the inline QR decodes to the persisted token (or equals the attachment bytes).
- [ ] 5.5 Render each template to `scratchpad/*.html` and check it at 375px and 600px+ widths (and in Mailpit's HTML view) against the mock. Record any client-specific quirk in `docs/features/notifications.md`.
- [x] 5.6 Update `docs/features/notifications.md` (and the email section of `docs/features/invitations.md`) with the layout, the per-type content table, the inline QR, and the name/date rules.
- [ ] 5.7 Run `ruff check`, `ruff format --check`, `mypy` on `core/`, and `ddev exec uv run pytest` (single process, see the concurrent-pytest note) until all are green.
