"""Renders the approval sheet for the logo masters: the supplied raster,
the on-dark master on navy, the derived light lockup on white, and the
small sizes the product actually uses (rebrand-to-guestify task 2.7).

    ddev exec uv run python scripts/brand/preview.py --out <png>

`--with-vector-alt` adds the pure-vector-shading mark for comparison.
"""

import argparse
from pathlib import Path

from _common import BRAND_DIR, LOCKUP_BOX, light_lockup, load_source, render_svg
from PIL import Image, ImageDraw

NAVY = (15, 23, 42, 255)  # #0f172a — portal sidebar / email header band
WHITE = (255, 255, 255, 255)
_GAP = 24
_LABEL_H = 22


def _labelled(image: Image.Image, label: str, bg: tuple[int, int, int, int]) -> Image.Image:
    tile = Image.new("RGBA", (image.width + 2 * _GAP, image.height + _LABEL_H + 2 * _GAP), bg)
    tile.alpha_composite(image, (_GAP, _GAP + _LABEL_H))
    text = (148, 163, 184) if bg == NAVY else (71, 85, 105)
    ImageDraw.Draw(tile).text((_GAP, _GAP // 2), label, fill=text)
    return tile


def _row(tiles: list[Image.Image]) -> Image.Image:
    row = Image.new("RGBA", (sum(t.width for t in tiles), max(t.height for t in tiles)), WHITE)
    x = 0
    for t in tiles:
        row.alpha_composite(t, (x, 0))
        x += t.width
    return row


def build_sheet(vector_alt_svg: str | None = None) -> Image.Image:
    on_dark = (BRAND_DIR / "guestify-lockup-on-dark.svg").read_text()
    light = light_lockup(on_dark)
    mark = (BRAND_DIR / "guestify-mark.svg").read_text()

    big_h = 220
    original = load_source().crop(LOCKUP_BOX).convert("RGBA")
    original = original.resize(
        (round(original.width * big_h / original.height), big_h), Image.Resampling.LANCZOS
    )
    rows = [
        _row(
            [
                _labelled(original, "ORIGINAL (supplied raster)", NAVY),
                _labelled(
                    render_svg(on_dark, height=big_h), "NEW on-dark master (on #0f172a)", NAVY
                ),
            ]
        ),
        _row([_labelled(render_svg(light, height=big_h), "NEW light lockup (on white)", WHITE)]),
    ]

    small: list[Image.Image] = []
    for h in (64, 32):
        small.append(_labelled(render_svg(on_dark, height=h), f"on-dark {h}px", NAVY))
        small.append(_labelled(render_svg(light, height=h), f"light {h}px", WHITE))
    rows.append(_row(small))

    marks: list[Image.Image] = []
    for h in (180, 64, 32, 16):
        marks.append(_labelled(render_svg(mark, height=h), f"mark {h}px", NAVY))
        marks.append(_labelled(render_svg(mark, height=h), f"mark {h}px", WHITE))
    rows.append(_row(marks))

    if vector_alt_svg is not None:
        rows.append(
            _row(
                [
                    _labelled(
                        render_svg(mark, height=300),
                        "CHOSEN mark: vector edges + image shading",
                        NAVY,
                    ),
                    _labelled(
                        render_svg(vector_alt_svg, height=300),
                        "ALTERNATIVE: pure-vector shading",
                        NAVY,
                    ),
                ]
            )
        )

    sheet = Image.new("RGBA", (max(r.width for r in rows), sum(r.height for r in rows)), WHITE)
    y = 0
    for r in rows:
        sheet.alpha_composite(r, (0, y))
        y += r.height
    return sheet


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--with-vector-alt", action="store_true")
    args = parser.parse_args()
    alt = None
    if args.with_vector_alt:
        from trace_mark import trace_mark

        alt, _ = trace_mark("vector")
    build_sheet(alt).convert("RGB").save(args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
