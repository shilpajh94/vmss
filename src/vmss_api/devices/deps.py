from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.devices import service
from vmss_api.devices.models import Device


def make_device_dependency(db_dependency):
    """Builds the optional `device-id` header dependency bound to a route's
    own tenant-session dependency (staff routes use `get_tenant_db`, public
    ones `track_default_tenant_db`). Returns `None` when the header is
    absent — existing web/staff clients keep working (design.md Decision 6).
    """

    async def _resolve(
        tenant_db: Annotated[AsyncSession, Depends(db_dependency)],
        device_id: Annotated[
            str | None,
            Header(
                alias="device-id",
                max_length=255,
                description=(
                    "Optional. Registered kiosk/security device performing the action; "
                    "must be approved and enabled."
                ),
            ),
        ] = None,
    ) -> Device | None:
        if device_id is None:
            return None
        return await service.resolve_usable_device(tenant_db, device_id)

    return _resolve
