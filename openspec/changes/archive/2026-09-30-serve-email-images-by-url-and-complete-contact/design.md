## Context

- `core/emailing.py::build_message` attaches `visimio-logo@vmss` as a
  related part whenever the HTML references it. The invitation tasks pass
  the QR as `inline_images` (`visit-qr@vmss`). Mailpit and Outlook desktop
  list both in an attachment strip (see `assets/`).
- `InvitationQRCode` persists `qr_token` and `image_storage_key` (the
  rendered PNG in storage). `core/storage.py` has HMAC-signed local URLs,
  but their TTL is 300 s, which is far too short for an email, and S3 mode
  presigns differently. So email assets need their own signing and route.
- `core/storage_router.py` is the precedent for a public, signature-gated
  file route (`/api/v1/files/local/{key}`).
- `invitations/tasks.py::_resolve_contact` currently falls back from POC
  to host to front desk, then returns nothing. `get_location` already
  returns the `Branch` row, which carries `contact_person_user_id`.
- Dev data: 1 approved invitation with no POC or host, branches with no
  contacts, and the Company phone set.

## Goals / Non-Goals

**Goals:** zero MIME image parts when configured; a QR URL that can't be
enumerated or forged; a contact block on every visitor visit email.

**Non-Goals:** a CDN or asset pipeline; tracking pixels or open analytics,
which this explicitly doesn't add (the QR route logs no reader data beyond
the standard access log); changing SMS.

## Decisions

### 1. One public router for email assets
`core/email_assets_router.py` has prefix `/public/email-assets` and tag
`email-assets` (added to `_TAGS_METADATA`). Routes:
- `GET /visimio-logo.png`: a `FileResponse` of
  `core/email_assets/visimio-logo-on-dark.png`, with `Cache-Control:
  public, max-age=31536000, immutable`. The file name carries the version,
  so renaming the file busts the cache.
- `GET /{tenant_id}/qr/{invitation_id}.png?exp&sig`, rate-limited at
  `60/minute`. It:
  1. verifies the signature, returning 403;
  2. checks `exp`, returning 410;
  3. resolves the tenant through `TenantRepository`, returning 404;
  4. opens `tenant_session_scope`;
  5. reads `get_qr_code`, returning 404;
  6. renders the PNG from `qr_token` with `generate_qr_png` (the same bytes
     as the email always had). Reading `image_storage_key` from storage
     would work too, but regenerating avoids an S3 round trip, and the
     output is deterministic.

  It returns `Response(media_type="image/png", headers={"Cache-Control":
  "private, max-age=86400"})`.

*Implementation note:* the routes are split across two routers that share
the prefix and tag. `core/email_assets_router.py` serves the logo, and
`invitations/email_assets_router.py` serves the QR, backed by
`invitations/service.py::email_qr_png`. The QR route needs invitation
models, and `core` must not import feature packages
(fastapi-architecture §6). Signing stays in `core/email_assets.py`. The
tasks resolve the tenant id from `tenant_schema` with
`TenantRepository.get_by_schema_name`, and only when a base URL is set.

The tenant id sits in the path because schema-per-tenant needs it before
any lookup. Putting it inside the signed message is what stops cross-tenant
probing. It's safe to expose: it's a UUID, not a secret, and the signature
is the gate (security-architecture §1 "tenant_id … from a signed … token,
never a raw client-supplied id").

### 2. Signing
`sig = hex(HMAC_SHA256(secret, f"qr:{tenant_id}:{invitation_id}:{exp}"))[:32]`,
where `secret` is `settings.email_asset_url_secret`, falling back to
`storage_local_url_secret`, then `jwt_secret_key`, the same fallback
chain storage uses. The comparison uses `hmac.compare_digest`.

`exp = int((invitation.expires_at + 7 days).timestamp())`, computed at
render time. For a reschedule, `expires_at` has already moved, so the new
email gets a fresh `exp`. The 7-day tail keeps the pass viewable in the
inbox shortly after the visit without leaving a permanent URL.

Helpers `sign_qr_url(...)` and `verify_qr_signature(...)` live in
`core/email_assets.py` and are unit-tested.

### 3. Absolute URLs from `EMAIL_ASSET_BASE_URL`
A new setting, `email_asset_base_url: str | None`. `render_email` injects
`logo_src = f"{base}/api/v1/public/email-assets/visimio-logo.png"` when it
is set, and the tasks inject `qr_src` (the signed URL). Templates:
- `base.html`: `{% if logo_url %}tenant logo{% elif logo_src %}<img
  src=logo_src>{% else %}styled text "Visimio"{% endif %}`;
- `qr_pass(src, tracking_id)` takes a `src` (either the URL or
  `cid:visit-qr@vmss`).

In fallback, the tasks still pass `inline_images` for the QR.
`build_message` attaches the brand logo only if the HTML contains
`cid:visimio-logo@vmss`, and it no longer will, since the text wordmark
replaces it. So the fallback yields at most one inline part, the QR.

DDEV: `.ddev/config.yaml` `web_environment` gains
`EMAIL_ASSET_BASE_URL=https://vmss-new-api.ddev.site:8443`. That's
reachable from the host browser, and so from Mailpit's viewer. Production
must set the API's public origin, which is documented in `.env.example`.

Remote images and privacy: Gmail proxies the fetch, while other clients
fetch directly or after "show images". That's accepted per the product
decision. The pass block keeps the tracking ID in text under the image
regardless.

### 4. Contact chain
`_resolve_contact(session, invitation, *, branch, front_desk_contact)`
checks, in order:
1. the invitation POC;
2. the host;
3. `branch.contact_person_user_id` → `UserRepository.get_active` →
   display name plus phone or email;
4. the front desk (branch, then Company);
5. `{"contact_title": "Your point of contact", "contact_name": f"Reception
   at {branch.name}", "contact_detail": None}`.

Every step uses `display_name` and skips untrustworthy names. The block
title is "Your point of contact" for every step, so the section heading is
stable. The label distinguishing "Front desk"/"Reception" lives in
`contact_name`. That's at most three user lookups per dispatch, in
sequence, and never in a loop.

### 5. Previews and realistic test data
`scripts/send_email_previews.py` factors out the preview sender used
during review. It renders every template with full sample data and sends
to `preview@visimio.local`, with the subject prefixed `[Preview]`. The
Mailpit round-trip tests set POC, branch and location on their fakes, so
test sends look like real ones.

## Risks / Trade-offs

- [Remote images blocked in some clients] → The tracking ID is always in
  text, and the plain-text part explains it. Accepted.
- [The public route is a new unauthenticated surface] → It's HMAC-gated,
  rate-limited and read-only, returns no JSON, and its expiry is bounded.
  An invalid-signature 403 is logged at `WARNING` (security events).
- [The base URL is misconfigured in production, so images are broken] →
  `/health/readiness` could check it later. For now, the fallback applies
  only when it's unset. A wrong value would still break images, and
  `.env.example` flags it as required for production.
- [Old emails still reference `cid:` parts] → They're unaffected, since
  those messages already carry their parts.

## Migration Plan

Deploy the API, set `EMAIL_ASSET_BASE_URL` (DDEV sets it via config), and
restart the Celery worker. No DB change. Rollback is a revert, which
brings back the inline parts.
