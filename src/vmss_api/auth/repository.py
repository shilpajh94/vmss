import uuid
from collections.abc import Collection, Sequence
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import Permission, Role, User, UserBranchRole
from vmss_api.core.database import TenantScopedRepository
from vmss_api.core.schemas import BranchScope, SortOrder
from vmss_api.org_structure.models import Building, Department, Floor


class UserRepository(TenantScopedRepository[User]):
    """Operates on the `users` table of whichever tenant schema `session` is
    already bound to (see `core/tenancy.py::get_tenant_db`) — tenant
    isolation here is structural, not a WHERE clause. See
    database-architecture.md §3. Inherits `TenantScopedRepository[User]`
    like every other tenant repository, for its `get`/`count`/`paginate`/
    `soft_delete` — `get_by_id` below is that inherited `get`, kept under
    its existing name since it's already the public method every caller
    uses.
    """

    model = User

    async def get_by_id(self, id_: uuid.UUID) -> User | None:
        return await self.get(id_)

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

    async def get_active(self, id_: uuid.UUID) -> User | None:
        """Used to validate `hostId` on invitation/walk-in creation — an id
        must resolve to an *active* employee, not merely a non-deleted one
        (visit-info-lookup-api spec.md "Unknown or cross-tenant id is
        rejected").
        """
        stmt = select(User).where(
            User.id == id_, User.is_active.is_(True), User.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def search_active_by_name_or_email(self, query: str | None, *, limit: int) -> list[User]:
        """Backs `GET /hosts/search` (visit-info-lookup-api): active
        employees whose name or email contains `query`, case-insensitively.
        No `employee_code` requirement — that field is optional directory
        metadata, not a gate on being a valid visit host (design.md
        Decisions). Deactivated employees are excluded via `is_active`, same
        posture as `list_employees_page`. A `None` query returns a browsable
        default list (alphabetical, still capped by `limit`) instead of
        filtering by name/email.
        """
        filters: list[ColumnElement[bool]] = [User.is_active.is_(True), User.deleted_at.is_(None)]
        if query:
            pattern = f"%{query}%"
            filters.append(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
        stmt = select(User).where(*filters).order_by(User.full_name.asc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_branch_role_assignment(
        self, user_id: uuid.UUID, assignment_id: uuid.UUID
    ) -> UserBranchRole | None:
        stmt = select(UserBranchRole).where(
            UserBranchRole.id == assignment_id, UserBranchRole.user_id == user_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def delete_branch_role_assignment(self, assignment: UserBranchRole) -> None:
        """Hard delete, not soft delete: a branch-role grant is disposable
        state, same as an expired OTP code — see `auth/models.py::UserBranchRole`.
        """
        await self.session.delete(assignment)

    async def list_employees_page(
        self,
        *,
        branch_scope: BranchScope,
        department_id: uuid.UUID | None,
        email: str | None,
        role: str | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[User], int]:
        """Every non-deleted user in the tenant, not just ones reconciled
        through `sync_employee_directory`/`create_employee` — an Admin,
        Security, or Reception account created directly (no
        `employee_code`) is still a real person who belongs in this
        directory. Outer-joins `Department -> Floor -> Building` to resolve
        each user's branch for scoping
        (`org_structure/deps.py::public_branch_scope` — this endpoint is
        public, so "scope" is just `X-Branch-ID` or every branch, not a
        caller's authorized branches): a user with no `department_id` set
        still appears in an unscoped ("all branches") listing. They only
        drop out of a *branch-scoped* view (`branch_scope != "all"`), since
        there's no department/floor/building chain to resolve them to that
        specific branch — see `org_structure/router.py`'s module docstring
        for the equivalent pattern applied to
        Building/Floor/Department/Desk/Gate.

        `role` matches via a correlated `EXISTS` against `UserBranchRole`/
        `Role` rather than a join, so a user holding that role at more than
        one branch is never duplicated in the page or double-counted in
        `total` (query-performance.md §1).
        """
        column: Any = {"name": User.full_name, "created_at": User.created_at}[sort_by]
        order = column.desc() if sort_order == SortOrder.desc else column.asc()
        conditions: list[Any] = [User.deleted_at.is_(None)]
        if branch_scope != "all":
            conditions.append(Building.branch_id.in_(branch_scope))
        if department_id is not None:
            conditions.append(User.department_id == department_id)
        if email is not None:
            conditions.append(User.email == email)
        if role is not None:
            conditions.append(
                select(UserBranchRole.id)
                .join(Role, UserBranchRole.role_id == Role.id)
                .where(UserBranchRole.user_id == User.id, Role.name == role)
                .exists()
            )

        joined_from = (
            select(User)
            .outerjoin(Department, User.department_id == Department.id)
            .outerjoin(Floor, Department.floor_id == Floor.id)
            .outerjoin(Building, Floor.building_id == Building.id)
        )

        count_stmt = (
            select(func.count())
            .select_from(User)
            .outerjoin(Department, User.department_id == Department.id)
            .outerjoin(Floor, Department.floor_id == Floor.id)
            .outerjoin(Building, Floor.building_id == Building.id)
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

    async def list_user_ids_holding_role_at_branch(
        self, role_id: uuid.UUID, branch_id: uuid.UUID
    ) -> list[uuid.UUID]:
        """Every user holding `role_id` via a `UserBranchRole` scoped to
        `branch_id`, or company-wide (`branch_id IS NULL`) — the fan-out
        counterpart of `approvals/service.py::_user_holds_role_at_branch`'s
        single-user check, added for
        add-invitation-push-notifications/design.md Decision 3 (push
        dispatch to "every user holding this step's role at this branch").
        """
        stmt = (
            select(UserBranchRole.user_id)
            .where(
                UserBranchRole.role_id == role_id,
                (UserBranchRole.branch_id == branch_id) | (UserBranchRole.branch_id.is_(None)),
            )
            .distinct()
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_hosts_page(
        self, *, page: int, page_size: int, sort_by: str, sort_order: SortOrder
    ) -> tuple[list[User], int]:
        """Backs the public host-directory listing
        (`router.py::list_employee_directory`) — every active user holding
        the `host` role, full stop. Deliberately not branch/department
        scoped like `list_employees_page`: a visitor's "who are you
        visiting" picker shouldn't hide a host just because they have no
        `department_id` set (unlike the employee-directory sync flow, a
        `host` account isn't necessarily reconciled through
        `sync_employee_directory`, so `employee_code`/`department_id` are
        often unset here).
        """
        column: Any = {"name": User.full_name, "created_at": User.created_at}[sort_by]
        order = column.desc() if sort_order == SortOrder.desc else column.asc()
        conditions: list[Any] = [
            User.deleted_at.is_(None),
            User.is_active.is_(True),
            select(UserBranchRole.id)
            .join(Role, UserBranchRole.role_id == Role.id)
            .where(UserBranchRole.user_id == User.id, Role.name == "host")
            .exists(),
        ]

        count_stmt = select(func.count()).select_from(User).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = (
            select(User)
            .where(*conditions)
            .order_by(order)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total


class PermissionRepository:
    """Not a `TenantScopedRepository` — `Permission` is the global catalog
    table (`database-architecture.md` §2: identical across tenants), queried
    through a plain `get_db` session, same as `TenantRepository`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[Permission]:
        stmt = select(Permission).order_by(Permission.code)
        return list((await self.session.execute(stmt)).scalars().all())


class RoleRepository(TenantScopedRepository[Role]):
    model = Role

    async def get_by_name(self, name: str) -> Role | None:
        stmt = select(Role).where(Role.name == name, Role.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_name_case_insensitive(self, name: str) -> Role | None:
        """Backs the role-name "verify" availability check
        (`auth/service.py::verify_role_name`) and create/rename uniqueness
        checks — role names are compared case-insensitively so "Admin" and
        "admin" are treated as the same name, matching how the design's
        role-creation form is expected to warn on a near-duplicate.
        """
        stmt = select(Role).where(func.lower(Role.name) == name.lower(), Role.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self, *, page: int, page_size: int, sort_by: str, sort_order: SortOrder
    ) -> tuple[list[Role], int]:
        column = {"name": Role.name, "created_at": Role.created_at}[sort_by]
        order = column.desc() if sort_order == SortOrder.desc else column.asc()
        return await super().paginate(page=page, page_size=page_size, order_by=order)

    async def get_existing_permissions(self, codes: Collection[str]) -> list[Permission]:
        """Batch lookup for `auth/service.py::create_role`/`update_role` —
        one `WHERE code IN (...)` for the whole requested permission set,
        instead of one lookup per code. See query-performance.md §2.
        """
        if not codes:
            return []
        stmt = select(Permission).where(Permission.code.in_(codes))
        return list((await self.session.execute(stmt)).scalars().all())

    async def has_active_grants(self, role_id: uuid.UUID) -> bool:
        stmt = select(UserBranchRole.id).where(UserBranchRole.role_id == role_id).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None
