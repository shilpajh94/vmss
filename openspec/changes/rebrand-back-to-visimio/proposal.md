## Why

The product name is going back from **Guestify** to **Visimio**. `rebrand-to-guestify` (commit `56d023a`, already on `origin/feature/iteration4`) put "Guestify" into every outbound email, the API's own name, the logo files and URL, the docs and the tests. Anything still saying Guestify next to the real product name would look broken, so each place it was introduced has to be switched back.

The Guestify change was never archived, so `openspec/specs/` still says **Visimio** everywhere. Archiving it now would write Guestify into the main specs, so it must be retired instead (see Decisions in `design.md`).

## What Changes

- **Brand constant:** `BRAND_NAME` in `core/config.py` becomes "Visimio". `app_name` ("Visimio API"), the default `SMTP_FROM_NAME` ("Visimio") and every email template's `brand_name` follow from it, so the header alt text, fallback text wordmark, footer ("Sent by", "Powered by Visimio", "© {year} Visimio") and plain-text part switch with no template edit.
- **Logo files:** the Guestify email logo `core/email_assets/guestify-logo-on-dark.png` is replaced by the previous Visimio logo (`visimio-logo-on-dark.png`), restored byte-for-byte from git history (`56d023a^`). The Guestify vector masters and tracing tooling (`brand/`, `scripts/brand/`) and their three dev-only dependencies are removed, and `scripts/build_brand_assets.py` goes back to the raster pipeline that produced the Visimio logo.
- **Logo URL:** `GET /api/v1/public/email-assets/visimio-logo.png` is the canonical URL again. `guestify-logo.png` becomes the retired alias that keeps serving the logo, because emails sent since the Guestify release point at it. The inline-image name goes back to `visimio-logo@vmss`.
- **Everything else that names it:** `.env.example` comments, `main.py` OpenAPI tag text, code comments and docstrings (`email_assets*.py`, `emailing.py`, `email_rendering.py`, `identity_verification/senders.py`, `sso/models.py`), `scripts/send_email_previews.py` (default recipient `preview@visimio.local`) and `scripts/qa_regression/run.py`.
- **Tests:** assertions, test names and the "retired brand is absent" guards flip to Visimio (Guestify becomes the retired name).
- **Docs:** `docs/features/notifications.md`, `invitations.md`, `identity_verification.md`, `sso_authentication.md`.
- **OpenSpec housekeeping:** `rebrand-to-guestify` is superseded (not archived); Guestify wording in other open changes is reworded.

## Capabilities

### Modified Capabilities
- `invitations`: the public email-logo URL requirement gains the retired `guestify-logo.png` alias.
- `email-notifications`: pins the brand name to the single `BRAND_NAME` constant and the fallback wordmark to "Visi" + "mio".

## Impact

- Code: `core/config.py`, `core/email_assets.py`, `core/email_assets_router.py`, `core/emailing.py`, `core/email_rendering.py`, `identity_verification/senders.py`, `sso/models.py`, `main.py`; the logo PNG; `pyproject.toml` (+ `uv.lock` via `uv remove`).
- Tests: `tests/test_email_assets.py`, `tests/test_email_notifications.py`, `invitations/tests/helpers.py`, `invitations/tests/test_notifications.py`.
- API: the logo URL changes name (additive: both URLs answer 200). No breaking change.
- Config: `.env.example` comments only. The local `.env` is not edited.
- Frontend / other repos: the portal (`VMMS_WEB`) and mobile app are separate repos and need their own rename; the portal's logo files come from `scripts/build_brand_assets.py --web-out`.

## Out of scope

- Internal identifiers: the `vmss_api` package, `VMSS_API`/`VMMS_API` repo names, `vmss:` Redis keys, `vmss_test`, the `@vmss` CID suffix. They were never branded.
- Redesigning the logo.
- Registered third-party templates (Fast2SMS DLT / WhatsApp). They are checked manually, see tasks.
- Archived changes: history is left as written.

## Assumptions (change if wrong)

- **The Visimio logo is the one that existed before the Guestify rebrand**, restored from git. No new Visimio artwork was supplied. If there is new artwork, send it and the logo task changes (the rest does not).
- **Keep the `guestify-logo.png` alias** indefinitely, same as the earlier `visimio-logo.png` alias, since emails live in inboxes for years.
- **Drop the Guestify vector tooling** rather than keep it dormant; it is recoverable from git history.
