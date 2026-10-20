"""Finds the open-licence font that best reproduces the supplied "Guestify"
wordmark and records the fit in `brand/wordmark-fit.json`
(rebrand-to-guestify design.md Decision 3).

    ddev exec uv run python scripts/brand/match_wordmark.py

Each candidate is scored with the exact geometry the master will use: the
glyphs are converted to SVG outlines with fontTools, each one centred on
the matching letter of the source, size and baseline fitted, rendered with
resvg, and compared with the keyed source wordmark by alpha-mask IoU.

Fonts are downloaded from the google/fonts repo into a scratch cache, never
vendored; only the winner's OFL licence is copied into `brand/`.
"""

import json
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from _common import (
    BRAND_DIR,
    LOCKUP_BOX,
    WORDMARK_LEFT,
    background_colour,
    iou,
    key_alpha,
    load_source,
    render_svg,
)
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

TEXT = "Guestify"
WORDMARK_IOU_MIN = 0.93
_FAIL_HINT = "FAIL — trace the wordmark instead (design Decision 3)"
FONT_CACHE = Path("/tmp/guestify-brand-fonts")
_GF = "https://raw.githubusercontent.com/google/fonts/main/ofl"

# (family, weight) -> (repo dir, file). Variable fonts are instanced at the
# requested weight; static families name the weight's own file.
CANDIDATES: dict[tuple[str, int], tuple[str, str]] = {
    ("Poppins", 800): ("poppins", "Poppins-ExtraBold.ttf"),
    ("Poppins", 700): ("poppins", "Poppins-Bold.ttf"),
    ("Outfit", 800): ("outfit", "Outfit[wght].ttf"),
    ("Outfit", 700): ("outfit", "Outfit[wght].ttf"),
    ("Plus Jakarta Sans", 800): ("plusjakartasans", "PlusJakartaSans[wght].ttf"),
    ("Plus Jakarta Sans", 700): ("plusjakartasans", "PlusJakartaSans[wght].ttf"),
    ("Urbanist", 800): ("urbanist", "Urbanist[wght].ttf"),
    ("Urbanist", 700): ("urbanist", "Urbanist[wght].ttf"),
    ("Lexend", 800): ("lexend", "Lexend[wght].ttf"),
    ("Lexend", 700): ("lexend", "Lexend[wght].ttf"),
    ("Montserrat", 800): ("montserrat", "Montserrat[wght].ttf"),
    ("Montserrat", 700): ("montserrat", "Montserrat[wght].ttf"),
}

# The wordmark window, in source pixels.
_WINDOW = (WORDMARK_LEFT - 20, LOCKUP_BOX[1] - 10, LOCKUP_BOX[2] + 10, LOCKUP_BOX[3] + 10)


@dataclass
class Fit:
    family: str
    weight: int
    repo_dir: str
    scale: float  # source px per font unit
    baseline: float  # lockup-coordinate y of the baseline
    x: list[float]  # lockup-coordinate x of each glyph's origin
    iou: float


def _download(repo_dir: str, name: str) -> Path:
    FONT_CACHE.mkdir(parents=True, exist_ok=True)
    path = FONT_CACHE / f"{repo_dir}__{name}"
    if not path.exists():
        url = f"{_GF}/{repo_dir}/{urllib.request.quote(name)}"
        urllib.request.urlretrieve(url, path)  # noqa: S310 - fixed https host
    return path


def load_font(family: str, weight: int) -> TTFont:
    repo_dir, name = CANDIDATES[(family, weight)]
    font = TTFont(_download(repo_dir, name))
    if "fvar" in font:
        font = instantiateVariableFont(font, {"wght": weight})
    return font


def licence_text(repo_dir: str) -> str:
    return _download(repo_dir, "OFL.txt").read_text()


def _letter_runs(alpha_window) -> list[tuple[int, int]]:  # type: ignore[no-untyped-def]
    """Ink column runs (window x) — one per letter of TEXT."""
    w, h = alpha_window.size
    col_ink = [alpha_window.crop((x, 0, x + 1, h)).getextrema()[1] >= 128 for x in range(w)]
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for x, ink in enumerate([*col_ink, False]):
        if ink and start is None:
            start = x
        elif not ink and start is not None:
            if x - start > 3:
                runs.append((start, x))
            start = None
    assert len(runs) == len(TEXT), f"expected {len(TEXT)} letter runs, got {len(runs)}"
    return runs


def _glyphs(font: TTFont) -> list[tuple[str, tuple[float, float, float, float]]]:
    cmap = font.getBestCmap()
    glyph_set = font.getGlyphSet()
    out = []
    for ch in TEXT:
        name = cmap[ord(ch)]
        pen = BoundsPen(glyph_set)
        glyph_set[name].draw(pen)
        assert pen.bounds is not None
        out.append((name, pen.bounds))
    return out


def glyph_paths(font: TTFont, fit: Fit) -> list[str]:
    """One SVG path `d` per letter, already in lockup coordinates."""
    glyph_set = font.getGlyphSet()
    out = []
    for (name, _), x in zip(_glyphs(font), fit.x, strict=True):
        pen = SVGPathPen(glyph_set, lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
        glyph_set[name].draw(pen)
        out.append((pen.getCommands(), x))
    return [
        f'<path transform="translate({x:.2f} {fit.baseline:.2f}) '
        f'scale({fit.scale:.6f} {-fit.scale:.6f})" d="{d}"/>'
        for d, x in out
    ]


def _wordmark_svg(paths: list[str]) -> str:
    wx, wy = _WINDOW[0] - LOCKUP_BOX[0], _WINDOW[1] - LOCKUP_BOX[1]
    ww, wh = _WINDOW[2] - _WINDOW[0], _WINDOW[3] - _WINDOW[1]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{wx} {wy} {ww} {wh}" '
        f'width="{ww}" height="{wh}">'
        f'<g fill="#000">{"".join(paths)}</g></svg>'
    )


def fit_font(family: str, weight: int, target, runs, ink_top: int, ink_base: int) -> Fit:  # type: ignore[no-untyped-def]
    font = load_font(family, weight)
    glyphs = _glyphs(font)
    lx, ly = _WINDOW[0] - LOCKUP_BOX[0], _WINDOW[1] - LOCKUP_BOX[1]
    # Initial scale: the "i" (dot top to stem bottom) spans the source's
    # full x-height-plus-dot; it has no overshoot, unlike round letters.
    i_index = TEXT.index("i")
    _, (_, i_ymin, _, i_ymax) = glyphs[i_index]
    base_scale = (ink_base - ink_top) / (i_ymax - i_ymin)

    def build(scale: float, baseline_nudge: float) -> Fit:
        baseline = ly + ink_base + i_ymin * scale + baseline_nudge
        xs = []
        for (_, (xmin, _, xmax, _)), (r0, r1) in zip(glyphs, runs, strict=True):
            centre = lx + (r0 + r1) / 2
            xs.append(centre - (xmin + xmax) / 2 * scale)
        return Fit(family, weight, CANDIDATES[(family, weight)][0], scale, baseline, xs, 0.0)

    best: Fit | None = None
    for step in range(-6, 7):
        for nudge in (-2.0, -1.0, 0.0, 1.0, 2.0):
            fit = build(base_scale * (1 + step * 0.005), nudge)
            rendered = render_svg(_wordmark_svg(glyph_paths(font, fit))).getchannel("A")
            fit.iou = iou(rendered, target)
            if best is None or fit.iou > best.iou:
                best = fit
    assert best is not None
    return best


def source_wordmark():  # type: ignore[no-untyped-def]
    source = load_source()
    window = source.crop(_WINDOW)
    alpha = key_alpha(window, background_colour(source))
    runs = _letter_runs(alpha)
    i0, i1 = runs[TEXT.index("i")]
    i_bbox = alpha.crop((i0, 0, i1, alpha.height)).point(lambda a: 255 if a >= 128 else 0).getbbox()
    assert i_bbox is not None
    return window, alpha, runs, i_bbox[1], i_bbox[3]


def main() -> None:
    _, target, runs, ink_top, ink_base = source_wordmark()
    fits = []
    for family, weight in CANDIDATES:
        fit = fit_font(family, weight, target, runs, ink_top, ink_base)
        fits.append(fit)
        print(f"  {family:<18} {weight}  IoU {fit.iou:.4f}")
    fits.sort(key=lambda f: f.iou, reverse=True)
    best = fits[0]
    ok = best.iou >= WORDMARK_IOU_MIN
    print(
        f"best: {best.family} {best.weight}, IoU {best.iou:.4f} "
        f"(≥ {WORDMARK_IOU_MIN}) → {'PASS' if ok else _FAIL_HINT}"
    )
    BRAND_DIR.mkdir(exist_ok=True)
    out = BRAND_DIR / "wordmark-fit.json"
    out.write_text(json.dumps(asdict(best), indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
