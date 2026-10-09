"""The signed check-in QR image a confirmation or reschedule email
references by URL (serve-email-images-by-url-and-complete-contact
design.md Decisions 1–2). The HMAC over tenant id, invitation id and
expiry is the authorization — like `core/storage_router.py`, no bearer
token — and it's what stops a caller probing another tenant or invitation
by editing the path (security-architecture.md §1: tenant from a signed
token, never a raw client-supplied id).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core import email_assets
from vmss_api.core.database import get_db
from vmss_api.core.logging import logger
from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import error_response
from vmss_api.invitations import service
from vmss_api.tenant.repository import TenantRepository

router = APIRouter(prefix="/public/email-assets", tags=["email-assets"])


@router.get(
    "/{tenant_id}/qr/{invitation_id}.png",
    response_class=Response,
    responses={
        200: {"content": {"image/png": {}}, "description": "The check-in QR image."},
        403: {"description": "The signature doesn't match."},
        404: {"description": "Unknown tenant, invitation, or QR record."},
        410: {"description": "The link has expired."},
    },
)
@limiter.limit("60/minute")
async def get_email_qr(
    request: Request,
    tenant_id: uuid.UUID,
    invitation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    exp: Annotated[int, Query()],
    sig: Annotated[str, Query(max_length=64)],
) -> Response:
    if not email_assets.verify_qr_signature(tenant_id, invitation_id, exp, sig):
        logger.warning(
            "email_qr_signature_invalid",
            tenant_id=str(tenant_id),
            invitation_id=str(invitation_id),
        )
        return error_response(message="This link is invalid", status_code=status.HTTP_403_FORBIDDEN)
    if email_assets.is_expired(exp):
        return error_response(message="This link has expired", status_code=status.HTTP_410_GONE)
    tenant = await TenantRepository(db).get(tenant_id)
    if tenant is None or not tenant.is_active:
        return error_response(message="Not found", status_code=status.HTTP_404_NOT_FOUND)
    png = await service.email_qr_png(tenant.schema_name, invitation_id)
    if png is None:
        return error_response(message="Not found", status_code=status.HTTP_404_NOT_FOUND)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=86400"},
    )
