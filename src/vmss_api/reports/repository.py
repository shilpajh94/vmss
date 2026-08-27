import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import Role, User, UserBranchRole
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
        """`Department.branch_id` is a direct column (as of
        openspec/changes/add-role-management-and-org-field-gaps/design.md
        Decision 4) — no join through `Floor`/`Building` needed, and this
        counts every department regardless of whether it also has a
        `floor_id` set.
        """
        stmt = (
            select(Department.branch_id, func.count())
            .where(Department.deleted_at.is_(None))
            .group_by(Department.branch_id)
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

    async def admin_users(self) -> list[User]:
        """Every active user holding the `"admin"` role, for
        `reports/tasks.py`'s scheduled snapshot recipient list
        (add-background-jobs-and-integration-tests). Not a permission
        check — the job runs unattended, so this is a role-membership
        query, the same shape as `active_employee_counts_by_branch`'s join
        above, not a new `require_permission` code.
        """
        stmt = (
            select(User)
            .join(UserBranchRole, UserBranchRole.user_id == User.id)
            .join(Role, Role.id == UserBranchRole.role_id)
            .where(
                Role.name == "admin",
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
            .distinct()
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def active_employee_counts_by_branch(self) -> dict[uuid.UUID, int]:
        """Joins straight to `Department.branch_id` — see
        `department_counts_by_branch`'s docstring for why the `Floor`/
        `Building` join this used to need is gone.
        """
        stmt = (
            select(Department.branch_id, func.count())
            .select_from(User)
            .join(Department, User.department_id == Department.id)
            .where(
                User.employee_code.is_not(None),
                User.is_active.is_(True),
                User.deleted_at.is_(None),
                Department.deleted_at.is_(None),
            )
            .group_by(Department.branch_id)
        )
        return {branch_id: count for branch_id, count in (await self.session.execute(stmt)).all()}
