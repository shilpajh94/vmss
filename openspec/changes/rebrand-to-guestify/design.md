## Context

- Brand assets are produced by one Pillow script,
  `scripts/build_brand_assets.py`. It reads a single source PNG and writes
  the email logo. With `--web-out ../VMMS_WEB` it also writes the portal's
  logo PNGs and favicons. Nothing runs it at build or request time; its
  outputs are committed.
- The supplied Guestify logo (`assets/guestify-logo-source.png`) is a
  2372×1334 opaque raster:
  - a solid navy background (sampled `#12172A`);
  - a teal "G" pin mark drawn as a folded two-tone ribbon (lighter
    cyan-teal faces, darker blue-teal folds);
  - "Gu" in teal (about `#0DA7B3`) and "estify" in white.

  The lockup covers about 2024×644 px, roughly 10× the largest size we
  render (64px email, 2× web, 180px touch icon), so resolution isn't the
  problem. What is poor is the edge quality: soft, compression-noisy
  outlines baked onto navy. Any background keying of this raster leaves
  either a fringe or eroded edges, and these show at 28–32px on a white
  portal header.
- The email logo is served from `GET /api/v1/public/email-assets/visimio-logo.png`
  with `Cache-Control: public, max-age=31536000, immutable`. The router
  comment already states the rule: replacing the image means renaming the
  file. Gmail's image proxy and other clients have cached the current URL.
- When no asset base URL is configured, the email header renders a styled
  text wordmark (`Visi<span teal>mio</span>`).
- `BRAND_LOGO_CID = "visimio-logo@vmss"` in `core/emailing.py` is the
  inline-image fallback name.
- Email clients don't render SVG reliably (Gmail strips it), so the email
  logo must stay a PNG whatever the master is.

## Goals / Non-Goals

**Goals:**
- A vector master that is visually faithful to the supplied logo and
  razor-sharp at every size, from a 16px favicon to a print-size banner.
- A user approval checkpoint on that master before any product code
  changes.
- One script run regenerates every brand raster in both repos from the
  master, with no hand-editing of PNGs.
- Emails already delivered keep rendering a logo (not a broken-image icon).

**Non-Goals:**
- Redesigning the logo. The master reproduces the supplied artwork; it
  doesn't "improve" its shapes, proportions or colours beyond removing
  noise.
- AI upscaling of the raster. More pixels of a noisy edge are still a
  noisy edge, and the output isn't editable.
- Changing the email colour palette or tone table.
- Renaming internal identifiers (see proposal, Out of scope).

## Decisions

### 1. The master is SVG, stored in `brand/` at the repo root
`brand/` is a sibling of `scripts/`, so neither the `vmss_api` package nor
the wheel ships it. It holds:
- `guestify-mark.svg`;
- `guestify-lockup-on-dark.svg`;
- `guestify-lockup-light.svg`;
- `OFL.txt` for the wordmark font (Decision 3);
- a short `README.md` saying these are the masters, how to rebuild them,
  and that everything else is generated from them.

All three SVGs share one `viewBox` coordinate system and the same mark
geometry. The two lockups differ only in the fill of "estify", so the
light lockup is generated from the on-dark one by the build step (one
attribute swap). It is not hand-maintained, which keeps the two from
drifting.

*Alternative rejected:* cleaning the raster (denoise, sharpen, 2×
supersample, then key). It's cheaper, but it's still a raster: edges stay
approximations, and each re-export degrades. The user chose the vector
rebuild.

### 2. The mark: a vector silhouette with clipped image shading
*As built, approved by the user at task 2.7.* This revises the original
plan, which was to rebuild the shading as a few gradient-filled vector
faces.

`scripts/brand/trace_mark.py` (one-off tooling, dev deps only) builds two
layers:

1. **Silhouette.** The script keys the mark from the navy background,
   supersamples the mask 4×, smooths away compression noise, and
   thresholds at half coverage. It then traces the result with `vtracer`
   in binary/spline mode. This one path (the pin with its open G counter)
   is the `clipPath`, and it's what makes every visible edge crisp at any
   size.
2. **Shading.** The source crop is median-filtered (5px) to remove
   compression noise, and its colours are bled outward past the edge, so
   the clip never reveals a navy fringe. It's embedded as a JPEG (q92)
   `<image>`, clipped by the silhouette.

*Why not vector shading:* posterising and tracing the ribbon's soft 3D
gradients was tried at 12–32 colours, with and without a softening blur.
It came out visibly mottled at full size (ΔE 3.5–4.7, against 1.02 for
the image layer), and 300–470 KB against 118 KB. The ribbon's folds are
soft gradients with no hard edges of their own, so an image layer loses
nothing that vectors would keep. The edges, which are the actual quality
problem in the source, are vector either way. `--shading vector` keeps
the alternative reproducible.

**Acceptance metric:** render the mark SVG at the source's pixel scale
and compare its alpha mask with the keyed source mask. The IoU must be at
least 0.97, and the mean colour ΔE (CIE76) over the shared opaque pixels
must be at most 6. The script prints both numbers. Passing them means
"faithful". The user's visual approval (task 2.7) means "good". The
result was IoU 0.997 and ΔE 1.02.

*Alternative rejected:* hand-drawing the ribbon from scratch in a vector
editor. That gives the best result if a designer does it, but nobody here
has the tool or the time, and tracing plus the metric gets close enough.
If a designer's SVG arrives later, it simply replaces
`brand/guestify-mark.svg`.

### 3. The wordmark is a real font, converted to outlines
Tracing letters gives wobbly curves. Typeset glyphs give perfect ones. The
"Guestify" letterforms are a heavy geometric sans: single-storey "a"-style
rounds, a straight-tailed "y" and a slanted-cut "t". Step by step:

1. `scripts/brand/match_wordmark.py` renders "Guestify" in each candidate
   OFL font at its heaviest weights. Candidates: Outfit (already the
   email font stack's first choice), Poppins, Plus Jakarta Sans, Urbanist,
   Lexend and Montserrat, at weights ExtraBold and Bold.
2. For each one, it fits the size, letter-spacing and x-offset to the
   source wordmark's bounding box.
3. It scores alpha-mask IoU against the keyed source wordmark and picks
   the best scoring one.
4. Acceptance: the winner must score an IoU of at least 0.93 (fonts differ
   in small details, so this is looser than the mark). If no candidate
   reaches 0.93, the fallback is to trace the wordmark like the mark
   (Decision 2) and smooth it, and to tell the user the result isn't a
   font match.
5. `fontTools` (`SVGPathPen`) converts the winning glyphs to `<path>`
   outlines with the fitted kerning applied. "Gu" gets fill `#0DA7B3`,
   sampled exactly, and "estify" gets `#FFFFFF`.

There's no `<text>` and no `@font-face`, so the SVG renders identically
everywhere with nothing to load. The font name and weight are recorded in
`brand/README.md`. Font files are downloaded into a scratch dir at build
time, not vendored, but OFL requires the licence to travel with derived
outlines, hence `brand/OFL.txt`.

### 4. Rasters are rendered from SVG with resvg; no keying anywhere
`build_brand_assets.py` loads the SVG masters, creates the light lockup
(Decision 1), and renders each output at its exact target pixel size
with `resvg-py`. That's a pure-Rust renderer shipped as a wheel, so it
needs no system Cairo inside the DDEV container. The outputs are:
- **email:** `guestify-logo-on-dark.png`, the on-dark lockup at 64px tall;
- **`--web-out`:** `src/assets/brand/logo-guestify.svg`,
  `logo-guestify-on-dark.svg` and `logo-guestify-mark.svg`, copied as
  SVG, because the portal can use vectors directly (see the web change);
- **favicons:** `public/favicon.svg`, plus `favicon.png` (48),
  `favicon-32.png` and `apple-touch-icon.png` (180, mark on white) as
  PNG fallbacks.

Small favicons render the mark with a little extra padding, and the
script asserts that the 16/32px renders keep the counter open. A
`--preview <path>` option writes one PNG showing the original raster, the
on-dark render on `#0f172a` and the light render on white, at 32px, 64px
and full size. This is the image the user approves.

`_trim`/`_mark`/`_on_dark` and the colour-tolerance constants are deleted.
`visimio-logo-source.png` and `visimio-logo-on-dark.png` are deleted.

*Alternative rejected:* `cairosvg`. It needs `libcairo2` in the container
image, which is a new system dependency for a one-off script.

### 5. New logo URL, old URL kept as an alias
- `LOGO_FILENAME` becomes `guestify-logo.png`. New emails reference it.
- `email_assets_router` registers **both** `/guestify-logo.png` and the
  retired `/visimio-logo.png`, each serving the Guestify file with the
  same immutable cache header. The retired route is marked
  `include_in_schema=False` and has a comment naming this change.
- Clients that already cached the old URL keep showing the Visimio logo
  until their cache drops it. This is unavoidable, because `immutable` was
  promised. Fresh fetches get Guestify, and nothing 404s.

*Alternative rejected:* a 301 from the old path to the new one. Some image
proxies don't follow redirects for `<img>`, which risks a broken image for
no benefit over serving the bytes directly.

### 6. Inline-image CID renamed
`BRAND_LOGO_CID` becomes `guestify-logo@vmss`. It's only an identifier
inside one MIME message, so nothing outside a single email depends on it.
The `@vmss` domain part stays, since it's an internal identifier.

### 7. Two-colour text wordmark fallback
In `base.html`, the no-asset-URL branch renders
`<span style="color:#14b8c4">Gu</span>estify`, white on the navy band. The
teal is chosen to read close to the logo's `#0DA7B3`, with AA contrast on
`#0f172a`. The existing tone-contrast unit test is extended to check this
pair. If Decision 3 picks a font that is also on the email font stack,
the stack is unchanged. Otherwise it stays `'Outfit','Segoe UI',Arial`,
because a remote web font in email is unreliable anyway.

### 8. Name lives in config defaults, not scattered literals
Two new constants live in `core/config.py`:
- `BRAND_NAME = "Guestify"`;
- `app_name: str = f"{BRAND_NAME} API"`.

`smtp_from_name` defaults to `BRAND_NAME`. `render_email` injects
`brand_name` into every template context, so `base.html`/`base.txt` use
`{{ brand_name }}` instead of literals. A future rename is then a
one-constant change in the API, mirroring the web's `brand.ts`.

## Risks / Trade-offs

- **[Trace fidelity of the folded ribbon]** The pin's two-tone folds are
  the hardest part. A too-simple cleanup flattens the 3D look, and a
  too-literal trace keeps noisy micro-shapes. → The IoU and ΔE gates catch
  shape and colour drift. The preview approval catches "looks flat". If
  the user rejects it twice, stop and recommend getting a designer's SVG,
  rather than iterating indefinitely.
- **[Font isn't the exact original]** The supplied wordmark may come from
  a commercial or modified font. → The ≥0.93 IoU gate plus visual
  approval. The fallback is a traced wordmark (Decision 3), stated
  explicitly to the user.
- **[New dev tooling]** `vtracer`, `fonttools` and `resvg-py` are added
  with `uv add --dev`. → None of them is imported from `src/`, and they
  don't affect the runtime image. If a wheel is unavailable for the
  container's platform, the task stops and reports it, rather than
  silently switching approach.
- **[Deployed `.env` overrides]** `APP_NAME` is set explicitly in the local
  `.env`, and a deployment may set `SMTP_FROM_NAME=Visimio`. Overrides beat
  the new defaults. → The migration plan says to update or remove those
  keys. `.env.example` documents the new defaults. Per git-workflow §5–6,
  this change never stages `.env`.
- **[Stale cached logo]** See Decision 5. This is accepted.
- **[Different aspect ratio]** The Guestify lockup is about 3.1:1, wider
  than Visimio's. The email `<img>` uses `height:32px; width:auto` on the
  URL path. The `cid` fallback hard-codes `width="150"`, which must be
  computed from the rendered PNG's real ratio. → A task covers this, and a
  test asserts the attribute matches the PNG's dimensions.

## Migration Plan

1. Build the SVG master and get the user's approval of the preview
   (tasks group 1–2). No product code changes before that approval.
2. Merge and deploy this API change. Old emails keep working through the
   alias route.
3. In each environment's `.env`, change or remove `APP_NAME` and
   `SMTP_FROM_NAME` if they still say Visimio.
4. Merge and deploy the paired `VMMS_WEB` change, whose assets this
   change's script generated.
5. Rollback: revert the commit. The old filename route returns with it,
   and the new route simply disappears. Emails sent in between point at
   `guestify-logo.png` and would 404 after a rollback. That's an accepted
   window, which can be avoided by keeping the alias pair if rolling back
   only the copy.
