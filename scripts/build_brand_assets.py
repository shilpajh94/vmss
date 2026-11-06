"""Generates the Visimio brand PNGs from the supplied raster logo
(refine-email-templates-and-visimio-brand design.md Decision 5). Run once
and commit the outputs, since nothing calls this at request or build time.

    ddev exec uv run python scripts/build_brand_assets.py
    ddev exec uv run python scripts/build_brand_assets.py --web-out ../VMMS_WEB

The source has a cyan mark and a dark (#0E1527) wordmark on a transparent
background. The "on-dark" variants recolour that wordmark to white, keeping
each pixel's alpha, so antialiased edges fade to transparent rather than
leaving a dark halo on the navy header/sidebars.
"""

import argparse
from pathlib import Path

from PIL import Image

_ROOT = Path(__file__).resolve().parent.parent
_SOURCE = _ROOT / "src/vmss_api/core/email_assets/visimio-logo-source.png"
_EMAIL_OUT = _ROOT / "src/vmss_api/core/email_assets/visimio-logo-on-dark.png"

_WORDMARK_RGB = (14, 21, 39)  # #0E1527
_WORDMARK_TOLERANCE = 90  # max Euclidean RGB distance still treated as wordmark


def _trim(image: Image.Image) -> Image.Image:
    bbox = image.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    assert bbox is not None, "source logo is fully transparent"
    return image.crop(bbox)


def _is_wordmark(r: int, g: int, b: int) -> bool:
    wr, wg, wb = _WORDMARK_RGB
    return ((r - wr) ** 2 + (g - wg) ** 2 + (b - wb) ** 2) ** 0.5 <= _WORDMARK_TOLERANCE


def _on_dark(image: Image.Image) -> Image.Image:
    out = image.copy()
    pixels = out.load()
    assert pixels is not None
    width, height = out.size
    for x in range(width):
        for y in range(height):
            r, g, b, a = pixels[x, y]
            if a and _is_wordmark(r, g, b):
                pixels[x, y] = (255, 255, 255, a)
    return out


def _mark(image: Image.Image) -> Image.Image:
    """The mark is the leftmost opaque run of columns, ending at the first
    fully transparent column gap before the wordmark starts.
    """
    alpha = image.getchannel("A")
    width, height = image.size
    started = False
    for x in range(width):
        column_opaque = any(alpha.getpixel((x, y)) > 8 for y in range(height))
        if column_opaque:
            started = True
        elif started:
            return _trim(image.crop((0, 0, x, height)))
    return image


def _resize_to_height(image: Image.Image, height: int) -> Image.Image:
    width = round(image.width * height / image.height)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)
    print(f"wrote {path} ({image.width}x{image.height}, {path.stat().st_size // 1024} KB)")


def _square_icon(
    mark: Image.Image, size: int, *, background: tuple[int, int, int, int]
) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), background)
    inner = round(size * 0.72)
    scaled = mark.copy()
    scaled.thumbnail((inner, inner), Image.Resampling.LANCZOS)
    canvas.alpha_composite(scaled, ((size - scaled.width) // 2, (size - scaled.height) // 2))
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--web-out", type=Path, help="VMMS_WEB repo root to also write portal assets into"
    )
    args = parser.parse_args()

    lockup = _trim(Image.open(_SOURCE).convert("RGBA"))
    on_dark = _on_dark(lockup)
    mark = _mark(lockup)

    # Email header: 64px tall, displayed at 32px (2x for high-DPI clients).
    _save(_resize_to_height(on_dark, 64), _EMAIL_OUT)

    if args.web_out:
        brand = args.web_out / "src/assets/brand"
        for name, image, height in [
            ("logo-visimio", lockup, 32),
            ("logo-visimio-on-dark", on_dark, 32),
            ("logo-visimio-mark", mark, 28),
        ]:
            _save(_resize_to_height(image, height), brand / f"{name}.png")
            _save(_resize_to_height(image, height * 2), brand / f"{name}@2x.png")
        public = args.web_out / "public"
        _save(_square_icon(mark, 48, background=(0, 0, 0, 0)), public / "favicon.png")
        _save(_square_icon(mark, 32, background=(0, 0, 0, 0)), public / "favicon-32.png")
        _save(
            _square_icon(mark, 180, background=(255, 255, 255, 255)),
            public / "apple-touch-icon.png",
        )


if __name__ == "__main__":
    main()
