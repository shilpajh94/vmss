from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.deps import get_current_user, get_tenant_db
from vmss_api.core.responses import success_response
from vmss_api.core.schemas import Envelope
from vmss_api.notifications import service
from vmss_api.notifications.schemas import DeviceOut, DeviceRegisterRequest

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post(
    "/devices",
    response_model=Envelope[DeviceOut],
    status_code=status.HTTP_201_CREATED,
)
async def register_device(
    payload: DeviceRegisterRequest,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Any authenticated staff user may register a device for their own
    account — self-service, like `GET /auth/me`, not RBAC-gated
    (specs/notifications/spec.md "A Staff User Registers a Device for Push
    Notifications").
    """
    device = await service.register_device(
        tenant_db, user_id=user.id, fcm_token=payload.fcm_token, platform=payload.platform
    )
    return success_response(
        data=DeviceOut.model_validate(device), status_code=status.HTTP_201_CREATED
    )


@router.delete(
    "/devices/{fcm_token}",
    response_model=Envelope[None],
)
async def unregister_device(
    fcm_token: str,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """No-op, not an error, when `fcm_token` was never registered or belongs
    to someone else (specs/notifications/spec.md "A Staff User Unregisters a
    Device").
    """
    await service.unregister_device(tenant_db, user_id=user.id, fcm_token=fcm_token)
    return success_response(data=None)
