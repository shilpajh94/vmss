"""Shared helpers for the one-off Guestify logo-master tooling
(rebrand-to-guestify design.md Decisions 2-3). Dev-only: nothing under
`src/` imports this, and its dependencies (vtracer, fontTools, resvg-py)
are dev-group only.

All master SVGs share one coordinate system: source-image pixels, shifted
so the lockup's bounding box starts at (0, 0). That's what lets the mark,
the wordmark and the fidelity checks line up without any rescaling.
"""

import io
import re
from pathlib import Path

import resvg_py
from PIL import Image, ImageChops, ImageCms, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "openspec/changes/rebrand-to-guestify/assets/guestify-logo-source.png"
BRAND_DIR = ROOT / "brand"

# Lockup bounding box in source pixels (left, top, right, bottom), and the
# column where the mark ends / the wordmark begins. Measured once from the
# supplied image; the gap between 702 and 830 is pure background.
LOCKUP_BOX = (172, 464, 2197, 1109)
MARK_RIGHT = 703
WORDMARK_LEFT = 830

# Colour distance from the background below which a pixel is pure
# background (compression noise), and above which it's fully opaque.
_KEY_LO = 14.0
_KEY_HI = 70.0


def load_source() -> Image.Image:
    return Image.open(SOURCE).convert("RGB")


def background_colour(image: Image.Image) -> tuple[int, int, int]:
    """Median of the four 40px corner patches, so a re-export with a
    slightly different navy still keys correctly."""
    w, h = image.size
    samples: list[tuple[int, int, int]] = []
    for x0, y0 in [(0, 0), (w - 40, 0), (0, h - 40), (w - 40, h - 40)]:
        samples.extend(image.crop((x0, y0, x0 + 40, y0 + 40)).get_flattened_data())
    channels = list(zip(*samples, strict=True))
    return (
        sorted(channels[0])[len(samples) // 2],
        sorted(channels[1])[len(samples) // 2],
        sorted(channels[2])[len(samples) // 2],
    )


def key_alpha(image: Image.Image, bg: tuple[int, int, int]) -> Image.Image:
    """Soft alpha ('L') from colour distance to the background."""
    flat = Image.new("RGB", image.size, bg)
    diff = ImageChops.difference(image, flat)
    r, g, b = diff.split()
    # Euclidean distance via a lookup on the summed squares would need
    # numpy; the max-channel difference is a close, monotone stand-in.
    dist = ImageChops.lighter(ImageChops.lighter(r, g), b)
    span = _KEY_HI - _KEY_LO
    return dist.point(
        lambda d: 0 if d <= _KEY_LO else 255 if d >= _KEY_HI else round((d - _KEY_LO) * 255 / span)
    )


def binary_mask(alpha: Image.Image, *, supersample: int = 4, blur: float = 1.2) -> Image.Image:
    """Clean silhouette for tracing: supersample, smooth away compression
    noise along the edge, then threshold at half coverage."""
    w, h = alpha.size
    big = alpha.resize((w * supersample, h * supersample), Image.Resampling.LANCZOS)
    big = big.filter(ImageFilter.GaussianBlur(blur * supersample))
    return big.point(lambda a: 255 if a >= 128 else 0)


def render_svg(
    svg: str, *, width: int | None = None, height: int | None = None, background: str | None = None
) -> Image.Image:
    png = resvg_py.svg_to_bytes(svg_string=svg, width=width, height=height, background=background)
    return Image.open(io.BytesIO(bytes(png))).convert("RGBA")


def iou(a: Image.Image, b: Image.Image, threshold: int = 128) -> float:
    """Intersection-over-union of two 'L' masks of the same size."""
    ma = a.point(lambda v: 255 if v >= threshold else 0)
    mb = b.point(lambda v: 255 if v >= threshold else 0)
    inter = ImageChops.multiply(ma, mb).histogram()[255]
    union = ImageChops.lighter(ma, mb).histogram()[255]
    return inter / union if union else 0.0


_SRGB = ImageCms.createProfile("sRGB")
_LAB = ImageCms.createProfile("LAB")
_TO_LAB = ImageCms.buildTransform(_SRGB, _LAB, "RGB", "LAB")


def mean_delta_e(a: Image.Image, b: Image.Image, mask: Image.Image) -> float:
    """Mean CIE76 ΔE between two RGB images over the mask's opaque pixels."""
    la = ImageCms.applyTransform(a.convert("RGB"), _TO_LAB)
    lb = ImageCms.applyTransform(b.convert("RGB"), _TO_LAB)
    assert la is not None and lb is not None
    total = 0.0
    count = 0
    for pa, pb, m in zip(
        la.get_flattened_data(), lb.get_flattened_data(), mask.get_flattened_data(), strict=True
    ):
        if m < 250:
            continue
        dl = (pa[0] - pb[0]) * 100 / 255
        da = pa[1] - pb[1]
        db = pa[2] - pb[2]
        total += (dl * dl + da * da + db * db) ** 0.5
        count += 1
    return total / count if count else 0.0


WORDMARK_LIGHT = "#12172A"  # the logo's own navy, for "estify" on light surfaces


def light_lockup(on_dark_svg: str) -> str:
    """The light lockup is the on-dark one with "estify" recoloured — one
    fill swap, so the two variants can never drift apart (design Decision 1)."""
    light, count = re.subn(
        r'(<g id="gfy-wordmark-rest" fill=")#[0-9A-Fa-f]{6}(")',
        rf"\g<1>{WORDMARK_LIGHT}\g<2>",
        on_dark_svg,
    )
    assert count == 1, "on-dark lockup has no gfy-wordmark-rest group"
    return light
