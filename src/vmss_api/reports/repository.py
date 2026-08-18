import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.org_structure.models import (
    Branch,
    Building,
    Department,
    Floor,
    ReceptionDesk,
    SecurityGate,
)


class BranchRollupRepository:
    """Read-only cross-branch aggregation queries for the `reports` feature.

    Owns no table of its own — it reads across `org_structure`'s and
    `auth`'s tenant-scoped tables the same way `auth/repository.py`'s
    `UserRepository.list_employees_page` already joins into `org_structure`
    models directly. One grouped-by-branch aggregate query per entity type,
    never a per-branch loop (query-performance.md §2) — `service.py`
    reassembles the per-branch rows in Python from these dicts.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def branches(self) -> list[Branch]:
        stmt = select(Branch).where(Branch.deleted_at.is_(None)).order_by(Branch.name.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def building_counts_by_branch(self) -> dict[uuid.UUID, int]:
        stmt = (
            select(Building.branch_id, func.count())
            .where(Building.deleted_at.is_(None))
            .group_by(Building.branch_id)
        )
        return {branch_id: count for branch_id, count in (await self.session.execute(stmt)).all()}

    async def floor_counts_by_branch(self) -> dict[uuid.UUID, int]:
        stmt = (
            select(Building.branch_id, func.count())
            .select_from(Floor)
            .join(Building, Floor.building_id == Building.id)
            .where(Floor.deleted_at.is_(None), Building.deleted_at.is_(None))
            .group_by(Building.branch_id)
        )
        return {branch_id: count for branch_id, count in (await self.session.execute(stmt)).all()}

    async def department_counts_by_branch(self) -> dict[uuid.UUID, int]:
        stmt = (
            select(Building.branch_id, func.count())
            .select_from(Department)
            .join(Floor, Department.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .where(
                Department.deleted_at.is_(None),
                Floor.deleted_at.is_(None),
                Building.deleted_at.is_(None),
            )
            .group_by(Building.branch_id)
        )
        return {branch_id: count for branch_id, count in (await self.session.execute(stmt)).all()}

    async def reception_desk_counts_by_branch(self) -> dict[uuid.UUID, int]:
        stmt = (
            select(Building.branch_id, func.count())
            .select_from(ReceptionDesk)
            .join(Floor, ReceptionDesk.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .where(
                ReceptionDesk.deleted_at.is_(None),
                Floor.deleted_at.is_(None),
                Building.deleted_at.is_(None),
            )
            .group_by(Building.branch_id)
        )
        return {branch_id: count for branch_id, count in (await self.session.execute(stmt)).all()}

    async def security_gate_counts_by_branch(self) -> dict[uuid.UUID, int]:
        stmt = (
            select(SecurityGate.branch_id, func.count())
            .where(SecurityGate.deleted_at.is_(None))
            .group_by(SecurityGate.branch_id)
        )
        return {branch_id: count for branch_id, count in (await self.session.execute(stmt)).all()}

    async def active_employee_counts_by_branch(self) -> dict[uuid.UUID, int]:
        stmt = (
            select(Building.branch_id, func.count())
            .select_from(User)
            .join(Department, User.department_id == Department.id)
            .join(Floor, Department.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .where(
                User.employee_code.is_not(None),
                User.is_active.is_(True),
                User.deleted_at.is_(None),
                Department.deleted_at.is_(None),
                Floor.deleted_at.is_(None),
                Building.deleted_at.is_(None),
            )
            .group_by(Building.branch_id)
        )
        return {branch_id: count for branch_id, count in (await self.session.execute(stmt)).all()}
