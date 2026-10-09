"""Public, unauthenticated image routes that emails reference by absolute
URL (serve-email-images-by-url-and-complete-contact design.md Decision 1),
so a delivered message carries no attachment or inline image parts.

Only the brand logo lives here; the signed check-in QR route needs
invitation data, so it's `invitations/email_assets_router.py` — `core`
doesn't import feature packages (fastapi-architecture.md §6). Both share
the `/public/email-assets` prefix and `email-assets` tag.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from vmss_api.core.email_assets import LOGO_FILENAME

router = APIRouter(prefix="/public/email-assets", tags=["email-assets"])

# Versioned by content, not URL: replacing the file means renaming
# `LOGO_FILENAME`, which is what busts an `immutable` cache.
_LOGO_PATH = Path(__file__).parent / "email_assets" / "visimio-logo-on-dark.png"


@router.get(f"/{LOGO_FILENAME}", response_class=FileResponse)
async def get_email_logo() -> FileResponse:
    return FileResponse(
        _LOGO_PATH,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
