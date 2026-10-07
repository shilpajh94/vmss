## Context

Current state, after `redesign-notification-email-templates`:
- `core/email_rendering.py::render_email(name, ctx) -> RenderedEmail(subject, html, text)`
  renders `<name>.html`/`.txt` pairs. `heading` is a block and is also the
  subject.
- `_macros.html` holds `lead`, `detail_table`, `qr_pass`, `callout` and
  `note`, all hard-coded to teal.
- `core/emailing.py::build_message` supports `inline_images` as
  `multipart/related`.
- `invitations/tasks.py::_invitation_email_context` builds the shared
  context. Its `location` is only `Branch.name`, and the front desk is the
  Company phone/email.
- `identity_verification/senders.py` has its **own** `SmtpEmailSender`
  (plain text only, no html/inline). `reports/tasks.py` uses
  `core/emailing.email_sender` with plain text only.
- `InvitationRepository.get_location(branch_id, department_id)` already
  resolves `(Branch, Department | None, Building | None)` in one joined
  query.
- `InvitationRepository.get_qr_code(invitation_id)` returns the persisted
  `qr_token`.
- The reference screenshots in `assets/` came from an earlier prototype
  run. Their confirmation mail had an empty "Visit details" section, which
  is the gap the reviewer saw.

## Goals / Non-Goals

**Goals:**
- One `tone` variable drives every colour decision. No template picks hex
  values itself.
- Every email, including the OTP and snapshot emails, goes through
  `render_email` and `build_message`, so branding, the logo and the From
  name are identical everywhere.
- "Where and who" data is resolved from the org chart, not from whatever
  free text happened to be typed.

**Non-Goals:**
- Merging `identity_verification/senders.py`'s SMS/WhatsApp senders into
  `core`. Only its email sender switches to the core one.
- A dark-mode palette, localisation, or per-tenant colour overrides.

## Decisions

### 1. Tone palette as data, passed into the base layout

*As built:* the tone per email type lives in Python
(`email_rendering.TEMPLATE_TONES`) rather than in a `{% set tone %}` in
each child template. A child template's top-level `set` doesn't reliably
reach the parent layout or macros imported `with context`, while a
Python-side injection of `tone` and `t` reaches every template.

`core/email_rendering.py` defines `TONES: dict[str, Tone]`, where `Tone`
holds `pill_bg`, `pill_fg`, `accent`, `tint_bg`, `tint_border` and
`heading_fg`. Values:
- `success`: pill `#dcfce7`/`#166534`, accent `#16a34a`, tint `#f0fdf4`.
- `pending`: `#fef3c7`/`#b45309`, accent `#d97706`, tint `#fffbeb`.
- `danger`: `#fee2e2`/`#b91c1c`, accent `#ef4444`, tint `#fef2f2`.
- `info`: `#dbeafe`/`#1d4ed8`, accent `#3b82f6`, tint `#eff6ff`.
- `brand`: `#ecfeff`/`#0b8b84`, accent `#0b8b84`, tint `#ecfeff`.

Each type template sets `{% set tone = "danger" %}`, and `render_email`
injects `t = TONES[tone]`, which the base layout and macros read. AA
contrast is checked once in a unit test over the table (pill text on pill
background, callout title on tint). The alternative, per-template CSS
classes, was rejected because most clients strip `<style>` classes, so
colours must be inline.

### 2. New macros matching the references
- `highlight_box(label, value, mono=True)`: a dashed-border tint box, used
  for the tracking ID and the OTP code.
- `timeline(steps)`, where each step is `(title, detail, state)` and state
  is `done` (✓ filled), `current` (filled number) or `todo` (outlined
  number). It's table-based so Outlook renders it.
- `checklist(items)`: ✓-prefixed rows.
- `section(title)`: a bold section heading such as "Visit details" or
  "What happens next".
- `callout(title, body, tone)`: the existing callout, now tone-coloured.
- `detail_table` is unchanged, and still skips empty values.
- `visit_details(ctx)`: one macro renders the standard "Visit details"
  rows, so every type shows the same place-of-visit formatting.

The monospace font stack is `'SFMono-Regular', Menlo, Consolas, 'Courier
New', monospace`.

### 3. Place of visit and contacts come from `get_location`
`_invitation_email_context` calls `InvitationRepository(session).get_location(branch_id=…, department_id=…)`
once. It then builds:
- `place = " · ".join(filter(None, [building.name, branch.name, address]))`,
  where `address` is `", ".join(filter(None, [branch.address, branch.city]))`;
- `department = department.name if department else invitation.department_to_visit`;
- `front_desk_contact = branch.contact_phone or branch.contact_email or company.phone or company.email`.

The POC block uses, in priority order: the invitation POC (`poc_name` plus
the `poc_user` phone or email), then the resolved host (name plus phone or
email), then the front desk. This replaces the separate
`BranchRepository.get` call. It's still one query per dispatch, and it
runs before the recipient loop in the submission fan-out.

### 4. QR: inline only, shared helper for confirmation and reschedule
A helper `_qr_inline_image(qr_token) -> InlineImage` wraps
`generate_qr_png`. `_send_approval_notification` stops passing
`attachment=`.

`_send_reschedule_notification` does this when `invitation.status ==
"approved"`:
1. `qr = await InvitationRepository(session).get_qr_code(invitation.id)`.
2. When found, it adds the inline image and `qr_cid` to the context.

The template shows the pass block when `qr_cid` is set, and otherwise the
"pass follows approval" note. An approved invitation with a missing QR row
isn't expected, but the email then falls back to the note and logs
`reschedule_notification_qr_missing` at `WARNING`.

The task's enqueue signature is unchanged. The token is read from the DB
inside the task, which is idempotent and needs no new argument.

### 5. Logo: generated PNG assets, embedded by CID
`assets/visimio-logo-source.png` (2172×724 RGBA, transparent) has a cyan
mark and dark `#0E1527` lettering, which would be invisible on the navy
header. A one-off script, `scripts/build_brand_assets.py` (Pillow, which
is already a dependency), writes
`core/email_assets/visimio-logo-on-dark.png`. The script:
- trims the transparent margins;
- recolours pixels whose RGB is near `#0E1527` to white while keeping
  their alpha, so the cyan mark is untouched;
- downsizes to 2× the display height (64px tall for a 32px `<img>`),
  keeping the file under 15 KB.

The generated PNG is committed, and the script is kept for re-generation.

`build_message` gains `brand_logo: bool` (default True whenever
`html_body` is set). It attaches that PNG as a related part with CID
`visimio-logo@vmss`, and `base.html` references it unless `logo_url` (the
tenant logo) is set.

The alternatives were rejected:
- An externally hosted logo URL: there's no public asset host yet, and
  it would be blocked by "load remote images".
- SVG: unsupported in Gmail and Outlook.

The web change (`VMMS_WEB` `rebrand-to-visimio`) generates its assets
from the same source.

### 6. OTP email renders the template; its sender builds via `build_message`
`identity_verification/service.py::request_otp` renders `verification_code`
with `{code, minutes}`. The code is passed in the render context only.
It's never logged, and a `TemplateRenderError` falls back to today's
one-line body, whose log line records the template name only. SMS and
WhatsApp keep the one-line body.

*As built:* `identity_verification/senders.py::SmtpEmailSender` is **kept**
rather than replaced by the core sender. It now builds its message with
`core/emailing.build_message`, which gives it the From name, the
`multipart/alternative` structure and the inline logo, and its `send`
gains `html_body`. The original plan was to re-export the core sender.
That was dropped because this flow depends on the sender raising
`EmailDispatchError`, which is never cached as an idempotent response, and
on masked-identifier logging. The core sender does neither.

### 7. Snapshot email
`reports/tasks.py` renders `daily_snapshot` with the `CrossBranchRollupOut`
model's fields, keeping `_render_snapshot_body` as the `.txt` template's
logic. The subject date comes from `visit_datetime(today)`.

### 8. Brand strings and From name
- New setting `smtp_from_name: str = "Visimio"` (`SMTP_FROM_NAME`).
  `build_message` sets `From` to
  `formataddr((settings.smtp_from_name, settings.smtp_from_address))`.
- `app_name` default becomes "Visimio API". `.env.example` is updated.
- A test asserts that no template file contains "VisitorPass".
- `base.html`'s footer takes `current_year` from `render_email`, which
  injects `datetime.now(UTC).year`.

## Risks / Trade-offs

- [Removing the attachment makes the QR unavailable when a client blocks
  images] → CID images are shown by default in Gmail, Outlook and Apple
  Mail, since they're not "remote". The plain text and pass block both
  give the tracking ID, which reception can look up. Accepted as the
  product decision.
- [The logo on every email adds ~10–15 KB] → Negligible. It's sent as one
  related part.
- [The recolour script misclassifies antialiased edge pixels] → The
  threshold is on distance to `#0E1527`, keeping alpha. The output is
  visually reviewed in Mailpit (tasks) and committed, so it never runs at
  request time.
- [MODIFIED requirements depend on the unarchived
  `redesign-notification-email-templates`] → Archive that change first.
  The proposal records the dependency.

## Migration Plan

Code and assets only: deploy the API and restart the Celery workers. Set
`SMTP_FROM_NAME` if something other than "Visimio" is wanted. Rollback is
a revert.

## Open Questions

- If the brand owner has a vector (SVG) logo, regenerate both PNGs from it
  for crisper edges. Swapping the source file doesn't change the approach.
