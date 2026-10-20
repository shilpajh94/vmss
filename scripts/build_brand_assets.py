"""Generates every Guestify brand asset from the SVG masters in `brand/`
(rebrand-to-guestify design.md Decision 4). Run once and commit the
outputs, since nothing calls this at request or build time.

    ddev exec uv run python scripts/build_brand_assets.py
    ddev exec uv run python scripts/build_brand_assets.py --web-out .brand-web-out --preview <png>
    cp -r .brand-web-out/. ../VMMS_WEB/ && rm -r .brand-web-out

(`../VMMS_WEB` isn't mounted inside the DDEV container, so web outputs are
staged in this repo and copied across from the host.)

Rasters are rendered with resvg straight from vector at their exact target
size, with no keying or recolouring of a noisy source. The light lockup
is derived from the on-dark master by one fill swap (`light_lockup`). The
web gets SVGs rather than PNGs. Their embedded shading image is
re-encoded small: the shading is soft, and every edge is vector, so a
full-resolution copy would only add weight.
"""

import argparse
import base64
import io
import re
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent / "brand"))

from _common import BRAND_DIR, light_lockup, render_svg  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_EMAIL_OUT = _ROOT / "src/vmss_api/core/email_assets/guestify-logo-on-dark.png"

# Intrinsic display heights for the web SVGs: what the portal's 1x slots
# render at, so `BrandLogo`'s `max-w-fit` keeps its meaning.
_WEB_LOCKUP_HEIGHT = 32
_WEB_MARK_HEIGHT = 28
# Embedded shading cap for web/favicon SVGs: 4x the largest slot.
_WEB_SHADING_MAX_PX = 256
_WEB_SHADING_QUALITY = 86

# Where the G counter sits, as a fraction of the mark's width/height — a
# favicon whose counter fills in reads as a blob, not a G.
_COUNTER_CENTRE = (0.33, 0.40)

_IMAGE_RE = re.compile(r'href="data:image/jpeg;base64,([^"]+)"')
_ROOT_SIZE_RE = re.compile(r'(<svg[^>]*?) width="[^"]*" height="[^"]*"')
_VIEWBOX_RE = re.compile(r'viewBox="([^"]+)"')


def _viewbox(svg: str) -> tuple[float, float, float, float]:
    match = _VIEWBOX_RE.search(svg)
    assert match is not None
    x, y, w, h = (float(v) for v in match.group(1).split())
    return x, y, w, h


def _with_intrinsic_height(svg: str, height: int) -> str:
    _, _, w, h = _viewbox(svg)
    width = round(w * height / h)
    return _ROOT_SIZE_RE.sub(rf'\g<1> width="{width}" height="{height}"', svg, count=1)


def _slim(svg: str, max_px: int = _WEB_SHADING_MAX_PX) -> str:
    """Re-encode the embedded shading image at most `max_px` on its long
    side. The `<image>` element's own width/height are unchanged, so the
    layout is identical; only the pixel density of the soft fill drops."""

    def shrink(match: re.Match[str]) -> str:
        image = Image.open(io.BytesIO(base64.b64decode(match.group(1)))).convert("RGB")
        image.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=_WEB_SHADING_QUALITY, optimize=True)
        return f'href="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"'

    return _IMAGE_RE.sub(shrink, svg)


def _square(svg: str, padding: float) -> str:
    """The mark centred in a square viewBox, `padding` × side on each edge."""
    x, y, w, h = _viewbox(svg)
    side = max(w, h) / (1 - 2 * padding)
    sx, sy = x + w / 2 - side / 2, y + h / 2 - side / 2
    svg = _VIEWBOX_RE.sub(f'viewBox="{sx:.2f} {sy:.2f} {side:.2f} {side:.2f}"', svg, count=1)
    return _ROOT_SIZE_RE.sub(r'\g<1> width="64" height="64"', svg, count=1)


def _square_icon(mark: str, size: int, *, padding: float, background: str | None) -> Image.Image:
    return render_svg(_square(mark, padding), width=size, height=size, background=background)


def _assert_counter_open(mark: str, size: int, padding: float) -> None:
    icon = _square_icon(mark, size, padding=padding, background=None)
    _, _, w, h = _viewbox(mark)
    side = max(w, h) / (1 - 2 * padding)
    scale = size / side
    cx = size / 2 + (_COUNTER_CENTRE[0] - 0.5) * w * scale
    cy = size / 2 + (_COUNTER_CENTRE[1] - 0.5) * h * scale
    alpha = icon.getchannel("A").getpixel((round(cx), round(cy)))
    assert isinstance(alpha, int) and alpha < 128, (
        f"{size}px favicon: G counter filled in (alpha {alpha}) — increase padding"
    )


def _save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)
    print(f"wrote {path} ({image.width}x{image.height}, {path.stat().st_size // 1024} KB)")


def _save_svg(svg: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg + ("" if svg.endswith("\n") else "\n"))
    print(f"wrote {path} ({path.stat().st_size // 1024} KB)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--web-out", type=Path, help="VMMS_WEB repo root to also write portal assets into"
    )
    parser.add_argument("--preview", type=Path, help="also write the approval preview sheet here")
    args = parser.parse_args()

    on_dark = (BRAND_DIR / "guestify-lockup-on-dark.svg").read_text()
    light = light_lockup(on_dark)
    mark = (BRAND_DIR / "guestify-mark.svg").read_text()

    # Email header: 64px tall, displayed at 32px (2x for high-DPI clients).
    _save_png(render_svg(on_dark, height=64), _EMAIL_OUT)

    favicon_padding = 0.06
    for size in (16, 32):
        _assert_counter_open(mark, size, favicon_padding)

    if args.web_out:
        brand = args.web_out / "src/assets/brand"
        for name, svg, height in [
            ("logo-guestify", light, _WEB_LOCKUP_HEIGHT),
            ("logo-guestify-on-dark", on_dark, _WEB_LOCKUP_HEIGHT),
            ("logo-guestify-mark", mark, _WEB_MARK_HEIGHT),
        ]:
            _save_svg(_with_intrinsic_height(_slim(svg), height), brand / f"{name}.svg")
        public = args.web_out / "public"
        _save_svg(_slim(_square(mark, favicon_padding), 128), public / "favicon.svg")
        _save_png(
            _square_icon(mark, 48, padding=favicon_padding, background=None),
            public / "favicon.png",
        )
        _save_png(
            _square_icon(mark, 32, padding=favicon_padding, background=None),
            public / "favicon-32.png",
        )
        _save_png(
            _square_icon(mark, 180, padding=0.14, background="#ffffff"),
            public / "apple-touch-icon.png",
        )

    if args.preview:
        from preview import build_sheet

        build_sheet().convert("RGB").save(args.preview)
        print(f"wrote {args.preview}")


if __name__ == "__main__":
    main()
