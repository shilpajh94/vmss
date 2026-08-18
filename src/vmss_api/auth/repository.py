import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import Role, User
from vmss_api.core.database import TenantScopedRepository
from vmss_api.core.schemas import SortOrder
from vmss_api.org_structure.models import Building, Department, Floor


class UserRepository:
    """Operates on the `users` table of whichever tenant schema `session` is
    already bound to (see `core/tenancy.py::get_tenant_db`) — tenant
    isolation here is structural, not a WHERE clause. See
    database-architecture.md §3.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, id_: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == id_, User.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_employee_code(self, employee_code: str) -> User | None:
        stmt = select(User).where(User.employee_code == employee_code, User.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_emails(self, emails: Sequence[str]) -> list[User]:
        """Batch lookup for `service.py::sync_employee_directory` — one
        `WHERE email IN (...)` for the whole incoming batch instead of one
        `get_by_email` call per row. See query-performance.md §2.
        """
        if not emails:
            return []
        stmt = select(User).where(User.email.in_(emails), User.deleted_at.is_(None))
        return list((await self.session.execute(stmt)).scalars().all())

    async def deactivate_employees_not_in(self, employee_codes: Sequence[str]) -> list[str]:
        """Single bulk `UPDATE ... WHERE employee_code NOT IN (...)` for
        employees missing from an incoming sync batch, instead of a Python
        loop mutating one ORM object per row. See query-performance.md §3.
        Doesn't touch non-employee accounts (`employee_code IS NULL`).
        """
        stmt = (
            update(User)
            .where(
                User.employee_code.is_not(None),
                User.employee_code.not_in(employee_codes),
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
            .values(is_active=False)
            .returning(User.email)
            .execution_options(synchronize_session=False)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_employees_page(
        self,
        *,
        authorized_branch_id: uuid.UUID,
        department_id: uuid.UUID | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[User], int]:
        """Branch-scoped: joins `Department -> Floor -> Building` to filter
        to employees whose department resolves to the caller's authorized
        branch (`org_structure/deps.py::require_branch_permission`).
        Employees with no `department_id` aren't resolvable to any branch and
        so never appear in a branch-scoped list — see
        `org_structure/router.py`'s module docstring for the equivalent
        pattern applied to Building/Floor/Department/Desk/Gate.
        """
        column: Any = {"name": User.full_name, "created_at": User.created_at}[sort_by]
        order = column.desc() if sort_order == SortOrder.desc else column.asc()
        conditions: list[Any] = [
            User.employee_code.is_not(None),
            User.deleted_at.is_(None),
            Building.branch_id == authorized_branch_id,
        ]
        if department_id is not None:
            conditions.append(User.department_id == department_id)

        joined_from = (
            select(User)
            .join(Department, User.department_id == Department.id)
            .join(Floor, Department.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
        )

        count_stmt = (
            select(func.count())
            .select_from(User)
            .join(Department, User.department_id == Department.id)
            .join(Floor, Department.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .where(*conditions)
        )
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = (
            joined_from.where(*conditions)
            .order_by(order)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total


class RoleRepository(TenantScopedRepository[Role]):
    model = Role

    async def get_by_name(self, name: str) -> Role | None:
        stmt = select(Role).where(Role.name == name, Role.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()
