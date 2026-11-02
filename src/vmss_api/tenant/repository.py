import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.tenant.models import Tenant


class TenantRepository:
    """Not a `TenantScopedRepository` — `Tenant` is the registry table itself,
    lives in the global schema, and is queried through the plain `get_db`
    session (there's no tenant schema to bind yet; resolving one is the
    point of this repository). See database-architecture.md §2.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id_: uuid.UUID) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.id == id_, Tenant.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.slug == slug, Tenant.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_schema_name(self, schema_name: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.schema_name == schema_name, Tenant.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_active(self) -> list[Tenant]:
        """Every active, non-deleted tenant — the fan-out set for per-tenant
        scheduled jobs (`invitations/tasks.py`, `reports/tasks.py`)."""
        stmt = select(Tenant).where(Tenant.is_active.is_(True), Tenant.deleted_at.is_(None))
        return list((await self.session.execute(stmt)).scalars().all())

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[Tenant]:
        stmt = select(Tenant).where(Tenant.deleted_at.is_(None)).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())

    async def create(self, *, name: str, slug: str, schema_name: str) -> Tenant:
        tenant = Tenant(id=uuid.uuid4(), name=name, slug=slug, schema_name=schema_name)
        self.session.add(tenant)
        await self.session.flush()
        return tenant

    async def set_badge_print_flow(self, id_: uuid.UUID, *, enabled: bool) -> Tenant | None:
        """Guarded single-statement update (rather than load-mutate) so the
        change doesn't depend on the registry session's state after
        `get_tenant`'s rollback."""
        stmt = (
            update(Tenant)
            .where(Tenant.id == id_, Tenant.deleted_at.is_(None))
            .values(badge_print_flow_enabled=enabled)
            .returning(Tenant)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
