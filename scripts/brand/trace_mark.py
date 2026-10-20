"""Traces the Guestify "G" pin mark from the supplied raster into
`brand/guestify-mark.svg` (rebrand-to-guestify design.md Decision 2).

    ddev exec uv run python scripts/brand/trace_mark.py

Two layers, so the edge is crisp but the folded-ribbon shading stays soft:
- the silhouette (pin + transparent G counter), traced from a supersampled,
  denoised mask; it's both the clip path and what makes the logo look sharp;
- the shading, posterised into a few teal tones, traced as flat regions,
  then softened with a small blur and clipped by the silhouette, which turns
  the posterisation bands back into the source's smooth gradients.

Prints the fidelity numbers (IoU, ΔE) the design gates on.
"""

import argparse
import base64
import io
import re

import vtracer
from _common import (
    BRAND_DIR,
    LOCKUP_BOX,
    MARK_RIGHT,
    background_colour,
    binary_mask,
    iou,
    key_alpha,
    load_source,
    mean_delta_e,
    render_svg,
)
from PIL import Image, ImageChops, ImageFilter, ImageMath

_PAD = 12  # source px around the mark crop, so edge tracing isn't clipped
_SUPERSAMPLE = 4
_SHADE_SCALE = 1
_SHADE_COLOURS = 12
_SOFTEN = 5.0  # blur radius (source px) applied to the shading layer
_PREBLUR = 1.5  # denoise before posterising
_SHADE_SPECKLE = 48
_RASTER_MEDIAN = 5  # px; removes compression noise, keeps the soft folds
_RASTER_QUALITY = 92

MARK_IOU_MIN = 0.97
MARK_DELTA_E_MAX = 6.0

_PATH_RE = re.compile(r"<path[^>]*/>")


def _png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _paths(svg: str, prefix: str = "") -> list[str]:
    """vtracer's `<path>`s, with `prefix` prepended to each path's own
    `translate(...)`. A `<clipPath>` may only contain shapes, not a `<g>`,
    so a shared transform has to live on every path."""
    out = []
    for path in _PATH_RE.findall(svg):
        match = re.search(r'transform="([^"]*)"', path)
        own = match.group(1) if match else ""
        transform = f"{prefix} {own}".strip()
        path = re.sub(r'\stransform="[^"]*"', "", path)
        if transform:
            path = path.replace("<path", f'<path transform="{transform}"', 1)
        out.append(path)
    return out


def _extrapolate_colours(rgb: Image.Image, solid: Image.Image) -> Image.Image:
    """Fill non-opaque pixels with colour bled outward from the opaque
    interior (normalised convolution), so traced shading regions overrun
    the silhouette edge instead of picking up navy-tinted fringe colours.
    The silhouette clip trims the overrun."""
    # A tight pass keeps edge colours local; a wide second pass fills the
    # rest of the crop, so no pixel is left black for a blur to pull in.
    for radius in (6, 60):
        weight = solid.filter(ImageFilter.GaussianBlur(radius))
        out = []
        for band in rgb.split():
            premul = ImageChops.multiply(band, solid).filter(ImageFilter.GaussianBlur(radius))
            bled = ImageMath.lambda_eval(
                lambda a: a["convert"](a["p"] * 255 / a["max"](a["w"], 1), "L"),
                p=premul,
                w=weight,
            )
            out.append(Image.composite(band, bled, solid))
        rgb = Image.merge("RGB", out)
        solid = weight.point(lambda w: 255 if w >= 24 else 0)
    return rgb


def _shading_vector(crop: Image.Image, solid: Image.Image, ox: int, oy: int) -> list[str]:
    """Shading as posterised, traced flat regions, softened by a blur."""
    shade = _extrapolate_colours(crop.filter(ImageFilter.GaussianBlur(_PREBLUR)), solid)
    w, h = shade.size
    shade = shade.resize((w * _SHADE_SCALE, h * _SHADE_SCALE), Image.Resampling.LANCZOS)
    shade = shade.quantize(_SHADE_COLOURS, method=Image.Quantize.MEDIANCUT, kmeans=4).convert("RGB")
    shading_svg = vtracer.convert_raw_image_to_svg(
        _png_bytes(shade),
        img_format="png",
        colormode="color",
        hierarchical="stacked",
        mode="spline",
        filter_speckle=_SHADE_SPECKLE,
        color_precision=8,
        layer_difference=4,
        corner_threshold=60,
        length_threshold=4.0,
        splice_threshold=45,
        path_precision=1,
    )
    return [
        '<defs><filter id="gfy-mark-soften" x="-5%" y="-5%" width="110%" height="110%">'
        f'<feGaussianBlur stdDeviation="{_SOFTEN}"/></filter></defs>',
        '<g filter="url(#gfy-mark-soften)">',
        *(f"  {p}" for p in _paths(shading_svg, f"translate({ox} {oy}) scale({1 / _SHADE_SCALE})")),
        "</g>",
    ]


def _shading_raster(crop: Image.Image, solid: Image.Image, ox: int, oy: int) -> list[str]:
    """Shading as a denoised image layer. The ribbon's folds are soft
    gradients with no hard edges of their own, so a raster at source
    resolution reproduces them faithfully; every visible edge still comes
    from the vector clip."""
    shade = crop.filter(ImageFilter.MedianFilter(_RASTER_MEDIAN))
    shade = _extrapolate_colours(shade, solid)
    buf = io.BytesIO()
    shade.save(buf, format="JPEG", quality=_RASTER_QUALITY, optimize=True, subsampling=0)
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    return [
        f'<image x="{ox}" y="{oy}" width="{crop.width}" height="{crop.height}" '
        f'preserveAspectRatio="none" href="data:image/jpeg;base64,{data}"/>'
    ]


def trace_mark(shading_mode: str = "raster") -> tuple[str, dict[str, float]]:
    source = load_source()
    bg = background_colour(source)
    left, top, _, bottom = LOCKUP_BOX
    box = (left - _PAD, top - _PAD, MARK_RIGHT + _PAD, bottom + _PAD)
    crop = source.crop(box)
    alpha = key_alpha(crop, bg)

    # --- silhouette -------------------------------------------------------
    mask = binary_mask(alpha, supersample=_SUPERSAMPLE)
    stencil = Image.merge("RGB", [ImageChops.invert(mask)] * 3)  # black shape on white
    silhouette_svg = vtracer.convert_raw_image_to_svg(
        _png_bytes(stencil),
        img_format="png",
        colormode="binary",
        mode="spline",
        filter_speckle=16,
        corner_threshold=60,
        length_threshold=20.0,  # fewer, smoother curves; IoU unchanged
        splice_threshold=45,
        path_precision=1,
    )
    ox, oy = box[0] - left, box[1] - top  # crop origin relative to lockup origin
    silhouette = [
        re.sub(r'\sfill="[^"]*"', "", p)
        for p in _paths(silhouette_svg, f"translate({ox} {oy}) scale({1 / _SUPERSAMPLE})")
    ]

    # --- shading ----------------------------------------------------------
    solid = alpha.point(lambda a: 255 if a >= 250 else 0)
    build = _shading_raster if shading_mode == "raster" else _shading_vector
    shading = build(crop, solid, ox, oy)

    # --- assemble, in lockup coordinates ------------------------------------
    bbox = mask.getbbox()
    assert bbox is not None
    vx = ox + bbox[0] / _SUPERSAMPLE
    vy = oy + bbox[1] / _SUPERSAMPLE
    vw = (bbox[2] - bbox[0]) / _SUPERSAMPLE
    vh = (bbox[3] - bbox[1]) / _SUPERSAMPLE
    svg = "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="{vx:.2f} {vy:.2f} {vw:.2f} {vh:.2f}" '
            f'width="{vw:.0f}" height="{vh:.0f}">',
            "  <defs>",
            '    <clipPath id="gfy-mark-clip">',
            *(f"      {p}" for p in silhouette),
            "    </clipPath>",
            "  </defs>",
            '  <g id="gfy-mark" clip-path="url(#gfy-mark-clip)">',
            *(f"    {p}" for p in shading),
            "  </g>",
            "</svg>",
        ]
    )

    # --- fidelity -----------------------------------------------------------
    # Re-render the full crop window at 1 source px per unit and compare.
    window = svg.replace(
        f'viewBox="{vx:.2f} {vy:.2f} {vw:.2f} {vh:.2f}" width="{vw:.0f}" height="{vh:.0f}"',
        f'viewBox="{ox} {oy} {crop.width} {crop.height}" '
        f'width="{crop.width}" height="{crop.height}"',
    )
    rendered = render_svg(window)
    metrics = {
        "iou": iou(rendered.getchannel("A"), alpha),
        "delta_e": mean_delta_e(
            rendered,
            crop,
            ImageChops.multiply(
                solid, rendered.getchannel("A").point(lambda a: 255 if a >= 250 else 0)
            ),
        ),
    }
    return svg, metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shading", choices=["raster", "vector"], default="raster")
    args = parser.parse_args()
    svg, metrics = trace_mark(args.shading)
    BRAND_DIR.mkdir(exist_ok=True)
    out = BRAND_DIR / "guestify-mark.svg"
    out.write_text(svg + "\n")
    print(f"wrote {out} ({len(svg) // 1024} KB)")
    ok = metrics["iou"] >= MARK_IOU_MIN and metrics["delta_e"] <= MARK_DELTA_E_MAX
    print(
        f"mark IoU {metrics['iou']:.4f} (≥ {MARK_IOU_MIN}), "
        f"ΔE {metrics['delta_e']:.2f} (≤ {MARK_DELTA_E_MAX}) → {'PASS' if ok else 'FAIL'}"
    )


if __name__ == "__main__":
    main()
