import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.access_control.models import (
    InvitationZone,
    VisitorCategoryZone,
    Zone,
    ZoneAccessEvent,
    ZoneGate,
)
from vmss_api.core.database import TenantScopedRepository, order_clause
from vmss_api.core.schemas import BranchScope, SortOrder
from vmss_api.core.tenancy import branch_filter
from vmss_api.devices.models import Device
from vmss_api.invitations.models import Invitation
from vmss_api.org_structure.models import Building, Floor
from vmss_api.visitors.models import VisitorCategory


class ZoneRepository(TenantScopedRepository[Zone]):
    model = Zone

    async def get_including_deleted(self, zone_id: uuid.UUID) -> Zone | None:
        """The scan path needs a soft-deleted zone to answer `zone_inactive`
        rather than behave as if the id never existed."""
        stmt = select(Zone).where(Zone.id == zone_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, branch_id: uuid.UUID, code: str) -> Zone | None:
        stmt = select(Zone).where(
            Zone.branch_id == branch_id, Zone.code == code, Zone.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        branch_scope: BranchScope,
        is_active: bool | None,
        is_default: bool | None = None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[Zone], int]:
        column = {"name": Zone.name, "created_at": Zone.created_at}[sort_by]
        filters: list[Any] = []
        scope = branch_filter(Zone.branch_id, branch_scope)
        if scope is not None:
            filters.append(scope)
        if is_active is not None:
            filters.append(Zone.is_active.is_(is_active))
        if is_default is not None:
            filters.append(Zone.is_default.is_(is_default))
        return await super().paginate(
            page=page,
            page_size=page_size,
            order_by=[order_clause(column, sort_order), Zone.id.asc()],
            filters=filters,
        )

    async def get_default_for_branch(self, branch_id: uuid.UUID) -> Zone | None:
        """The branch's live default zone, active or not (the service decides)."""
        stmt = select(Zone).where(
            Zone.branch_id == branch_id, Zone.is_default.is_(True), Zone.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def gate_ids_by_zone(
        self, zone_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[uuid.UUID]]:
        """One query for a whole page, never one per zone (query-performance.md §2)."""
        result: dict[uuid.UUID, list[uuid.UUID]] = {zone_id: [] for zone_id in zone_ids}
        if not zone_ids:
            return result
        stmt = (
            select(ZoneGate.zone_id, ZoneGate.gate_id)
            .where(ZoneGate.zone_id.in_(zone_ids))
            .order_by(ZoneGate.gate_id)
        )
        for zone_id, gate_id in (await self.session.execute(stmt)).all():
            result[zone_id].append(gate_id)
        return result

    async def replace_gates(self, zone_id: uuid.UUID, gate_ids: Sequence[uuid.UUID]) -> None:
        await self.session.execute(delete(ZoneGate).where(ZoneGate.zone_id == zone_id))
        if gate_ids:
            await self.session.execute(
                pg_insert(ZoneGate).values(
                    [{"zone_id": zone_id, "gate_id": g} for g in set(gate_ids)]
                )
            )

    async def live_zones_for_gate(self, gate_id: uuid.UUID) -> list[Zone]:
        """Live, active zones a gate device is linked to (for the check-in log)."""
        stmt = (
            select(Zone)
            .join(ZoneGate, ZoneGate.zone_id == Zone.id)
            .where(ZoneGate.gate_id == gate_id, Zone.deleted_at.is_(None), Zone.is_active.is_(True))
            .order_by(Zone.id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def gate_serves_zone(self, zone_id: uuid.UUID, gate_id: uuid.UUID) -> bool:
        stmt = select(ZoneGate.zone_id).where(
            ZoneGate.zone_id == zone_id, ZoneGate.gate_id == gate_id
        )
        return (await self.session.execute(stmt)).first() is not None

    async def count_gates_in_branch(
        self, gate_ids: Sequence[uuid.UUID], branch_id: uuid.UUID
    ) -> int:
        if not gate_ids:
            return 0
        stmt = (
            select(func.count())
            .select_from(Device)
            .where(
                Device.id.in_(set(gate_ids)),
                Device.branch_id == branch_id,
                Device.operating_mode == "security",
                Device.deleted_at.is_(None),
            )
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def building_in_branch(self, building_id: uuid.UUID, branch_id: uuid.UUID) -> bool:
        stmt = select(Building.id).where(
            Building.id == building_id,
            Building.branch_id == branch_id,
            Building.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).first() is not None

    async def floor_in_building(self, floor_id: uuid.UUID, building_id: uuid.UUID) -> bool:
        stmt = select(Floor.id).where(
            Floor.id == floor_id, Floor.building_id == building_id, Floor.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).first() is not None

    async def count_in_branch(self, zone_ids: Sequence[uuid.UUID], branch_id: uuid.UUID) -> int:
        if not zone_ids:
            return 0
        stmt = (
            select(func.count())
            .select_from(Zone)
            .where(
                Zone.id.in_(set(zone_ids)), Zone.branch_id == branch_id, Zone.deleted_at.is_(None)
            )
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def count_by_ids(self, zone_ids: Sequence[uuid.UUID]) -> int:
        if not zone_ids:
            return 0
        stmt = (
            select(func.count())
            .select_from(Zone)
            .where(Zone.id.in_(set(zone_ids)), Zone.deleted_at.is_(None))
        )
        return (await self.session.execute(stmt)).scalar_one()


class ZoneMappingRepository:
    """Allowed-zone join tables. Not soft-delete aware: the rows are plain
    mappings, and a deleted zone is already denied by `zone_inactive`."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_invitation(self, invitation_id: uuid.UUID) -> Invitation | None:
        stmt = select(Invitation).where(
            Invitation.id == invitation_id, Invitation.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def category_exists(self, category_id: uuid.UUID) -> bool:
        stmt = select(VisitorCategory.id).where(
            VisitorCategory.id == category_id, VisitorCategory.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).first() is not None

    async def category_zone_ids(self, category_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(VisitorCategoryZone.zone_id).where(
            VisitorCategoryZone.category_id == category_id
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def replace_category_zones(
        self, category_id: uuid.UUID, zone_ids: Sequence[uuid.UUID]
    ) -> None:
        await self.session.execute(
            delete(VisitorCategoryZone).where(VisitorCategoryZone.category_id == category_id)
        )
        if zone_ids:
            await self.session.execute(
                pg_insert(VisitorCategoryZone).values(
                    [{"category_id": category_id, "zone_id": z} for z in set(zone_ids)]
                )
            )

    async def invitation_zone_ids(self, invitation_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(InvitationZone.zone_id).where(InvitationZone.invitation_id == invitation_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def replace_invitation_zones(
        self,
        invitation_id: uuid.UUID,
        zone_ids: Sequence[uuid.UUID],
        *,
        assigned_by_user_id: uuid.UUID | None,
    ) -> None:
        await self.session.execute(
            delete(InvitationZone).where(InvitationZone.invitation_id == invitation_id)
        )
        if zone_ids:
            await self.session.execute(
                pg_insert(InvitationZone).values(
                    [
                        {
                            "invitation_id": invitation_id,
                            "zone_id": z,
                            "assigned_by_user_id": assigned_by_user_id,
                        }
                        for z in set(zone_ids)
                    ]
                )
            )

    async def default_zone_id(self, branch_id: uuid.UUID) -> uuid.UUID | None:
        stmt = select(Zone.id).where(
            Zone.branch_id == branch_id,
            Zone.is_default.is_(True),
            Zone.is_active.is_(True),
            Zone.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def effective_zone_ids(
        self, invitation_id: uuid.UUID, category_id: uuid.UUID | None, branch_id: uuid.UUID
    ) -> set[uuid.UUID]:
        """Invitation's own zones replace the category defaults, and the branch's
        default zone is always added on top, so a forgotten assignment never locks
        a visitor out of it. No assignment and no default zone means an empty set
        (default deny). At most three queries, independent of zone count."""
        allowed = set(await self.invitation_zone_ids(invitation_id))
        if not allowed and category_id is not None:
            allowed = set(await self.category_zone_ids(category_id))
        default_id = await self.default_zone_id(branch_id)
        if default_id is not None:
            allowed.add(default_id)
        return allowed


class ZoneEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_gate(self, gate_id: uuid.UUID) -> Device | None:
        """A gate is a live security-mode device."""
        stmt = select(Device).where(
            Device.id == gate_id, Device.operating_mode == "security", Device.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def add(
        self,
        *,
        invitation_id: uuid.UUID,
        zone_id: uuid.UUID,
        gate_id: uuid.UUID,
        direction: str,
        decision: str,
        reason: str | None,
        scanned_by_user_id: uuid.UUID | None,
        occurred_at: datetime,
    ) -> ZoneAccessEvent:
        event = ZoneAccessEvent(
            id=uuid.uuid4(),
            invitation_id=invitation_id,
            zone_id=zone_id,
            gate_id=gate_id,
            direction=direction,
            decision=decision,
            reason=reason,
            scanned_by_user_id=scanned_by_user_id,
            occurred_at=occurred_at,
        )
        self.session.add(event)
        return event
