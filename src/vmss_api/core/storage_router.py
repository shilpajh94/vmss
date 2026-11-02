"""Serves the `local` storage backend's signed URLs
(add-avatar-upload-and-verify-image-storage/design.md Decision 1) — the
route a `core/storage.py::url_for()` local-mode URL actually points to.
Cross-cutting storage infrastructure, not a feature: it has no
`service.py`/`schemas.py` of its own beyond the sign/verify helpers already
living in `core/storage.py`.

The signature is the authorization (mirroring how an S3 presigned URL
works) — this route deliberately takes no `get_current_user`/
`require_permission` dependency of its own. Whoever built the signed URL
already decided, at that moment, that the current caller may see this file.
"""

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response
from starlette import status

from vmss_api.core import storage
from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import error_response

router = APIRouter(prefix="/files", tags=["file-storage"])


# Generous: email image proxies fetch on behalf of many recipients from few IPs.
@router.get("/local/{key:path}")
@limiter.limit("300/minute")
async def get_local_file(
    request: Request,
    key: str,
    exp: int,
    sig: str = Query(...),
) -> Response:
    """`key:path` (not a plain `str` segment) because a storage key contains
    literal `/` characters — e.g. `vmss:{tenant}:invitations/badges:{uuid}
    .png` — which an ASGI server decodes out of `%2F` before routing ever
    sees it, splitting a single-segment matcher across multiple path
    segments and 404ing on every key with a `/` in its category.
    """
    if not storage.verify_local_url(key, exp, sig):
        return error_response(
            message="This link is invalid or has expired",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    try:
        content = await storage.load(key)
    except FileNotFoundError:
        return error_response(message="File not found", status_code=status.HTTP_404_NOT_FOUND)
    content_type = storage.content_type_for(key)
    return Response(content=content, media_type=content_type)
