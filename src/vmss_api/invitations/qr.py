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
