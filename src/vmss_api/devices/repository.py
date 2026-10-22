import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from vmss_api.core.database import TenantScopedRepository
from vmss_api.core.schemas import SortOrder
from vmss_api.devices.models import Device, TenantSettings
from vmss_api.org_structure.models import Branch, Building


class DeviceRepository(TenantScopedRepository[Device]):
    model = Device

    async def get_by_device_id(self, device_id: str) -> Device | None:
        stmt = select(Device).where(Device.device_id == device_id, Device.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_many(self, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Device]:
        """Includes soft-deleted rows: invitation history keeps pointing at a
        device after it is deleted."""
        wanted = {i for i in ids}
        if not wanted:
            return {}
        stmt = select(Device).where(Device.id.in_(wanted))
        return {d.id: d for d in (await self.session.execute(stmt)).scalars()}

    async def list_page(
        self,
        *,
        approval_status: str | None,
        is_active: bool | None,
        operating_mode: str | None,
        branch_id: uuid.UUID | None,
        building_id: uuid.UUID | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[tuple[Device, str | None, str | None]], int]:
        """Single query joining branch/building names (no per-row lookups,
        query-performance.md §2)."""
        column = {
            "name": Device.name,
            "created_at": Device.created_at,
            "approval_status": Device.approval_status,
        }[sort_by]
        filters: list[Any] = [Device.deleted_at.is_(None)]
        if approval_status is not None:
            filters.append(Device.approval_status == approval_status)
        if is_active is not None:
            filters.append(Device.is_active.is_(is_active))
        if operating_mode is not None:
            filters.append(Device.operating_mode == operating_mode)
        if branch_id is not None:
            filters.append(Device.branch_id == branch_id)
        if building_id is not None:
            filters.append(Device.building_id == building_id)

        building = aliased(Building)
        base = (
            select(Device, Branch.name, building.name)
            .join(Branch, Branch.id == Device.branch_id)
            .outerjoin(building, building.id == Device.building_id)
            .where(*filters)
        )
        total = (
            await self.session.execute(
                select(func.count()).select_from(select(Device.id).where(*filters).subquery())
            )
        ).scalar_one()
        order = column.desc() if sort_order == SortOrder.desc else column.asc()
        stmt = base.order_by(order, Device.id).limit(page_size).offset((page - 1) * page_size)
        rows = (await self.session.execute(stmt)).all()
        return [(d, b, bl) for d, b, bl in rows], total

    async def names_for(self, device: Device) -> tuple[str | None, str | None]:
        branch = await self.session.get(Branch, device.branch_id)
        building = (
            await self.session.get(Building, device.building_id) if device.building_id else None
        )
        return (branch.name if branch else None, building.name if building else None)


class TenantSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self) -> TenantSettings | None:
        return (await self.session.execute(select(TenantSettings).limit(1))).scalar_one_or_none()
