"""Badge image rendering for `POST /invitations/{id}/badge`
(add-invitation-lifecycle-actions/design.md Decision 3): a simple PNG
composited with Pillow — no new dependency, since `qrcode[pil]` already
pulls Pillow in transitively (`qr.py`). Reuses `qr.py::generate_qr_png` for
the QR portion rather than duplicating QR generation. Deliberately simple —
fixed layout, the bundled default font, no per-tenant branding (design.md
Risks/Trade-offs) — a template/branding system is future work.
"""

import io
from datetime import datetime

import anyio
from PIL import Image, ImageDraw, ImageFont

from vmss_api.invitations.qr import generate_qr_png

_WIDTH = 600
_HEIGHT = 350
_QR_SIZE = 220
_MARGIN = 20


def _composite(
    *, tracking_id: str, primary_contact_full_name: str, expires_at: datetime, qr_png: bytes
) -> bytes:
    canvas = Image.new("RGB", (_WIDTH, _HEIGHT), "white")
    draw = ImageDraw.Draw(canvas)
    title_font = ImageFont.load_default(size=28)
    body_font = ImageFont.load_default(size=18)

    draw.text((_MARGIN, _MARGIN), "VISITOR BADGE", font=title_font, fill="black")
    draw.text((_MARGIN, 70), primary_contact_full_name, font=body_font, fill="black")
    draw.text((_MARGIN, 100), f"Tracking ID: {tracking_id}", font=body_font, fill="black")
    draw.text(
        (_MARGIN, 130),
        f"Valid until: {expires_at.strftime('%Y-%m-%d %H:%M UTC')}",
        font=body_font,
        fill="black",
    )

    qr_image = Image.open(io.BytesIO(qr_png)).convert("RGB").resize((_QR_SIZE, _QR_SIZE))
    canvas.paste(qr_image, (_WIDTH - _QR_SIZE - _MARGIN, _HEIGHT - _QR_SIZE - _MARGIN))

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


async def render_badge_png(
    *, tracking_id: str, primary_contact_full_name: str, expires_at: datetime
) -> bytes:
    """Renders (or re-renders, for a reprint) the current badge image from
    live invitation data — spec.md "Reprint reflects data changed since
    original issuance" is why callers pass the invitation's *current*
    `expires_at` rather than a value captured at first issuance.
    """
    qr_png = await generate_qr_png(tracking_id)
    return await anyio.to_thread.run_sync(
        lambda: _composite(
            tracking_id=tracking_id,
            primary_contact_full_name=primary_contact_full_name,
            expires_at=expires_at,
            qr_png=qr_png,
        )
    )
