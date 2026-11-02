"""Public, unauthenticated image routes that emails reference by absolute
URL (serve-email-images-by-url-and-complete-contact design.md Decision 1),
so a delivered message carries no attachment or inline image parts.

Only the brand logo lives here; the signed check-in QR route needs
invitation data, so it's `invitations/email_assets_router.py` — `core`
doesn't import feature packages (fastapi-architecture.md §6). Both share
the `/public/email-assets` prefix and `email-assets` tag.
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from vmss_api.core.email_assets import LOGO_FILENAME, RETIRED_LOGO_FILENAMES
from vmss_api.core.rate_limit import limiter

router = APIRouter(prefix="/public/email-assets", tags=["email-assets"])

# Versioned by content, not URL: replacing the file means renaming
# `LOGO_FILENAME`, which is what busts an `immutable` cache.
_LOGO_PATH = Path(__file__).parent / "email_assets" / "guestify-logo-on-dark.png"


# Generous: mail-client image proxies fetch for many recipients from few IPs.
@router.get(f"/{LOGO_FILENAME}", response_class=FileResponse)
@limiter.limit("600/minute")
async def get_email_logo(request: Request) -> FileResponse:
    return FileResponse(
        _LOGO_PATH,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


# Retired logo URLs serve the current logo rather than 404, since sent
# emails still point at them. Clients that cached the old bytes under the
# `immutable` promise keep them; that's accepted (rebrand-to-guestify
# design.md Decision 5). Not a redirect: some image proxies won't follow one.
for _retired in RETIRED_LOGO_FILENAMES:
    router.add_api_route(
        f"/{_retired}",
        get_email_logo,
        methods=["GET"],
        response_class=FileResponse,
        include_in_schema=False,
    )
