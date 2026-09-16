import uuid
from collections.abc import Collection
from typing import Any

from sqlalchemy import func, select

from vmss_api.core.database import TenantScopedRepository
from vmss_api.core.schemas import BranchScope, SortOrder
from vmss_api.org_structure.models import (
    Branch,
    Building,
    Company,
    Department,
    Floor,
    ReceptionDesk,
    SecurityGate,
)
from vmss_api.org_structure.schemas import (
    ActiveStatus,
    DeskStatus,
    FloorAccessLevel,
    GateType,
    SecurityLevel,
)


def _branch_filter(column: Any, branch_scope: BranchScope) -> Any | None:
    """Translates a resolved `BranchScope` into a filter clause: `None` (no
    filter at all) for a company-wide "all" scope, otherwise `column IN
    (...)` — a single-branch scope is just a one-element set, so there's no
    separate equality-filter path to maintain. See
    `org_structure/deps.py::require_branch_scope`.
    """
    return None if branch_scope == "all" else column.in_(branch_scope)


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

    async def get_including_deleted(self, id_: uuid.UUID) -> Branch | None:
        """Like `get`, but does not filter out a soft-deleted branch — used
        to authorize approving an invitation whose recorded branch was later
        soft-deleted. See `BuildingRepository.get_including_deleted`.
        """
        stmt = select(Branch).where(Branch.id == id_)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def has_active_org_chart_descendants(self, branch_id: uuid.UUID) -> bool:
        """Whether any active (non-soft-deleted) Building, Department,
        SecurityGate (direct `branch_id`), or Floor/ReceptionDesk
        (transitively via `building_id`) still belongs to this branch —
        checked by `service.py::delete_branch` before soft-deleting a
        branch, mirroring `RoleRepository.has_active_grants`.
        """
        building_stmt = (
            select(Building.id)
            .where(Building.branch_id == branch_id, Building.deleted_at.is_(None))
            .limit(1)
        )
        if (await self.session.execute(building_stmt)).scalar_one_or_none() is not None:
            return True

        department_stmt = (
            select(Department.id)
            .where(Department.branch_id == branch_id, Department.deleted_at.is_(None))
            .limit(1)
        )
        if (await self.session.execute(department_stmt)).scalar_one_or_none() is not None:
            return True

        gate_stmt = (
            select(SecurityGate.id)
            .where(SecurityGate.branch_id == branch_id, SecurityGate.deleted_at.is_(None))
            .limit(1)
        )
        if (await self.session.execute(gate_stmt)).scalar_one_or_none() is not None:
            return True

        floor_stmt = (
            select(Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .where(Building.branch_id == branch_id, Floor.deleted_at.is_(None))
            .limit(1)
        )
        if (await self.session.execute(floor_stmt)).scalar_one_or_none() is not None:
            return True

        desk_stmt = (
            select(ReceptionDesk.id)
            .join(Floor, ReceptionDesk.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .where(Building.branch_id == branch_id, ReceptionDesk.deleted_at.is_(None))
            .limit(1)
        )
        return (await self.session.execute(desk_stmt)).scalar_one_or_none() is not None

    async def list_page(
        self,
        *,
        branch_scope: BranchScope,
        status: ActiveStatus | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[Branch], int]:
        """`branch_scope` mirrors `BuildingRepository.list_page` — the
        caller's authorized scope (`org_structure/deps.py::require_branch_scope`),
        filtered on `Branch.id` itself rather than a `branch_id` column,
        since a branch *is* the entity here.
        """
        column = {"name": Branch.name, "created_at": Branch.created_at}[sort_by]
        branch_filter = _branch_filter(Branch.id, branch_scope)
        filters: list[Any] = [branch_filter] if branch_filter is not None else []
        if status is not None:
            filters.append(Branch.is_active.is_(status == ActiveStatus.active))
        return await super().paginate(
            page=page,
            page_size=page_size,
            order_by=_order_clause(column, sort_order),
            filters=filters,
        )


class BuildingRepository(TenantScopedRepository[Building]):
    model = Building

    async def get_by_code(self, branch_id: uuid.UUID, code: str) -> Building | None:
        stmt = select(Building).where(
            Building.branch_id == branch_id, Building.code == code, Building.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_including_deleted(self, id_: uuid.UUID) -> Building | None:
        """Like `get`, but does not filter out a soft-deleted building.

        Used only to resolve the branch of an *existing* Floor/SecurityGate
        whose parent building was later soft-deleted (nothing today cascades
        that delete or blocks it while child floors remain) — without this,
        `TenantScopedRepository.get`'s `deleted_at IS NULL` filter makes
        `resolve_building_branch_id` return `None` for such a floor forever,
        so its own get/update/delete permission check can never resolve a
        branch and 404s permanently, even though the floor row itself was
        never deleted. Never use this for create-time validation, where a
        soft-deleted parent must still be treated as absent.
        """
        stmt = select(Building).where(Building.id == id_)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        branch_scope: BranchScope,
        status: ActiveStatus | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[Building], int]:
        """`branch_scope` is always the caller's authorized scope
        (`org_structure/deps.py::require_branch_scope`), not a client-chosen
        filter — see `database-architecture.md`/security notes in
        `router.py` on why a branch-scoped user must never see another
        branch's buildings.
        """
        column = {"name": Building.name, "created_at": Building.created_at}[sort_by]
        branch_filter = _branch_filter(Building.branch_id, branch_scope)
        filters: list[Any] = [branch_filter] if branch_filter is not None else []
        if status is not None:
            filters.append(Building.is_active.is_(status == ActiveStatus.active))
        return await super().paginate(
            page=page,
            page_size=page_size,
            order_by=_order_clause(column, sort_order),
            filters=filters,
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

    async def get_including_deleted(self, id_: uuid.UUID) -> Floor | None:
        """Like `get`, but does not filter out a soft-deleted floor — see
        `BuildingRepository.get_including_deleted` for why this exists.
        Used to resolve the branch of an existing ReceptionDesk whose parent
        floor was later soft-deleted.
        """
        stmt = select(Floor).where(Floor.id == id_)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        branch_scope: BranchScope,
        building_id: uuid.UUID | None,
        status: ActiveStatus | None,
        access_level: FloorAccessLevel | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[Floor], int]:
        """Joins back to `Building` to filter by branch (`Floor` has no
        `branch_id` column of its own) — the caller's authorized scope, not
        a client-chosen filter. `TenantScopedRepository.paginate` can't
        express a join, so this bypasses it with the same count+page shape.
        """
        column = {"name": Floor.name, "created_at": Floor.created_at}[sort_by]
        conditions: list[Any] = [Floor.deleted_at.is_(None)]
        branch_filter = _branch_filter(Building.branch_id, branch_scope)
        if branch_filter is not None:
            conditions.append(branch_filter)
        if building_id is not None:
            conditions.append(Floor.building_id == building_id)
        if status is not None:
            conditions.append(Floor.is_active.is_(status == ActiveStatus.active))
        if access_level is not None:
            conditions.append(Floor.access_level == access_level)

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

    async def get_by_code(self, branch_id: uuid.UUID, code: str) -> Department | None:
        """Uniqueness is scoped by `branch_id` directly (a real column on
        `Department` as of
        openspec/changes/add-role-management-and-org-field-gaps/design.md
        Decision 4), not by `floor_id`/a join.
        """
        stmt = select(Department).where(
            Department.branch_id == branch_id,
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
        branch_scope: BranchScope,
        floor_id: uuid.UUID | None,
        status: ActiveStatus | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[Department], int]:
        """Filters directly on `Department.branch_id` — no join needed now
        that a department is scoped to a branch directly, not only via its
        (now optional) floor.
        """
        column = {"name": Department.name, "created_at": Department.created_at}[sort_by]
        branch_filter = _branch_filter(Department.branch_id, branch_scope)
        filters: list[Any] = [branch_filter] if branch_filter is not None else []
        if floor_id is not None:
            filters.append(Department.floor_id == floor_id)
        if status is not None:
            filters.append(Department.is_active.is_(status == ActiveStatus.active))
        return await super().paginate(
            page=page,
            page_size=page_size,
            order_by=_order_clause(column, sort_order),
            filters=filters,
        )

    async def get_active(self, id_: uuid.UUID) -> Department | None:
        """Used to validate `departmentId` on invitation/walk-in creation —
        an id must resolve to an *active* row, not merely a non-deleted one
        (visit-info-lookup-api spec.md "Unknown or cross-tenant id is
        rejected").
        """
        stmt = select(Department).where(
            Department.id == id_,
            Department.is_active.is_(True),
            Department.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_active_for_branch(self, branch_id: uuid.UUID) -> list[Department]:
        """Backs `GET /visit-info/departments` (visit-info-lookup-api): the
        active, non-deleted departments of one branch, unpaginated — the
        kiosk dropdown needs the full set, not a page of it.
        """
        stmt = (
            select(Department)
            .where(
                Department.branch_id == branch_id,
                Department.is_active.is_(True),
                Department.deleted_at.is_(None),
            )
            .order_by(Department.name.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_names_by_ids(self, ids: Collection[uuid.UUID]) -> dict[uuid.UUID, str]:
        """Batch id->name lookup for `visit_info/service.py::search_hosts` —
        one query for every host result's `department_id`, not one query per
        host (query-performance.md §2).
        """
        if not ids:
            return {}
        stmt = select(Department.id, Department.name).where(
            Department.id.in_(ids), Department.deleted_at.is_(None)
        )
        rows = (await self.session.execute(stmt)).all()
        return {row[0]: row[1] for row in rows}


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
        branch_scope: BranchScope,
        floor_id: uuid.UUID | None,
        status: DeskStatus | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[ReceptionDesk], int]:
        """Joins through `Floor` → `Building` to filter by the caller's
        authorized scope — see `FloorRepository.list_page`.
        """
        column = {"name": ReceptionDesk.name, "created_at": ReceptionDesk.created_at}[sort_by]
        conditions: list[Any] = [ReceptionDesk.deleted_at.is_(None)]
        branch_filter = _branch_filter(Building.branch_id, branch_scope)
        if branch_filter is not None:
            conditions.append(branch_filter)
        if floor_id is not None:
            conditions.append(ReceptionDesk.floor_id == floor_id)
        if status is not None:
            conditions.append(ReceptionDesk.status == status.value)

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
        branch_scope: BranchScope,
        building_id: uuid.UUID | None,
        gate_type: GateType | None,
        security_level: SecurityLevel | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[SecurityGate], int]:
        """`branch_scope` is always the caller's authorized scope — see
        `BuildingRepository.list_page`.
        """
        column = {"name": SecurityGate.name, "created_at": SecurityGate.created_at}[sort_by]
        branch_filter = _branch_filter(SecurityGate.branch_id, branch_scope)
        filters: list[Any] = [branch_filter] if branch_filter is not None else []
        if building_id is not None:
            filters.append(SecurityGate.building_id == building_id)
        if gate_type is not None:
            filters.append(SecurityGate.gate_type == gate_type.value)
        if security_level is not None:
            filters.append(SecurityGate.high_security.is_(security_level == SecurityLevel.high))
        return await super().paginate(
            page=page,
            page_size=page_size,
            order_by=_order_clause(column, sort_order),
            filters=filters,
        )
