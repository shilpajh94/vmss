import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.deps import get_current_user, get_pagination, get_tenant_db
from vmss_api.core.responses import paginated_response, success_response
from vmss_api.core.schemas import Envelope, PaginatedEnvelope
from vmss_api.notifications import service
from vmss_api.notifications.schemas import (
    DeviceOut,
    DeviceRegisterRequest,
    NotificationOut,
    UnreadCountOut,
)

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


# --- In-app notification feed (fix-web-push-and-add-notification-feed) ------
# Self-scoped: every route acts only on the caller's own notifications, so
# there's no `require_permission` gate — same as device registration above.


@router.get("", response_model=PaginatedEnvelope[NotificationOut])
async def list_notifications(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    unread_only: Annotated[bool, Query(alias="unreadOnly")] = False,
) -> JSONResponse:
    page, page_size = pagination
    notifications, total = await service.list_notifications(
        tenant_db, user_id=user.id, unread_only=unread_only, page=page, page_size=page_size
    )
    return paginated_response(
        data=[NotificationOut.model_validate(n) for n in notifications],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/unread-count", response_model=Envelope[UnreadCountOut])
async def get_unread_count(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    unread_count = await service.count_unread(tenant_db, user_id=user.id)
    return success_response(data=UnreadCountOut(unread_count=unread_count))


@router.post("/read-all", response_model=Envelope[None])
async def mark_all_notifications_read(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    await service.mark_all_read(tenant_db, user_id=user.id)
    return success_response(data=None, message="All notifications marked read")


@router.patch("/{notification_id}/read", response_model=Envelope[NotificationOut])
async def mark_notification_read(
    notification_id: uuid.UUID,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    notification = await service.mark_read(
        tenant_db, user_id=user.id, notification_id=notification_id
    )
    return success_response(data=NotificationOut.model_validate(notification))
