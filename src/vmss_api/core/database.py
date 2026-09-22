import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, Protocol

from sqlalchemy import DateTime, MetaData, func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from vmss_api.core.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# `Base` and `GlobalBase` deliberately share ONE MetaData instance (below),
# not two. A cross-schema `ForeignKey("global.permissions.id")` string
# (auth/models.py's `role_permissions`) only resolves to the *real* target
# table if that table is registered in the same MetaData collection —
# otherwise SQLAlchemy silently fabricates an empty stub table with that
# name, and `relationship(secondary=...)` join-condition inference fails
# with a confusing "no foreign keys linking these tables" error. Neither
# base sets a metadata-level default schema, since that default would apply
# to *every* table on it, including `Base`'s tenant tables, which must stay
# schema-less; each `GlobalBase` model instead declares its own
# `schema=settings.global_schema_name` via `__table_args__`.
_metadata = MetaData()


class Base(DeclarativeBase):
    """Declarative base for tenant-scoped tables.

    Tables here carry no explicit schema — which physical Postgres schema
    they resolve against is decided per-connection via `schema_translate_map`
    (see `get_tenant_db` below), not baked into the table object. A session
    built from the plain `engine`/`AsyncSessionLocal` (no translate map) will
    fail to find these tables at all — that's intentional, see
    database-architecture.md §2.
    """

    metadata = _metadata


class GlobalBase(DeclarativeBase):
    """Declarative base for cross-tenant registry tables (tenants,
    superadmins, the auth index, the permission catalog, ...).

    Reachable from any session regardless of that connection's
    `schema_translate_map`, since every concrete model built on this base
    declares its own explicit schema — see `tenant/models.py::Tenant` for
    the pattern every `GlobalBase` model follows:
    `__table_args__ = {"schema": settings.global_schema_name}`.
    """

    metadata = _metadata


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Plain, schema-agnostic session — usable for `GlobalBase` tables from
    any request. Never usable for tenant tables (`Base`) since there's no
    tenant schema bound yet; use `get_tenant_db` (`core/tenancy.py`) for
    those.
    """
    async with AsyncSessionLocal() as session:
        yield session


@lru_cache(maxsize=256)
def _tenant_bound_engine(schema_name: str) -> AsyncEngine:
    """One lightweight `execution_options` proxy per tenant schema, cached so
    repeated requests for the same tenant don't rebuild it. Shares the
    underlying connection pool with `engine` — this is not a second engine.
    """
    return engine.execution_options(schema_translate_map={None: schema_name})


@asynccontextmanager
async def tenant_session_scope(schema_name: str) -> AsyncIterator[AsyncSession]:
    """Opens a session whose `Base` (tenant) table queries resolve against
    `schema_name` instead of failing to resolve at all. Used both as a
    FastAPI dependency (`core/tenancy.py::get_tenant_db`) and imperatively
    wherever a tenant schema is only known mid-function — e.g. login's
    second hop (`auth/service.py`) or tenant provisioning
    (`platform/service.py`). See database-architecture.md §2.
    """
    async with AsyncSession(_tenant_bound_engine(schema_name), expire_on_commit=False) as session:
        yield session


class _SoftDeletableModel(Protocol):
    """What `TenantScopedRepository` needs any model it manages to have."""

    id: Mapped[uuid.UUID]
    deleted_at: Mapped[datetime | None]


class TenantScopedRepository[ModelT: _SoftDeletableModel]:
    """Base repository for tables living in a tenant's own Postgres schema.

    Tenant isolation is structural here, not a WHERE clause: the `session`
    passed in is already bound to exactly one tenant's schema via
    `schema_translate_map` (see `core/tenancy.py::get_tenant_db`), so this
    base class only needs the soft-delete filter. A repository that builds
    its own `AsyncSession`/engine instead of taking the tenant-bound one it's
    given is a bug — it's how a query could silently fall through to no
    schema (and fail) or, if search_path is ever misconfigured, another
    tenant's schema. See database-architecture.md §3.
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id_: uuid.UUID) -> ModelT | None:
        stmt = select(self.model).where(self.model.id == id_, self.model.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def count(self, *filters: Any) -> int:
        stmt = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.deleted_at.is_(None), *filters)
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def paginate(
        self, *, page: int, page_size: int, order_by: Any, filters: Sequence[Any] = ()
    ) -> tuple[list[ModelT], int]:
        """Shared pagination primitive for the org-structure-style
        `list_page` methods (api-conventions.md §1): one count query plus one
        page query, both scoped by the same soft-delete + caller-supplied
        `filters`. `order_by` is a resolved SQLAlchemy column expression
        (e.g. `Model.name.asc()`), never a raw client-supplied string — see
        api-conventions.md §1 on why sort columns go through an explicit
        whitelist upstream, in the feature's own repository method, not here.

        Deliberately named differently from every subclass's own
        `list_page` (which each takes different filter kwargs) rather than
        being itself overridden — same-named methods with incompatible
        signatures is a Liskov violation mypy (rightly) flags.

        Defined (along with `count`) *before* `list` below: annotating this
        method's return type as `list[ModelT]` after a method literally named
        `list` has been defined in this same class body would resolve `list`
        against that method, not the builtin — class-body annotations
        evaluate in the class namespace, which the `list` method assignment
        overwrites. Order matters here, not just style.
        """
        total = await self.count(*filters)
        stmt = (
            select(self.model)
            .where(self.model.deleted_at.is_(None), *filters)
            .order_by(order_by)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total

    async def paginate_with_joins(
        self,
        *,
        page: int,
        page_size: int,
        order_by: Any,
        joins: Sequence[tuple[Any, Any]],
        filters: Sequence[Any] = (),
    ) -> tuple[list[ModelT], int]:
        """Same count+page shape as `paginate`, for the `list_page` methods
        that need to join to another table to express their caller's
        authorized scope (e.g. `Floor`/`ReceptionDesk` have no `branch_id`
        of their own — `FloorRepository.list_page` joins to `Building` to
        filter by branch). `joins` is `(target, onclause)` pairs applied via
        `.join()`, in order, to both the count and page queries.
        """
        count_stmt = select(func.count()).select_from(self.model)
        stmt = select(self.model)
        for target, onclause in joins:
            count_stmt = count_stmt.join(target, onclause)
            stmt = stmt.join(target, onclause)
        conditions = (self.model.deleted_at.is_(None), *filters)
        count_stmt = count_stmt.where(*conditions)
        stmt = (
            stmt.where(*conditions)
            .order_by(order_by)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[ModelT]:
        stmt = select(self.model).where(self.model.deleted_at.is_(None)).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())

    async def soft_delete(self, obj: ModelT) -> None:
        obj.deleted_at = datetime.now(UTC)  # type: ignore[assignment]
        await self.session.flush()
