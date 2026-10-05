## 1. Settings and signing

- [x] 1.1 Add `email_asset_base_url` (`EMAIL_ASSET_BASE_URL`) and `email_asset_url_secret` (`EMAIL_ASSET_URL_SECRET`) to `core/config.py`. Add placeholders to `.env.example`, and a note that production must set the API's public origin. Add `EMAIL_ASSET_BASE_URL=https://vmss-new-api.ddev.site:8443` to `.ddev/config.yaml` `web_environment`.
- [x] 1.2 Add `core/email_assets.py` with `logo_url()`, `sign_qr_url(tenant_id, invitation_id, expires_at)` and `verify_qr_signature(...)` (design.md Decision 2), plus unit tests for a valid, tampered (each field) and expired signature.

## 2. Public asset routes

- [x] 2.1 Add `core/email_assets_router.py`: `GET /public/email-assets/visimio-logo.png` (immutable caching) and `GET /public/email-assets/{tenant_id}/qr/{invitation_id}.png` (rate-limited 60/min; 403, 410 and 404 as specified; private caching; a 403 logged at WARNING). Register it in `api.py` and add the `email-assets` tag to `main.py` `_TAGS_METADATA`.
- [x] 2.2 Endpoint tests covering: 200 PNG that decodes to the persisted token; 403 tampered invitation or tenant; 410 expired; 404 unknown tenant, invitation or QR row; logo 200 with a cache header; and that the route appears in OpenAPI with its tag (`tests/test_api_documentation.py`).

## 3. Rendering and dispatch

- [x] 3.1 `render_email` injects `logo_src` when the base URL is set. `base.html` renders, in order of preference: the tenant logo, the `logo_src` image, then a styled "Visimio" text wordmark. Log `email_asset_base_url_unset` once per process at WARNING when it's unset.
- [x] 3.2 Change `_macros.html::qr_pass` to take `src`. The confirmation and reschedule templates call `qr_pass(qr_src, tracking_id)`.
- [x] 3.3 In `invitations/tasks.py`, build `qr_src` via `sign_qr_url` when configured and pass no `inline_images`. Otherwise use `cid:visit-qr@vmss` plus the inline image (the fallback). This applies to both the approval and the approved-reschedule paths.
- [x] 3.4 Extend `_resolve_contact` with the branch contact person and the "Reception at {branch}" steps, and use the uniform "Your point of contact" title (design.md Decision 4).

## 4. Tests, previews, docs

- [x] 4.1 Rendering tests:
  - configured: absolute `src` for the logo and QR, and no `cid:` anywhere;
  - unconfigured: text wordmark, QR `cid:`, and a WARNING;
  - `build_message` for a configured confirmation yields exactly `multipart/alternative` (text + html).
- [x] 4.2 Contact-chain tests: POC → host → branch contact person → front desk → reception, with untrustworthy names skipped.
- [x] 4.3 Mailpit tests with `email_asset_base_url` set and realistic fakes (POC, place, front desk):
  - confirmation and reschedule show `Attachments == []` and `Inline == []`;
  - the HTML QR `src` points at the endpoint;
  - fetching it through the ASGI test client returns the PNG.
- [x] 4.4 Add `scripts/send_email_previews.py` (every template, full sample data, `[Preview]` subjects), and document it in `docs/features/notifications.md`.
- [x] 4.5 Docs: in `notifications.md`, cover the image delivery model, settings, fallback and contact chain. In `invitations.md`, add the endpoint table row and the QR-by-URL note.
- [x] 4.6 Restart the Celery worker, send the previews, and confirm in Mailpit that no email shows an attachment strip and that the logo and QR load.
- [x] 4.7 Run `ruff check`, `ruff format --check`, `mypy` on `core/`, and the full `pytest` suite, comparing failures against the known pre-existing set.
