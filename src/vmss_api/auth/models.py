import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vmss_api.core.config import settings
from vmss_api.core.database import Base, GlobalBase, TimestampMixin

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Uuid, ForeignKey("roles.id"), primary_key=True),
    Column(
        "permission_id",
        Uuid,
        ForeignKey(f"{settings.global_schema_name}.permissions.id"),
        primary_key=True,
    ),
)


class Permission(GlobalBase, TimestampMixin):
    """A fixed, global catalog of permission codes, e.g. `visitors:checkin`.

    Lives in the global schema — the catalog of *what actions exist* is the
    same for every tenant; which roles grant them is tenant-scoped via
    `Role`, which lives in each tenant's own schema. `role_permissions`
    (above) is the tenant-scoped join, with a cross-schema FK back to this
    table. See database-architecture.md §2.
    """

    __tablename__ = "permissions"
    __table_args__ = {"schema": settings.global_schema_name}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255))


class Role(Base, TimestampMixin):
    """Tenant-scoped by schema, not by column — see database-architecture.md
    §2. `name` only needs to be unique within this table, which already only
    ever holds one tenant's rows.
    """

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(String(255))

    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permissions, lazy="selectin"
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Employee-directory fields (org_structure/tasks.md's "Employee directory
    # sync") — optional: a company-wide Admin/Security account created via
    # `create_user` directly has none of these, only a user reconciled through
    # `service.py::sync_employee_directory` does. `department_id` is a
    # cross-package FK into `org_structure`'s tenant-scoped `departments`
    # table — same pattern as `UserBranchRole.branch_id` already crossing
    # into `org_structure` from here. See fastapi-architecture.md §6.
    employee_code: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    designation: Mapped[str | None] = mapped_column(String(100))
    phone_number: Mapped[str | None] = mapped_column(String(50))
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("departments.id"), index=True
    )
    avatar_url: Mapped[str | None] = mapped_column(String(500))

    branch_roles: Mapped[list["UserBranchRole"]] = relationship(lazy="selectin")

    def has_permission(self, code: str, branch_id: uuid.UUID | None = None) -> bool:
        """`branch_id=None` (the default) checks for a company-wide grant
        only — what `require_permission` uses for actions that aren't tied
        to any one branch/location. Passing a branch id also matches a role
        granted specifically at that branch. A `UserBranchRole.branch_id` of
        `None` means "every branch in the company" (used for company-wide
        roles like Admin), so it matches regardless of which `branch_id` is
        being checked.
        """
        for assignment in self.branch_roles:
            if assignment.branch_id is not None and assignment.branch_id != branch_id:
                continue
            if any(p.code == code for p in assignment.role.permissions):
                return True
        return False

    def has_branch_access(self, branch_id: uuid.UUID) -> bool:
        return any(a.branch_id is None or a.branch_id == branch_id for a in self.branch_roles)


class UserBranchRole(Base):
    """A role grant to a user, scoped to one branch — or, when `branch_id`
    is `None`, to every branch in the company (used for company-wide roles
    like Admin). Hard-deleted on revocation, not soft-deleted: the grant
    itself is disposable state, same as an expired OTP code
    (database-architecture.md §4) — the fact that access *was* revoked, by
    whom and when, belongs in `AuditLog`, not a `deleted_at` flag here.
    """

    __tablename__ = "user_branch_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "branch_id", name="uq_user_branch_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("roles.id"))
    branch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("branches.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    role: Mapped[Role] = relationship(lazy="selectin")


class AuditLog(Base):
    """Append-only audit trail for mutating actions within this tenant —
    check-in/out, approval decisions, blacklist changes, admin config
    changes, logins. Required from day one per security-architecture.md §5.
    Written via `auth/audit.py::record_audit_log`, called as a
    `BackgroundTasks` task from every mutating route so the write never
    blocks the request path.

    Deliberately not a `TimestampMixin` table: append-only rows are never
    updated or soft-deleted, so `updated_at`/`deleted_at` would be dead
    columns.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    diff: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
