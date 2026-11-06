## Context

- `rebrand-to-guestify` (`56d023a`) is pushed. It routed the visible brand through one constant (`BRAND_NAME`, `core/config.py`) and the Jinja variable `brand_name`, so templates contain no hard-coded brand string. The remaining hard-coded places are the logo filename/URL, CID name, comments, docs, scripts and tests.
- The logo is served with `Cache-Control: public, max-age=31536000, immutable`; the code already states the rule that replacing the image means renaming the file. Emails sent while Guestify was live reference `.../guestify-logo.png`; emails older than that reference `.../visimio-logo.png`.
- `openspec/specs/` was never updated to Guestify (the change is unarchived), so the main specs still say Visimio.
- The previous Visimio assets exist in git: `visimio-logo-on-dark.png` and `visimio-logo-source.png` under `src/vmss_api/core/email_assets/` at `56d023a^`, and the old `scripts/build_brand_assets.py`.

## Goals / Non-Goals

**Goals:** every user-visible and developer-facing mention reads Visimio; no email ever shows a broken logo; the main specs stay correct; one constant remains the only source of the name.

**Non-Goals:** logo redesign; renaming internal identifiers; touching other repos.

## Decisions

**1. Retire `rebrand-to-guestify`, do not archive it.** Archiving would merge its deltas (Guestify wording) into the main specs. Its code is already in the tree, so what remains of it is history. After this change lands, remove the change directory (or archive it with `--skip-specs`) and note it superseded. Its three open tasks go with it: 8.2 (retitle a scenario to Guestify) becomes moot, 8.3 (paired `VMMS_WEB` Guestify change) must be dropped in that repo too, and 9.4 (check Fast2SMS DLT templates for brand names) is carried into this change's tasks because it is about the brand name, not which one.

**2. Restore the Visimio logo from git, byte-for-byte.** `git show 56d023a^:<path>` for the PNG (and source raster), rather than re-deriving. The bytes are what emails sent before the Guestify release already show, so the legacy URL is never visually inconsistent. Chosen over re-rendering from SVG because there is no Visimio vector master.

**3. Logo URL and aliases.** `LOGO_FILENAME = "visimio-logo.png"`; `RETIRED_LOGO_FILENAMES = ("guestify-logo.png",)`, served from the same file by the existing alias loop in `email_assets_router.py`, so no new route code. `visimio-logo.png` was last cached with the *same* image, so reusing the name is safe despite `immutable`. The inline fallback CID returns to `visimio-logo@vmss`.

**4. Remove the Guestify tooling.** Delete `brand/` and `scripts/brand/`; restore `scripts/build_brand_assets.py` from `56d023a^` (writes the email logo and, with `--web-out`, the portal's `logo-visimio*` files); drop `vtracer`, `fonttools`, `resvg-py` with `uv remove` (never hand-edit `uv.lock`). Check first that nothing else imports them. The Guestify source raster stays only in the superseded change's `assets/`, which is deleted with it (git keeps it).

**5. Tests flip, they are not deleted.** `test_every_email_carries_guestify_branding` becomes the Visimio equivalent and keeps asserting the other name is absent (now "Guestify" in rendered output and template files, case-sensitive, so archived/superseded change names in comments do not trip it). The "retired logo URL still serves the current logo" test is inverted to `guestify-logo.png`, byte-identical to the current one. The cid-branch width/height aspect test reads the restored PNG, so its expected ratio is re-measured, not copied.

**6. Fallback wordmark.** With no asset base URL the header renders a two-colour text wordmark; it must read "Visi" + "mio" (`Visi<span teal>mio</span>`), as before the Guestify release. Confirm in `base.html` rather than assume, since the Guestify change touched the split.

**7. Docs and comments are edited by sweep.** `git grep -i guestify` outside `openspec/changes/archive` is the work list; the final sweep must return only the retired alias, tests asserting its absence/alias, and the superseded change.

## Risks / Trade-offs

- **Cached/old emails:** both URL names keep working, so nothing breaks; a client that cached the Guestify logo keeps showing it until it refetches. Accepted, same as the earlier rename.
- **Third-party registered templates** (Fast2SMS DLT, WhatsApp) may name a brand; re-registration has lead time and changes env template IDs. Checked manually, not blocked on.
- **Another rename later:** the constant plus the alias list make it small, but the logo file name is still hard-coded in five places; not worth abstracting now.
- **Mixed-brand window:** the web and mobile repos switch separately; flag in the handoff message.
