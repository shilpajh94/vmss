from typing import Any

from sqlalchemy import func, select

from vmss_api.core.database import TenantScopedRepository, order_clause
from vmss_api.core.schemas import SortOrder
from vmss_api.kiosks.models import Kiosk
from vmss_api.org_structure.schemas import ActiveStatus


class KioskRepository(TenantScopedRepository[Kiosk]):
    model = Kiosk

    async def get_by_name(self, name: str) -> Kiosk | None:
        stmt = select(Kiosk).where(
            func.lower(Kiosk.name) == name.lower(), Kiosk.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        status: ActiveStatus | None,
        include_hidden: bool,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[Kiosk], int]:
        column = {"name": Kiosk.name, "created_at": Kiosk.created_at}[sort_by]
        filters: list[Any] = []
        if not include_hidden:
            filters.append(Kiosk.is_hidden.is_(False))
        if status is not None:
            filters.append(Kiosk.is_active.is_(status == ActiveStatus.active))
        return await super().paginate(
            page=page,
            page_size=page_size,
            order_by=order_clause(column, sort_order),
            filters=filters,
        )
