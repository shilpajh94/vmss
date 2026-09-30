## 0. Prerequisite

- [x] 0.1 Archive `redesign-notification-email-templates` (after its manual checks), so this change's MODIFIED requirements apply on top of it.

## 1. Brand assets and settings

- [x] 1.1 Add `scripts/build_brand_assets.py`. It trims `openspec/changes/refine-email-templates-and-visimio-brand/assets/visimio-logo-source.png`, recolours the `#0E1527` lettering to white while keeping alpha, resizes to 64px tall, and writes `src/vmss_api/core/email_assets/visimio-logo-on-dark.png`. Run it, check the output (<15 KB), and commit the PNG plus a copy of the source under `core/email_assets/`.
- [x] 1.2 Add `smtp_from_name` (`SMTP_FROM_NAME`, default "Visimio") to `core/config.py`, change the `app_name` default to "Visimio API", and add both to `.env.example` with placeholder values.
- [x] 1.3 In `core/emailing.py`, set `From` via `formataddr((smtp_from_name, smtp_from_address))`. Attach the logo PNG as a related part with CID `visimio-logo@vmss` whenever `html_body` is set (a `brand_logo` flag, default True). Extend the MIME unit tests.

## 2. Rendering: tones, macros, base layout

- [x] 2.1 Add the `TONES` table to `core/email_rendering.py` (design.md Decision 1). `render_email` injects the tone palette `t` (from the template's `tone`, default `brand`) and `current_year`. Add a unit test asserting AA contrast (≥4.5:1) for pill text on pill background and callout title on tint, for every tone.
- [x] 2.2 Rewrite `base.html`:
  - header shows `cid:visimio-logo@vmss` (alt "Visimio") unless `logo_url` is set;
  - tone-coloured pill, only when the template defines one;
  - optional greeting (`show_greeting`, default true);
  - footer reads "Sent by {company or Visimio}", then the automated line, then "Powered by Visimio", then "© {year} Visimio".

  Update `base.txt` to match.
- [x] 2.3 In `_macros.html`, add `highlight_box`, `timeline`, `checklist`, `section` and `visit_details`, and make `callout` tone-aware. Add text equivalents in `_macros.txt` (design.md Decision 2).

## 3. Invitation email context and tasks

- [x] 3.1 Rework `_invitation_email_context` to use `InvitationRepository.get_location`. It provides `place` (building · branch · address, city), `department` (catalog name, falling back to free text), `front_desk_contact` (branch phone/email, then company phone/email), and a POC block (invitation POC, then resolved host, then front desk, each with a contact). Remove the separate `BranchRepository.get` call (design.md Decision 3).
- [x] 3.2 `_send_approval_notification`: remove the `visit-qr.png` attachment and send only the inline QR, via a `_qr_inline_image` helper.
- [x] 3.3 `_send_reschedule_notification`: for an `approved` invitation, load the token via `InvitationRepository.get_qr_code`, and embed the inline QR plus `qr_cid`. If the QR row is missing, log `reschedule_notification_qr_missing` at WARNING and render the "pass follows approval" note.
- [x] 3.4 Extend `invitations/tests.py::_FakeSession` to support the `get_location` join and the `get_qr_code` lookup that the task tests use.

## 4. Templates

- [x] 4.1 `visit_confirmation` (success tone), in this order: lead; tracking-ID box; Visit details; point of contact; QR pass; "Before you arrive" checklist; "Need to change your plans?" callout with front desk. The `.txt` says to open with images enabled for the QR, and gives the tracking ID as the fallback.
- [x] 4.2 `tracking_only` (pending tone): "Pending approval" pill; lead; tracking-ID box; three-step "What happens next" timeline; "Your request" rows; status-lookup note (matches `assets/ref-received.png`).
- [x] 4.3 `denial` (danger tone): "Not approved" pill; lead; red "Reason given" callout; "What you can do" checklist with the front-desk contact; tracking-ID follow-up (matches `assets/ref-not-approved.png`).
- [x] 4.4 `reschedule` (info tone): "Rescheduled" pill; previous → new; Visit details; QR pass when `qr_cid` is set, otherwise the pending note; "Can't make the new time?" callout. Heading and subject: "Your visit has been rescheduled".
- [x] 4.5 `edit` (info), `submission_role` (pending, "Action needed"), `host_assigned` (brand, with visitor contact), `poc_assigned` (brand): use `visit_details` and the section structure from the spec table.
- [x] 4.6 New `verification_code.html`/`.txt` (brand tone, no pill, no greeting): lead; code `highlight_box` in monospace; expiry line with bold minutes and "can only be used once"; "Keep it private" callout (matches `assets/ref-otp.png`).
- [x] 4.7 New `daily_snapshot.html`/`.txt`: totals row plus per-branch table, and a "no branches" note.
- [x] 4.8 Replace every remaining "VisitorPass" in templates, docstrings and docs with "Visimio".

## 5. Other senders

- [x] 5.1 `identity_verification`: make `senders.email_sender` the core `SmtpEmailSender`, and have `service.request_otp` render `verification_code`. It falls back to the one-line body on `TemplateRenderError` and logs the template name only, never the code. SMS and WhatsApp are unchanged (design.md Decision 6).
- [x] 5.2 `reports/tasks.py`: render `daily_snapshot` per admin (greeting by display name) with the new subject. Idempotency and recipients are unchanged.

## 6. Tests and docs

- [x] 6.1 Update `tests/test_email_notifications.py`:
  - per-type pill, tone and heading = subject;
  - confirmation "when/where/who" scenario (place string, POC contact);
  - denial red callout and checklist;
  - received timeline states;
  - omitted rows and sections;
  - no "VisitorPass" anywhere;
  - `© {year} Visimio`;
  - logo `cid` present unless `logo_url` is set;
  - verification-code content;
  - snapshot table and no-branches note.
- [x] 6.2 Update `invitations/tests.py`:
  - approval-task tests assert no `attachment` kwarg and one inline QR;
  - reschedule-task tests cover approved (inline QR from `get_qr_code`), pending (no QR) and missing QR row (WARNING plus note);
  - fix the subject/text assertions.
- [x] 6.3 Mailpit round trips:
  - confirmation: zero attachments, inline QR `Content-ID` referenced in the pass block, logo CID present, From display name "Visimio";
  - new: an approved reschedule carries the same inline QR bytes as confirmation.
- [x] 6.4 Identity-verification tests: email OTP renders the template (code in the HTML and text, expiry minutes), the fallback on render failure, and no code in logs. Reports tests: the snapshot email carries html plus text with matching figures.
- [ ] 6.5 Render every template to the scratchpad and review in Mailpit's HTML view and HTML Check against `assets/ref-*.png`, at ≤600px and at desktop width.
- [x] 6.6 Update `docs/features/notifications.md` (tones, section table, logo, QR inline-only), `invitations.md` (no attachment, reschedule QR), `identity_verification.md` (templated email) and `reports.md` (templated snapshot).
- [ ] 6.7 Run `ruff check`, `ruff format --check`, `mypy` on `core/`, and `ddev exec uv run pytest` (single process). Compare any failures against the known pre-existing set before calling them regressions.
