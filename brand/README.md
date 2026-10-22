# Guestify logo masters

These SVGs are the source of truth for the Guestify logo. Every logo PNG
and favicon in this repo and in VMMS_WEB is generated from them by
`scripts/build_brand_assets.py`. Don't hand-edit a generated PNG; change a
master here and re-run the build.

| File | What |
|---|---|
| `guestify-mark.svg` | The teal "G" pin mark alone. |
| `guestify-lockup-on-dark.svg` | Mark + "Guestify" wordmark: "Gu" teal `#0EA6B2`, "estify" white. For navy surfaces. |
| `OFL.txt` | Licence of the wordmark font (Poppins, SIL Open Font Licence 1.1). The wordmark glyphs are embedded as outlines, and the OFL requires its licence to travel with them. |
| `wordmark-fit.json` | Provenance of the wordmark: font, weight, scale, baseline and per-letter x positions, as fitted to the supplied artwork. |

The **light lockup** (for white surfaces, "estify" in navy `#12172A`) is
not stored here. The build derives it from the on-dark master by swapping
the `gfy-wordmark-rest` group's fill, so the two can't drift apart.

## How the masters were made

They were rebuilt from the supplied raster artwork
(`openspec/changes/rebrand-to-guestify/assets/guestify-logo-source.png`,
or under `openspec/changes/archive/` once that change is archived). That
raster has soft, compression-noisy edges on a navy background.

- **Mark** (`scripts/brand/trace_mark.py`): the silhouette, including the
  open G counter, is traced from a 4×-supersampled, denoised mask into
  vector paths. That's what makes every edge crisp at any size. The
  folded-ribbon shading inside it is a denoised image layer clipped by
  that silhouette. The shading is soft gradients with no edges of its own.
  A pure-vector shading (`--shading vector`) was tried and came out
  visibly mottled (ΔE 3.8 against 1.0).
- **Wordmark** (`scripts/brand/match_wordmark.py`): six open-licence
  geometric fonts were scored against the artwork by alpha-mask IoU.
  Poppins Bold won at 0.949, with the next best at 0.89. Its glyphs are
  converted to SVG outlines (`fontTools`), so the SVG has no font
  dependency. The match takes several minutes, since every candidate is
  rendered 65 times.
- **Lockup** (`scripts/brand/compose_lockup.py`): mark plus wordmark in
  one shared coordinate system, so the gap and baseline match the artwork
  exactly.

Re-run them in that order to rebuild:

    ddev exec uv run python scripts/brand/trace_mark.py
    ddev exec uv run python scripts/brand/match_wordmark.py
    ddev exec uv run python scripts/brand/compose_lockup.py
    ddev exec uv run python scripts/brand/preview.py --out <png>

The fidelity gates are: mark IoU ≥ 0.97 and mean ΔE ≤ 6, and wordmark
IoU ≥ 0.93. The scripts print PASS or FAIL against them.

If a designer later supplies a proper vector logo, it replaces these
files directly. The build script only reads the two SVGs.
