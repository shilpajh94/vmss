## Why

Two problems remain after `refine-email-templates-and-visimio-brand`:

1. **Images show up as attachments.** The Visimio logo and the check-in QR
   are embedded as `cid:` inline parts. Mailpit, and Outlook desktop, list
   every such part in an attachment strip below the message
   (`assets/ref-otp-attachment-strip.png`,
   `assets/ref-reschedule-attachment-strip.png`: `visimio-logo@vmss`,
   `visit-qr@vmss`). The product owner doesn't want any attachment on these
   emails.
2. **The confirmed email often has no point of contact.** The contact
   block falls back from invitation POC → resolved host → front desk, and
   is omitted when none of those exist. That's the common case in real
   data: the dev tenant's only approved invitation has no POC and no host,
   and neither branch has a contact phone or email. The Mailpit test emails
   the reviewer opened use minimal fake data, so the gap looked universal.

## What Changes

- **Email images load by URL. No inline parts and no attachments.**
  - The header logo becomes a public, cacheable static URL:
    `GET /api/v1/public/email-assets/visimio-logo.png`.
  - The check-in QR becomes a long-lived, HMAC-signed URL:
    `GET /api/v1/public/email-assets/{tenant_id}/qr/{invitation_id}.png?exp=…&sig=…`.
    It's valid until 7 days after the invitation's `expires_at`, and
    serves the same persisted QR the check-in flow uses.
  - Emails use absolute `https://` `<img src>` URLs built from a new
    `EMAIL_ASSET_BASE_URL` setting, the API's public origin. DDEV sets it
    to `https://vmss-new-api.ddev.site:8443`.
  - When the setting is unset, the header falls back to a styled
    "Visimio" text wordmark, and the QR falls back to an inline `cid:`
    part so it's never lost. This is logged at `WARNING`.
  - **BREAKING** for mail clients that block remote images by default
    (Outlook desktop, some corporate gateways): the logo and QR appear
    only after the reader chooses "show images". The pass block always
    shows the tracking ID as text, so check-in still works.
- **Point of contact is always shown** on the confirmation, reschedule and
  edit emails, in this order:
  1. the invitation POC;
  2. the resolved host;
  3. **the branch's contact person** (`Branch.contact_person_user_id`),
     with name and phone or email;
  4. the branch or Company front-desk phone or email;
  5. "Reception at {branch name}".
- **Representative test and preview emails:**
  - The Mailpit round-trip tests use realistic fixture data (POC, place,
    front desk).
  - A `scripts/send_email_previews.py` command sends every template with
    full sample data to Mailpit, so reviewers look at complete emails
    rather than minimal test sends.

Out of scope: the `signature_pad` field-type 500 seen on
`GET /form-builder/steps` in the dev tenant. That's stale data from
another branch, and is reported separately.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `email-notifications`: Images are served by URL (no inline or attached
  parts, with a text and inline fallback when unconfigured). The sender's
  inline-image support becomes the fallback path only. The point of
  contact is always present on visitor visit emails.
- `invitations`: The QR in confirmation and reschedule emails is
  referenced via a signed public URL, served by a new rate-limited public
  endpoint. The mail-catcher verification asserts no attachments and no
  inline parts.

## Impact

- New `src/vmss_api/core/email_assets_router.py` (public, rate-limited,
  registered in `api.py`, and added to `_TAGS_METADATA`). New settings
  `EMAIL_ASSET_BASE_URL` and `EMAIL_ASSET_URL_SECRET` (falls back to the
  storage or JWT secret). Updates to `.env.example` and
  `.ddev/config.yaml` `web_environment`.
- `core/email_rendering.py`: injects `logo_src`. `core/emailing.py`: the
  brand-logo CID is attached only in fallback mode.
  `invitations/tasks.py`: builds `qr_src` and the extended contact chain.
  Templates `base.html` and `_macros.html::qr_pass` take URLs.
- Tests: rendering (absolute URLs, no `cid:` when configured, fallback when
  not), endpoint (signature, expiry, tenant, wrong invitation, rate limit),
  Mailpit (zero attachments, zero inline parts), and the contact chain.
- Docs: `notifications.md`, `invitations.md`, and a new endpoint row in
  `invitations.md`'s table.
