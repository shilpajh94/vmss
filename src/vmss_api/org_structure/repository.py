import uuid
from collections.abc import Collection
from typing import Any

from sqlalchemy import func, select

from vmss_api.core.database import TenantScopedRepository
from vmss_api.core.schemas import SortOrder
from vmss_api.org_structure.models import (
    Branch,
    Building,
    Company,
    Department,
    Floor,
    ReceptionDesk,
    SecurityGate,
)


def _order_clause(column: Any, sort_order: SortOrder) -> Any:
    return column.desc() if sort_order == SortOrder.desc else column.asc()


class CompanyRepository(TenantScopedRepository[Company]):
    model = Company

    async def get_singleton(self) -> Company | None:
        stmt = select(Company).where(Company.deleted_at.is_(None)).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_registration_number(self, registration_number: str) -> Company | None:
        stmt = select(Company).where(
            Company.registration_number == registration_number, Company.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class BranchRepository(TenantScopedRepository[Branch]):
    model = Branch

    async def get_by_code(self, code: str) -> Branch | None:
        stmt = select(Branch).where(Branch.code == code, Branch.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self, *, page: int, page_size: int, sort_by: str, sort_order: SortOrder
    ) -> tuple[list[Branch], int]:
        column = {"name": Branch.name, "created_at": Branch.created_at}[sort_by]
        return await super().paginate(
            page=page, page_size=page_size, order_by=_order_clause(column, sort_order)
        )


class BuildingRepository(TenantScopedRepository[Building]):
    model = Building

    async def get_by_code(self, branch_id: uuid.UUID, code: str) -> Building | None:
        stmt = select(Building).where(
            Building.branch_id == branch_id, Building.code == code, Building.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        branch_id: uuid.UUID,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[Building], int]:
        """`branch_id` is always the caller's `X-Branch-ID`-authorized branch
        (`org_structure/deps.py::require_branch_permission`), not a
        client-chosen filter — see `database-architecture.md`/security notes
        in `router.py` on why a branch-scoped user must never see another
        branch's buildings.
        """
        column = {"name": Building.name, "created_at": Building.created_at}[sort_by]
        return await super().paginate(
            page=page,
            page_size=page_size,
            order_by=_order_clause(column, sort_order),
            filters=[Building.branch_id == branch_id],
        )


class FloorRepository(TenantScopedRepository[Floor]):
    model = Floor

    async def get_by_number(self, building_id: uuid.UUID, floor_number: int) -> Floor | None:
        stmt = select(Floor).where(
            Floor.building_id == building_id,
            Floor.floor_number == floor_number,
            Floor.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        branch_id: uuid.UUID,
        building_id: uuid.UUID | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[Floor], int]:
        """Joins back to `Building` to filter by `branch_id` (`Floor` has no
        `branch_id` column of its own) — the caller's authorized branch, not
        a client-chosen filter. `TenantScopedRepository.paginate` can't
        express a join, so this bypasses it with the same count+page shape.
        """
        column = {"name": Floor.name, "created_at": Floor.created_at}[sort_by]
        conditions: list[Any] = [Floor.deleted_at.is_(None), Building.branch_id == branch_id]
        if building_id is not None:
            conditions.append(Floor.building_id == building_id)

        count_stmt = (
            select(func.count())
            .select_from(Floor)
            .join(Building, Floor.building_id == Building.id)
            .where(*conditions)
        )
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = (
            select(Floor)
            .join(Building, Floor.building_id == Building.id)
            .where(*conditions)
            .order_by(_order_clause(column, sort_order))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total


class DepartmentRepository(TenantScopedRepository[Department]):
    model = Department

    async def get_by_code(self, floor_id: uuid.UUID, code: str) -> Department | None:
        stmt = select(Department).where(
            Department.floor_id == floor_id,
            Department.code == code,
            Department.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_existing_ids(self, ids: Collection[uuid.UUID]) -> set[uuid.UUID]:
        """Batch existence check for `auth/service.py::sync_employee_directory`
        — one `WHERE id IN (...)` for every `department_id` referenced across
        an incoming sync batch, instead of one `get()` call per row. See
        query-performance.md §2.
        """
        if not ids:
            return set()
        stmt = select(Department.id).where(Department.id.in_(ids), Department.deleted_at.is_(None))
        return set((await self.session.execute(stmt)).scalars().all())

    async def list_page(
        self,
        *,
        branch_id: uuid.UUID,
        floor_id: uuid.UUID | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[Department], int]:
        """Joins through `Floor` → `Building` to filter by the caller's
        authorized branch — see `FloorRepository.list_page`.
        """
        column = {"name": Department.name, "created_at": Department.created_at}[sort_by]
        conditions: list[Any] = [Department.deleted_at.is_(None), Building.branch_id == branch_id]
        if floor_id is not None:
            conditions.append(Department.floor_id == floor_id)

        count_stmt = (
            select(func.count())
            .select_from(Department)
            .join(Floor, Department.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .where(*conditions)
        )
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = (
            select(Department)
            .join(Floor, Department.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .where(*conditions)
            .order_by(_order_clause(column, sort_order))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total


class ReceptionDeskRepository(TenantScopedRepository[ReceptionDesk]):
    model = ReceptionDesk

    async def get_by_code(self, floor_id: uuid.UUID, code: str) -> ReceptionDesk | None:
        stmt = select(ReceptionDesk).where(
            ReceptionDesk.floor_id == floor_id,
            ReceptionDesk.code == code,
            ReceptionDesk.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        branch_id: uuid.UUID,
        floor_id: uuid.UUID | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[ReceptionDesk], int]:
        """Joins through `Floor` → `Building` to filter by the caller's
        authorized branch — see `FloorRepository.list_page`.
        """
        column = {"name": ReceptionDesk.name, "created_at": ReceptionDesk.created_at}[sort_by]
        conditions: list[Any] = [
            ReceptionDesk.deleted_at.is_(None),
            Building.branch_id == branch_id,
        ]
        if floor_id is not None:
            conditions.append(ReceptionDesk.floor_id == floor_id)

        count_stmt = (
            select(func.count())
            .select_from(ReceptionDesk)
            .join(Floor, ReceptionDesk.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .where(*conditions)
        )
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = (
            select(ReceptionDesk)
            .join(Floor, ReceptionDesk.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .where(*conditions)
            .order_by(_order_clause(column, sort_order))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total


class SecurityGateRepository(TenantScopedRepository[SecurityGate]):
    model = SecurityGate

    async def get_by_code(self, branch_id: uuid.UUID, code: str) -> SecurityGate | None:
        stmt = select(SecurityGate).where(
            SecurityGate.branch_id == branch_id,
            SecurityGate.code == code,
            SecurityGate.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        branch_id: uuid.UUID,
        building_id: uuid.UUID | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[SecurityGate], int]:
        """`branch_id` is always the caller's authorized branch — see
        `BuildingRepository.list_page`.
        """
        column = {"name": SecurityGate.name, "created_at": SecurityGate.created_at}[sort_by]
        filters: list[Any] = [SecurityGate.branch_id == branch_id]
        if building_id is not None:
            filters.append(SecurityGate.building_id == building_id)
        return await super().paginate(
            page=page,
            page_size=page_size,
            order_by=_order_clause(column, sort_order),
            filters=filters,
        )
