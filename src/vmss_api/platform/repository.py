import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.platform.models import (
    PlatformAuditEvent,
    SuperAdmin,
    TenantSchemaVersion,
    TenantUserIndex,
)


class SuperAdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> SuperAdmin | None:
        stmt = select(SuperAdmin).where(SuperAdmin.email == email)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, id_: uuid.UUID) -> SuperAdmin | None:
        stmt = select(SuperAdmin).where(SuperAdmin.id == id_)
        return (await self.session.execute(stmt)).scalar_one_or_none()


class TenantUserIndexRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> TenantUserIndex | None:
        stmt = select(TenantUserIndex).where(TenantUserIndex.email == email)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def delete_by_email(self, email: str) -> None:
        await self.session.execute(delete(TenantUserIndex).where(TenantUserIndex.email == email))

    async def create(
        self, *, email: str, tenant_id: uuid.UUID, user_id: uuid.UUID, flush: bool = True
    ) -> None:
        self.session.add(TenantUserIndex(email=email, tenant_id=tenant_id, user_id=user_id))
        if flush:
            await self.session.flush()


class TenantSchemaVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(self, *, tenant_id: uuid.UUID, revision: str) -> None:
        """Upserts the bookkeeping row for `tenant_id` — provisioning and
        every subsequent tenant-schema migration run call this.
        """
        stmt = (
            insert(TenantSchemaVersion)
            .values(tenant_id=tenant_id, revision=revision)
            .on_conflict_do_update(
                index_elements=[TenantSchemaVersion.tenant_id], set_={"revision": revision}
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def get_all(self) -> dict[uuid.UUID, str]:
        """Every tenant's recorded revision in one query — the drift check
        and the upgrade-all-tenants sweep both need "where does each tenant
        stand" without a per-tenant round trip.
        """
        stmt = select(TenantSchemaVersion.tenant_id, TenantSchemaVersion.revision)
        rows = (await self.session.execute(stmt)).all()
        return {tenant_id: revision for tenant_id, revision in rows}


class PlatformAuditRepository:
    """Writes `platform_audit_events` (global schema): superadmin logins and
    tenant provisioning (audit-trail spec "Form-Builder, Profile, and
    Platform Mutations Are Audited"). Append-only."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(
        self,
        *,
        action: str,
        actor_superadmin_id: uuid.UUID | None = None,
        target_tenant_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            PlatformAuditEvent(
                id=uuid.uuid4(),
                actor_superadmin_id=actor_superadmin_id,
                action=action,
                target_tenant_id=target_tenant_id,
                metadata_=metadata,
            )
        )
