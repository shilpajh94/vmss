from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from vmss_api.core.schemas import SortOrder
from vmss_api.kiosks.models import Kiosk
from vmss_api.kiosks.repository import KioskRepository
from vmss_api.kiosks.schemas import KioskCreate, KioskUpdate
from vmss_api.org_structure.schemas import ActiveStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_DUPLICATE_NAME = "A kiosk with this name already exists"


async def _get_or_404(repo: KioskRepository, kiosk_id: uuid.UUID) -> Kiosk:
    kiosk = await repo.get(kiosk_id)
    if kiosk is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Kiosk not found")
    return kiosk


async def _ensure_name_free(
    repo: KioskRepository, name: str, *, except_id: uuid.UUID | None = None
) -> None:
    existing = await repo.get_by_name(name)
    if existing is not None and existing.id != except_id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_DUPLICATE_NAME)


async def create_kiosk(tenant_db: AsyncSession, payload: KioskCreate) -> Kiosk:
    repo = KioskRepository(tenant_db)
    await _ensure_name_free(repo, payload.name)
    kiosk = Kiosk(id=uuid.uuid4(), **payload.model_dump())
    tenant_db.add(kiosk)
    await tenant_db.commit()
    await tenant_db.refresh(kiosk)
    return kiosk


async def list_kiosks_page(
    tenant_db: AsyncSession,
    *,
    status: ActiveStatus | None,
    include_hidden: bool,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
) -> tuple[list[Kiosk], int]:
    return await KioskRepository(tenant_db).list_page(
        status=status,
        include_hidden=include_hidden,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def get_kiosk(tenant_db: AsyncSession, kiosk_id: uuid.UUID) -> Kiosk:
    return await _get_or_404(KioskRepository(tenant_db), kiosk_id)


async def update_kiosk(tenant_db: AsyncSession, kiosk_id: uuid.UUID, payload: KioskUpdate) -> Kiosk:
    repo = KioskRepository(tenant_db)
    kiosk = await _get_or_404(repo, kiosk_id)
    changes = payload.model_dump(exclude_unset=True)
    # A null name/is_active would violate NOT NULL; treat explicit null as "unchanged".
    for required in ("name", "is_active"):
        if changes.get(required, ...) is None:
            del changes[required]
    if "name" in changes:
        await _ensure_name_free(repo, changes["name"], except_id=kiosk.id)
    for field, value in changes.items():
        setattr(kiosk, field, value)
    await tenant_db.commit()
    await tenant_db.refresh(kiosk)
    return kiosk


async def set_visibility(tenant_db: AsyncSession, kiosk_id: uuid.UUID, is_hidden: bool) -> Kiosk:
    kiosk = await _get_or_404(KioskRepository(tenant_db), kiosk_id)
    kiosk.is_hidden = is_hidden
    await tenant_db.commit()
    await tenant_db.refresh(kiosk)
    return kiosk


async def delete_kiosk(tenant_db: AsyncSession, kiosk_id: uuid.UUID) -> None:
    repo = KioskRepository(tenant_db)
    kiosk = await _get_or_404(repo, kiosk_id)
    await repo.soft_delete(kiosk)
    await tenant_db.commit()
