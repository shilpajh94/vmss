import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from vmss_api.core.database import Base, TimestampMixin

# Every partial unique index below is scoped to `deleted_at IS NULL` so a
# soft-deleted row's code/number is actually freed for reuse — the plain,
# unconditional `UniqueConstraint`/unique-index this replaced kept a
# soft-deleted row's code reserved forever, contradicting the app-level
# `get_by_code`/`get_by_number` checks in `repository.py`, which already
# filter `deleted_at IS NULL`. See
# openspec/changes/harden-org-structure-crud/design.md Decision 1.
_NOT_DELETED = text("deleted_at IS NULL")


class Company(Base, TimestampMixin):
    """This tenant's own business profile — legal name, registration/tax id,
    contact info, logo. The root of the org chart `Branch`/`Building`/
    `Floor`/`Department` hang off of.

    Deliberately distinct from `tenant.models.Tenant` (global schema):
    `Tenant` is the SaaS/schema boundary ("which tenant is this" —
    `database-architecture.md` §2); `Company` is this tenant's own business
    identity. Exactly one row is expected per tenant schema, enforced in
    `service.py` (a business rule, not a DB constraint) — same posture as
    `Tenant` having exactly one row today without a DB-level singleton
    constraint (`database-architecture.md` §2).
    """

    __tablename__ = "companies"
    __table_args__ = (
        Index(
            "uq_companies_registration_number",
            "registration_number",
            unique=True,
            postgresql_where=_NOT_DELETED,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    legal_name: Mapped[str] = mapped_column(String(255))
    registration_number: Mapped[str | None] = mapped_column(String(100))
    tax_id: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(String(500))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Branch(Base, TimestampMixin):
    """A physical location of the single company operating this tenant —
    the unit access is scoped to via the `X-Branch-ID` header
    (`org_structure/deps.py::get_branch_context`) and RBAC grants
    (`auth/models.py::UserBranchRole`) are tied to. Tenant-scoped by schema,
    not by column, same as `Role`/`User` — see database-architecture.md §2.
    """

    __tablename__ = "branches"
    __table_args__ = (
        Index("ix_branches_code", "code", unique=True, postgresql_where=_NOT_DELETED),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Building(Base, TimestampMixin):
    """A building at one `Branch`. Hierarchy: Branch → Building → Floor →
    Department (project decision — see docs/features/org_structure.md).
    """

    __tablename__ = "buildings"
    __table_args__ = (
        Index(
            "uq_building_branch_code",
            "branch_id",
            "code",
            unique=True,
            postgresql_where=_NOT_DELETED,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Floor(Base, TimestampMixin):
    """A floor within one `Building`."""

    __tablename__ = "floors"
    __table_args__ = (
        Index(
            "uq_floor_building_number",
            "building_id",
            "floor_number",
            unique=True,
            postgresql_where=_NOT_DELETED,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    building_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("buildings.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    floor_number: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Department(Base, TimestampMixin):
    """A department located on one `Floor` — and transitively that floor's
    building/branch.
    """

    __tablename__ = "departments"
    __table_args__ = (
        Index(
            "uq_department_floor_code",
            "floor_id",
            "code",
            unique=True,
            postgresql_where=_NOT_DELETED,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    floor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("floors.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ReceptionDesk(Base, TimestampMixin):
    """A staffed reception desk on one `Floor` — where a visitor checks in.
    No hardware/badge-printer integration yet; that's `access_control`'s
    concern once built (`project-rules.md`'s directory-structure note).
    """

    __tablename__ = "reception_desks"
    __table_args__ = (
        Index("uq_desk_floor_code", "floor_id", "code", unique=True, postgresql_where=_NOT_DELETED),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    floor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("floors.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SecurityGate(Base, TimestampMixin):
    """A physical entry/exit gate at one `Branch`, optionally narrowed to one
    `Building` on a multi-building campus. `gate_type` is a plain string
    (`schemas.py::GateType` validates it at the API boundary) rather than a
    DB-level enum, to keep this migration a single `CREATE TABLE` — no
    hardware/RFID integration hook here yet, same caveat as `ReceptionDesk`.
    """

    __tablename__ = "security_gates"
    __table_args__ = (
        Index(
            "uq_gate_branch_code", "branch_id", "code", unique=True, postgresql_where=_NOT_DELETED
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), index=True)
    building_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("buildings.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(50))
    gate_type: Mapped[str] = mapped_column(String(20), default="both")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
