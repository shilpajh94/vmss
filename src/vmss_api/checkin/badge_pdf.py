"""PDF badge renderer for the badge print flow (add-badge-print-flow design
Decision 6). Pillow composes the page and saves it as PDF, so there's no new
dependency. Entirely separate from `invitations/badge.py` (the PNG badge),
which is untouched. The blocking composition runs via
`anyio.to_thread.run_sync` (fastapi-architecture.md §4).
"""

import io
from datetime import date

import anyio
from PIL import Image, ImageDraw, ImageFont, ImageOps

from vmss_api.invitations.qr import generate_qr_png

# A6 portrait at 300 dpi.
_WIDTH = 1240
_HEIGHT = 1748
_MARGIN = 90
_HEADER_HEIGHT = 280
_PHOTO_SIZE = 420
_QR_SIZE = 400

_INK = (17, 24, 39)
_MUTED = (107, 114, 128)
_BRAND = (15, 42, 74)
_RULE = (209, 213, 219)
_ON_BRAND = (255, 255, 255)
_ON_BRAND_MUTED = (191, 207, 228)
_ACCENT = (245, 158, 11)
_CARD = (243, 246, 250)


_Font = ImageFont.FreeTypeFont | ImageFont.ImageFont
_Color = tuple[int, int, int]


def _font(size: int) -> _Font:
    return ImageFont.load_default(size=size)


def _fit(
    draw: ImageDraw.ImageDraw, text: str, *, size: int, max_width: int, min_size: int = 44
) -> tuple[str, _Font]:
    """Largest font (down to `min_size`) at which `text` fits `max_width`;
    past that the text is clipped with an ellipsis, so a pathological 255-char
    name can't push the QR off the page."""
    min_size = min(min_size, size)
    while size >= min_size:
        font = _font(size)
        if draw.textlength(text, font=font) <= max_width:
            return text, font
        size -= 4
    font = _font(min_size)
    while text and draw.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return text + "…", font


def _centered(
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    *,
    size: int,
    fill: _Color,
    max_width: int = _WIDTH - 2 * _MARGIN,
    bold: bool = False,
    center_x: float = _WIDTH / 2,
) -> int:
    """Draws `text` centred at `y` and returns the y just below it."""
    fitted, font = _fit(draw, text, size=size, max_width=max_width)
    width = draw.textlength(fitted, font=font)
    draw.text(
        (center_x - width / 2, y),
        fitted,
        font=font,
        fill=fill,
        stroke_width=2 if bold else 0,
        stroke_fill=fill,
    )
    return y + int(font.size * 1.25) if hasattr(font, "size") else y + size


def _compose(
    *,
    visitor_name: str,
    host_name: str,
    visit_date: date,
    photo_bytes: bytes,
    qr_png: bytes,
    organisation_name: str | None = None,
    tracking_id: str | None = None,
) -> bytes:
    canvas = Image.new("RGB", (_WIDTH, _HEIGHT), "white")
    draw = ImageDraw.Draw(canvas)

    # Header band: organisation (small) over the badge type.
    top, bottom = (10, 28, 52), (24, 64, 112)
    for row in range(_HEADER_HEIGHT):
        t = row / _HEADER_HEIGHT
        draw.line(
            (0, row, _WIDTH, row),
            fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom, strict=True)),
        )
    # Soft decorative rings, clipped to the header band.
    rings = Image.new("RGBA", (_WIDTH, _HEADER_HEIGHT), (0, 0, 0, 0))
    ring_draw = ImageDraw.Draw(rings)
    for cx, cy in ((_WIDTH - 60, 40), (80, _HEADER_HEIGHT - 20)):
        for r in (110, 170, 230):
            ring_draw.ellipse(
                (cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 22), width=4
            )
    canvas.paste(rings, (0, 0), rings)
    draw.rectangle((0, _HEADER_HEIGHT, _WIDTH, _HEADER_HEIGHT + 14), fill=_ACCENT)
    # Lanyard slot.
    draw.rounded_rectangle(
        ((_WIDTH - 220) // 2, 18, (_WIDTH + 220) // 2, 48), radius=15, fill=_ON_BRAND_MUTED
    )
    draw.rounded_rectangle(
        ((_WIDTH - 200) // 2, 22, (_WIDTH + 200) // 2, 44), radius=11, fill=(10, 28, 52)
    )
    title_y = 74
    if organisation_name:
        title_y = _centered(draw, 64, organisation_name.upper(), size=48, fill=_ON_BRAND_MUTED)
        title_y -= 10
    _centered(draw, title_y + 10, "VISITOR", size=140, fill=_ON_BRAND, bold=True)

    # Photo, centred, with a hairline frame.
    photo_x = (_WIDTH - _PHOTO_SIZE) // 2
    photo_y = _HEADER_HEIGHT + 50
    radius = 40
    photo = ImageOps.fit(
        Image.open(io.BytesIO(photo_bytes)).convert("RGB"), (_PHOTO_SIZE, _PHOTO_SIZE)
    )
    mask = Image.new("L", (_PHOTO_SIZE, _PHOTO_SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, _PHOTO_SIZE - 1, _PHOTO_SIZE - 1), radius=radius, fill=255
    )
    canvas.paste(photo, (photo_x, photo_y), mask)
    draw.rounded_rectangle(
        (photo_x - 6, photo_y - 6, photo_x + _PHOTO_SIZE + 5, photo_y + _PHOTO_SIZE + 5),
        radius=radius + 6,
        outline=_BRAND,
        width=6,
    )

    # Name, then labelled details: host and date side by side, visit id below.
    y = photo_y + _PHOTO_SIZE + 40
    # Fixed advance (not the fitted font's height) so every badge lays out alike.
    _centered(draw, y, visitor_name, size=100, fill=_INK, bold=True)
    y += 125
    draw.rounded_rectangle(
        (_MARGIN, y, _WIDTH - _MARGIN, y + 262), radius=28, fill=_CARD, outline=_RULE, width=2
    )
    draw.line((_WIDTH // 2, y + 24, _WIDTH // 2, y + 112), fill=_RULE, width=3)
    y += 26
    column_width = (_WIDTH - 2 * _MARGIN) // 2 - 20
    left_x = _MARGIN + column_width / 2
    right_x = _WIDTH - _MARGIN - column_width / 2
    for label, value, x in (
        ("HOST", host_name, left_x),
        ("DATE", visit_date.strftime("%d %b %Y"), right_x),
    ):
        _centered(draw, y, label, size=34, fill=_MUTED, max_width=column_width, center_x=x)
        _centered(draw, y + 42, value, size=56, fill=_INK, max_width=column_width, center_x=x)
    y += 120
    if tracking_id:
        _centered(draw, y, "VISIT ID", size=34, fill=_MUTED)
        _centered(draw, y + 42, tracking_id, size=56, fill=_INK)

    # QR pinned to the bottom with a caption.
    qr_top = _HEIGHT - _QR_SIZE - 140
    qr = Image.open(io.BytesIO(qr_png)).convert("RGB").resize((_QR_SIZE, _QR_SIZE))
    qr_x = (_WIDTH - _QR_SIZE) // 2
    draw.rounded_rectangle(
        (qr_x - 14, qr_top - 14, qr_x + _QR_SIZE + 14, qr_top + _QR_SIZE + 14),
        radius=24,
        outline=_RULE,
        width=3,
    )
    canvas.paste(qr, (qr_x, qr_top))
    _centered(draw, qr_top + _QR_SIZE + 16, "Scan at the exit to check out", size=40, fill=_MUTED)
    _centered(draw, qr_top + _QR_SIZE + 70, "Valid on the date shown only", size=34, fill=_MUTED)

    # Footer bar and outer frame.
    draw.rectangle((0, _HEIGHT - 18, _WIDTH, _HEIGHT), fill=_BRAND)
    draw.rectangle((0, _HEIGHT - 24, _WIDTH, _HEIGHT - 18), fill=_ACCENT)
    draw.rectangle((0, 0, _WIDTH - 1, _HEIGHT - 1), outline=_RULE, width=4)

    buffer = io.BytesIO()
    canvas.save(buffer, format="PDF", resolution=300.0)
    return buffer.getvalue()


async def render_badge_pdf(
    *,
    visitor_name: str,
    host_name: str,
    visit_date: date,
    photo_bytes: bytes,
    qr_token: str,
    organisation_name: str | None = None,
    tracking_id: str | None = None,
) -> bytes:
    qr_png = await generate_qr_png(qr_token)
    return await anyio.to_thread.run_sync(
        lambda: _compose(
            visitor_name=visitor_name,
            host_name=host_name,
            visit_date=visit_date,
            photo_bytes=photo_bytes,
            qr_png=qr_png,
            organisation_name=organisation_name,
            tracking_id=tracking_id,
        )
    )
