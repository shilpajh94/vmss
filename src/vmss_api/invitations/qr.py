import io

import anyio
import qrcode


def _render_png(data: str) -> bytes:
    image = qrcode.make(data)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def generate_qr_png(data: str) -> bytes:
    """QR image rendering is CPU-bound, so it's offloaded per
    fastapi-architecture.md §4 rather than run inline on the event loop.
    """
    return await anyio.to_thread.run_sync(_render_png, data)


def _render_rgb_png(data: str) -> bytes:
    # WhatsApp rejects the 1-bit PNG `qrcode.make` emits (Meta error 131053:
    # only 8-bit RGB/RGBA images are accepted).
    image = qrcode.make(data).get_image().convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def generate_qr_png_rgb(data: str) -> bytes:
    return await anyio.to_thread.run_sync(_render_rgb_png, data)
