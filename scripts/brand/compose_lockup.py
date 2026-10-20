"""Composes `brand/guestify-lockup-on-dark.svg` from the traced mark and
the fitted wordmark (rebrand-to-guestify design.md Decisions 1 and 3).

    ddev exec uv run python scripts/brand/compose_lockup.py

Run after `trace_mark.py` and `match_wordmark.py`. Both already share the
lockup coordinate system, so the mark-to-wordmark gap and the baseline come
straight from the source with no manual placement. Also copies the winning
font's OFL licence to `brand/OFL.txt`, which the licence requires to travel
with the derived outlines.

The light lockup is deliberately not written here: `build_brand_assets.py`
derives it from this file by swapping one fill, so the two can't drift.
"""

import json
import re
from collections import Counter

from _common import BRAND_DIR, LOCKUP_BOX, iou, render_svg
from match_wordmark import Fit, glyph_paths, licence_text, load_font, source_wordmark

WORDMARK_ON_DARK = "#FFFFFF"
# "Gu" are the first two letters; the rest are "estify".
_TEAL_LETTERS = 2


def _sample_teal() -> str:
    """Most common opaque colour of the source's "Gu", rounded to the
    nearest 4 per channel so compression noise doesn't split the vote."""
    window, alpha, runs, _, _ = source_wordmark()
    votes: Counter[tuple[int, int, int]] = Counter()
    for r0, r1 in runs[:_TEAL_LETTERS]:
        box = (r0, 0, r1, window.height)
        for rgb, a in zip(
            window.crop(box).get_flattened_data(), alpha.crop(box).get_flattened_data(), strict=True
        ):
            if a == 255:
                votes[(rgb[0] // 4 * 4, rgb[1] // 4 * 4, rgb[2] // 4 * 4)] += 1
    (r, g, b), _ = votes.most_common(1)[0]
    return f"#{r + 2:02X}{g + 2:02X}{b + 2:02X}"


def _mark_body() -> tuple[str, str]:
    """The mark SVG's inner markup (defs + group), without its root tag."""
    svg = (BRAND_DIR / "guestify-mark.svg").read_text()
    inner = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S)
    assert inner is not None
    return inner.group(1).strip("\n"), svg


def compose() -> str:
    fit = Fit(**json.loads((BRAND_DIR / "wordmark-fit.json").read_text()))
    font = load_font(fit.family, fit.weight)
    paths = glyph_paths(font, fit)
    teal = _sample_teal()
    mark, _ = _mark_body()
    width = LOCKUP_BOX[2] - LOCKUP_BOX[0]
    height = LOCKUP_BOX[3] - LOCKUP_BOX[1]
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}">',
            "  <title>Guestify</title>",
            mark,
            f'  <g id="gfy-wordmark-teal" fill="{teal}">',
            *(f"    {p}" for p in paths[:_TEAL_LETTERS]),
            "  </g>",
            # build_brand_assets.py swaps this group's fill for the light lockup.
            f'  <g id="gfy-wordmark-rest" fill="{WORDMARK_ON_DARK}">',
            *(f"    {p}" for p in paths[_TEAL_LETTERS:]),
            "  </g>",
            "</svg>",
        ]
    ), fit.repo_dir


def main() -> None:
    svg, repo_dir = compose()
    out = BRAND_DIR / "guestify-lockup-on-dark.svg"
    out.write_text(svg + "\n")
    (BRAND_DIR / "OFL.txt").write_text(licence_text(repo_dir))
    print(f"wrote {out} ({len(svg) // 1024} KB) and {BRAND_DIR / 'OFL.txt'}")

    # Whole-lockup silhouette check against the source.
    from _common import background_colour, key_alpha, load_source

    source = load_source()
    alpha = key_alpha(source.crop(LOCKUP_BOX), background_colour(source))
    rendered = render_svg(svg).getchannel("A")
    print(f"lockup IoU {iou(rendered, alpha):.4f}")


if __name__ == "__main__":
    main()
