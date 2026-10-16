import io

import anyio
import qrcode


def _render_png(data: str) -> bytes:
    # A fixed mask skips qrcode's search over all eight masks for the one
    # with the lowest readability-penalty score. Decoders read every mask, and
    # the search was ~70% of a render that runs on each approval, holding the
    # GIL the whole time (QA load test, full-stack-qa-and-load-testing).
    code = qrcode.QRCode(mask_pattern=0)
    code.add_data(data)
    code.make(fit=True)
    buffer = io.BytesIO()
    code.make_image().save(buffer, format="PNG")
    return buffer.getvalue()


async def generate_qr_png(data: str) -> bytes:
    """QR image rendering is CPU-bound, so it's offloaded per
    fastapi-architecture.md §4 rather than run inline on the event loop.
    """
    return await anyio.to_thread.run_sync(_render_png, data)
