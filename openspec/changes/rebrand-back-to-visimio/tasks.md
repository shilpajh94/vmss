## 1. Brand constant and settings

- [x] 1.1 `core/config.py`: `BRAND_NAME = "Visimio"`; update the comments on `smtp_from_name` and the asset base URL setting
- [x] 1.2 `.env.example`: lines naming "Guestify API", "Current default: Guestify" and "the Guestify logo" (never stage `.env`)
- [x] 1.3 `main.py`: OpenAPI tag description for public email images

## 2. Logo files and tooling

- [x] 2.1 Restore `src/vmss_api/core/email_assets/visimio-logo-on-dark.png` and `visimio-logo-source.png` with `git show 56d023a^:<path>`; delete `guestify-logo-on-dark.png`
- [x] 2.2 Restore `scripts/build_brand_assets.py` from `56d023a^`; confirm it runs and reproduces the restored PNG
- [x] 2.3 Confirm nothing else imports `vtracer`, `fonttools`, `resvg` (`git grep`), then delete `brand/` and `scripts/brand/` and run `uv remove` for the three dev dependencies (never hand-edit `uv.lock`)

## 3. Logo URL, aliases and code names

- [x] 3.1 `core/email_assets.py`: `LOGO_FILENAME = "visimio-logo.png"`, `RETIRED_LOGO_FILENAMES = ("guestify-logo.png",)`, docstring/comments
- [x] 3.2 `core/email_assets_router.py`: `_LOGO_PATH` to `visimio-logo-on-dark.png`, comments
- [x] 3.3 `core/emailing.py`: `BRAND_LOGO_CID = "visimio-logo@vmss"`, logo path, docstring
- [x] 3.4 Comments/docstrings: `core/email_rendering.py`, `identity_verification/senders.py`, `sso/models.py`
- [x] 3.5 `core/email_templates/base.html`: confirm the fallback wordmark splits "Visi" + "mio" in the two colours and the cid `<img>` width/height match the restored PNG

## 4. Scripts

- [x] 4.1 `scripts/send_email_previews.py`: default recipient `preview@visimio.local`
- [x] 4.2 `scripts/qa_regression/run.py`: logo URL assertion

## 5. Tests

- [x] 5.1 `tests/test_email_notifications.py`: Visimio assertions, rename the two branding tests and the From-name and tenant-logo tests, flip the "retired brand absent" checks to "Guestify" (case-sensitive)
- [x] 5.2 `tests/test_email_assets.py`: `logo_url()` ends in `visimio-logo.png`; canonical route 200 with immutable cache header; retired `guestify-logo.png` returns 200 with identical bytes; rename the retired-URL test; `paths` assertion at the end flips
- [x] 5.3 `invitations/tests/helpers.py` and `invitations/tests/test_notifications.py`: logo URL, From name, CID name; update the aspect-ratio expectation from the restored PNG
- [x] 5.4 Add a test that no rendered email references `guestify-logo.png`

## 6. Docs

- [x] 6.1 `docs/features/notifications.md` (brand, logo path, URLs, preview recipient), `invitations.md`, `identity_verification.md`, `sso_authentication.md`

## 7. OpenSpec housekeeping

- [x] 7.1 Reword Guestify to Visimio in the open changes that mention it (`add-sso-oidc-login`, `separate-admin-staff-login`, `autoreload-local-celery-worker`)
- [x] 7.2 Retire `rebrand-to-guestify` (do not archive it into main specs): remove it, or archive with `--skip-specs`, and say it was superseded by this change

## 8. Verify

- [x] 8.1 Sweep: `git grep -n -i guestify -- . ':!openspec/changes/archive'` returns only the retired alias, the tests for it, and this change's own files
- [x] 8.2 Targeted tests, one sequential run: `tests/test_email_notifications.py`, `tests/test_email_assets.py`, `invitations/tests/test_notifications.py`, `identity_verification/tests.py`, `tests/test_api_documentation.py`; `ruff check`, `ruff format --check`, `mypy` on `src/vmss_api/core`
- [x] 8.3 Send previews to Mailpit (`scripts/send_email_previews.py`) with and without `EMAIL_ASSET_BASE_URL`; check header logo/wordmark, From, footer and plain text; Mailpit search for "Guestify" returns 0

## 9. Manual follow-ups (outside this repo)

- [ ] 9.1 In the Fast2SMS portal, read the registered DLT SMS and WhatsApp templates and the sender ID; record in `docs/features/notifications.md` whether any names Guestify or Visimio. If one names the wrong brand, raise it: re-registering needs DLT approval lead time and changes the env template IDs
- [ ] 9.2 Tell the `VMMS_WEB` and mobile teams to rename too (see handoff note), and drop the paired Guestify web change
