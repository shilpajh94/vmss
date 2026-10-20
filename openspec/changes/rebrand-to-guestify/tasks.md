## 1. Logo tooling

- [x] 1.1 Add the dev-only dependencies: `ddev exec uv add --dev vtracer fonttools resvg-py`. If a wheel is unavailable for the container platform, stop and report it rather than switching approach (design Risks).
- [x] 1.2 Create `brand/` at the repo root and a `scripts/brand/` package for the one-off tooling. Confirm that neither is included in the `vmss_api` package build.

## 2. Vector logo master (user approval gate)

- [x] 2.1 `scripts/brand/trace_mark.py`: crop the mark from `openspec/changes/rebrand-to-guestify/assets/guestify-logo-source.png`. Upsample 2× with Lanczos, posterise to background plus about 4 teal tones (k-means), and trace with `vtracer` in colour/spline mode with speckle filtering (design Decision 2).
- [x] 2.2 Build the mark from two layers: the traced vector silhouette (pin plus transparent G counter) as a clip path, and the denoised shading image clipped by it. This revises the original plan of gradient faces (design Decision 2, approved at 2.7). Write `brand/guestify-mark.svg`.
- [x] 2.3 `scripts/brand/match_wordmark.py`: score the candidate OFL fonts (Outfit, Poppins, Plus Jakarta Sans, Urbanist, Lexend, Montserrat; ExtraBold and Bold) by fitted alpha-mask IoU against the source wordmark. Print the ranking and pick the best (Decision 3). If none reaches 0.93, trace the wordmark instead, and flag that to the user.
- [x] 2.4 Convert the winning glyphs to `<path>` outlines with `fontTools` (`SVGPathPen`), with the fitted spacing applied. Use `#0DA7B3` for "Gu" and `#FFFFFF` for "estify". Compose `brand/guestify-lockup-on-dark.svg` with the mark, using the source's mark-to-wordmark gap and baseline alignment.
- [x] 2.5 Write `brand/OFL.txt` (the chosen font's licence) and `brand/README.md` (what the masters are, the chosen font name and weight, how to re-run 2.1–2.4, and that all PNGs are generated from these files).
- [x] 2.6 Print the fidelity numbers: mark IoU ≥ 0.97 and ΔE ≤ 6, wordmark IoU ≥ 0.93. Fix and re-run until they pass.
- [x] 2.7 Render the comparison preview: the original raster, the on-dark SVG on `#0f172a`, and the light SVG on white, at 32px, 64px and full size. **Stop and show the preview to the user for approval.** Do not start group 3 or any later group until the user approves. If the user rejects the result twice, recommend getting a designer-made SVG instead of iterating further.

## 3. Asset rendering from the master

- [x] 3.1 Rewrite `scripts/build_brand_assets.py` to load the `brand/*.svg` masters and derive the light lockup from the on-dark one ("estify" fill → `#12172A`). Render with `resvg-py` at exact target sizes. Delete `_trim`, `_mark`, `_on_dark` and the tolerance constants, and update the module docstring (Decision 4).
- [x] 3.2 Outputs:
  - `src/vmss_api/core/email_assets/guestify-logo-on-dark.png`, 64px tall;
  - with `--web-out`, copied SVGs `src/assets/brand/logo-guestify{,-on-dark,-mark}.svg`;
  - `public/favicon.svg`, `favicon.png` (48), `favicon-32.png` and `apple-touch-icon.png` (180, mark on white).

  Keep the `--preview <path>` option.
- [x] 3.3 Assert that the 16px and 32px favicon renders keep the G counter open (a transparent pixel at its centre). Add padding if they don't.
- [x] 3.4 Run `ddev exec uv run python scripts/build_brand_assets.py --web-out ../VMMS_WEB --preview <scratch>/preview.png`.
- [x] 3.5 Delete `core/email_assets/visimio-logo-source.png` and `visimio-logo-on-dark.png`.

## 4. Brand name in one place

- [x] 4.1 Add `BRAND_NAME = "Guestify"` to `core/config.py`. Make `app_name` default to `f"{BRAND_NAME} API"` and `smtp_from_name` default to `BRAND_NAME`. Update the comments that say Visimio.
- [x] 4.2 Update `.env.example`: the defaults comments for `APP_NAME` and `SMTP_FROM_NAME` (keep `_PLACEHOLDER_` style values), and the email-asset-base-URL comment. Do not stage `.env` (git-workflow §5–6). Tell the user that the local `.env` sets `APP_NAME` explicitly and needs updating by hand.
- [x] 4.3 Inject `brand_name` into the template context in `core/email_rendering.py::render_email`.

## 5. Email templates and logo serving

- [x] 5.1 `core/email_templates/base.html`: replace every Visimio literal with `{{ brand_name }}` (alt text, "Sent by" default, "Powered by", copyright). Make the text fallback the two-colour wordmark `Gu` + `estify` (Decision 7).
- [x] 5.2 `core/email_templates/base.txt`: the same literal → `{{ brand_name }}` swap.
- [x] 5.3 `base.html` `cid` branch: compute the `width` attribute from the rendered `guestify-logo-on-dark.png` ratio at 32px height.
- [x] 5.4 `core/email_assets.py`: set `LOGO_FILENAME = "guestify-logo.png"` and update the docstring.
- [x] 5.5 `core/email_assets_router.py`: serve `guestify-logo-on-dark.png` at the new filename. Add the retired `/visimio-logo.png` alias route (same file, same cache header, `include_in_schema=False`, comment naming this change) (Decision 5).
- [x] 5.6 `core/emailing.py`: switch the logo path to the new PNG and set `BRAND_LOGO_CID = "guestify-logo@vmss"`. Update the comments.
- [x] 5.7 `main.py`: in the email-assets OpenAPI tag description, say "Guestify header logo".

## 6. Remaining references

- [x] 6.1 Replace Visimio in docstrings and comments: `identity_verification/senders.py`, `invitations/tasks.py`, `sso/models.py`, `core/email_rendering.py`, `_macros.html`. Leave references to archived change *names* (e.g. `refine-email-templates-and-visimio-brand`) as they are, since those are historical identifiers.
- [x] 6.2 `scripts/qa_regression/run.py`: use the new logo path. `scripts/send_email_previews.py`: change the default `--to` to `preview@guestify.local`.
- [x] 6.3 Docs: update `docs/features/notifications.md` (logo master in `brand/`, file, URL, alias note, footer copy), `invitations.md`, `identity_verification.md`, `reports.md` and `sso_authentication.md`.
- [x] 6.4 Run `git grep -n -i visimio -- src scripts tests docs .env.example`. The only hits left should be archived change names and the alias route.

## 7. Tests

- [x] 7.1 `tests/test_email_notifications.py`:
  - branding assertions become "Guestify" (copyright, "Powered by", plain-text, From display name, logo `<img>` src/alt);
  - assert "Visimio" is absent from every rendered template;
  - add a fallback-wordmark test for the no-base-URL case;
  - extend the contrast test to the fallback teal on navy.
- [x] 7.2 `tests/test_email_assets.py`:
  - `logo_url()` ends in `guestify-logo.png`;
  - the new route returns 200 `image/png` with the immutable cache header;
  - the retired `visimio-logo.png` route returns 200 with byte-identical content.
- [x] 7.3 Add a test asserting the `cid` branch's `width`/`height` attributes match the rendered PNG's aspect ratio (±1px).
- [x] 7.4 Update the Mailpit assertions in `invitations/tests.py` (logo URL, From name "Guestify", CID name) and the `identity_verification/tests.py` branding comment and assertions.
- [x] 7.5 Run `ddev exec uv run pytest tests/test_email_notifications.py tests/test_email_assets.py`. Then run the full suite (single process, never in parallel), diffing failures against a baseline because of known pre-existing flakes.
- [x] 7.6 Run `ruff check`, `ruff format --check` (including `scripts/brand/`) and `mypy` on `src/vmss_api/core`.

## 8. Ship and follow-up

- [x] 8.1 Send the email previews to Mailpit (`scripts/send_email_previews.py`). Visually confirm the header logo, footer and plain-text part.
- [ ] 8.2 After archive, retitle the main-spec scenario "Visimio branding is shown when the tenant has no logo" to "Guestify branding is shown when the tenant has no logo" in `openspec/specs/email-notifications/spec.md`. The delta had to keep the old name to match.
- [ ] 8.3 Implement the paired `VMMS_WEB` change `rebrand-to-guestify` next. Its SVGs and favicons were already generated by task 3.4.

## 9. "Everywhere" sweep (added after the cross-check)

- [x] 9.1 Add `staff_lifecycle_update` (one case per `event`: `approval_reverted`, `denied`, `rescheduled`) to the branding test in `tests/test_email_notifications.py`. Today it's the only email type that `test_every_email_carries_guestify_branding` doesn't render.
- [x] 9.2 Add `approval_reverted` and `staff_lifecycle_update` to `TEMPLATES` in `scripts/send_email_previews.py`, so a preview run covers all 12 email types.
- [x] 9.3 Send the previews to Mailpit twice: once with `EMAIL_ASSET_BASE_URL` set (header logo image) and once without (text wordmark). For each of the 24 messages, check:
  - the header shows the Guestify logo or the "Gu"+"estify" wordmark;
  - the From header is `Guestify <…>`;
  - the footer reads "Powered by Guestify" and "© {year} Guestify";
  - the plain-text part matches.

  Then query the Mailpit search API for "Visimio": it must return 0 messages. This supersedes 8.1.
- [ ] 9.4 **Manual, outside the repo:** in the Fast2SMS portal, read the registered DLT SMS templates (OTP, registration pending/confirmed/confirmed-code/denied, visit rescheduled/details changed), the WhatsApp templates and the sender ID. Record whether any of them names Visimio or VisitorPass in `docs/features/notifications.md`. If one does, raise it with the user: re-registering with DLT needs approval lead time, and the env template IDs change afterwards.
- [x] 9.5 Reword "VisitorPass" to "Guestify" in the still-open changes `add-sso-oidc-login` (proposal and `specs/sso-authentication/spec.md`) and `separate-admin-staff-login` (`specs/sso-authentication/spec.md`). Otherwise archiving them would write the retired name into the main `sso-authentication` spec. Run `openspec validate` on both afterwards.
- [x] 9.6 Final sweep: running `git grep -n -i -E "visimio|visitorpass" -- src scripts docs tests .env.example openspec/changes ':!openspec/changes/archive' ':!openspec/changes/rebrand-to-guestify'` must return only archived change names, the retired-logo alias, and tests asserting the old names' absence.

