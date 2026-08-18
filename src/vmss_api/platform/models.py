import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from vmss_api.core.config import settings
from vmss_api.core.database import GlobalBase, TimestampMixin

_GLOBAL = settings.global_schema_name
_TENANTS_FK = f"{_GLOBAL}.tenants.id"
_SUPERADMINS_FK = f"{_GLOBAL}.superadmins.id"


class SuperAdmin(GlobalBase, TimestampMixin):
    """Platform operator — provisions/manages tenants. Not a member of any
    tenant's schema, so carries no `tenant_id` anywhere. Deliberately
    minimal: no roles/permissions system of its own in this pass (a
    superadmin can do everything platform-level); add one if superadmin
    duties ever need to be split up.
    """

    __tablename__ = "superadmins"
    __table_args__ = {"schema": _GLOBAL}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TenantUserIndex(GlobalBase):
    """Global auth-routing index: `email -> which tenant, which user row`.

    Login receives only an email/password, but a schema-per-tenant `users`
    table can't be queried until the tenant (and therefore its schema) is
    known — this index is that first hop. Kept consistent by being written
    in the same transaction whenever a `User` row is created in any tenant
    (see `auth/service.py`) — global and tenant tables share one connection,
    so that's one atomic commit, not a distributed write. See
    database-architecture.md §2.
    """

    __tablename__ = "tenant_user_index"
    __table_args__ = {"schema": _GLOBAL}

    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey(_TENANTS_FK), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantSchemaVersion(GlobalBase):
    """Bookkeeping cache of which Alembic revision each tenant's schema is
    on, updated by `platform/service.py` after every provisioning/upgrade
    run. Alembic's own per-schema `alembic_version` table (inside each
    tenant schema, via `alembic_tenant/env.py`'s `version_table_schema`) is
    still the source of truth — this table exists so "what version is every
    tenant on" is one global-schema query instead of connecting into every
    tenant schema to check.
    """

    __tablename__ = "tenant_schema_versions"
    __table_args__ = {"schema": _GLOBAL}

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey(_TENANTS_FK), primary_key=True)
    revision: Mapped[str] = mapped_column(String(32))
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PlatformAuditEvent(GlobalBase):
    """Append-only audit trail for platform-level actions (tenant
    provisioned/suspended, superadmin login) — distinct from the
    tenant-scoped `AuditLog` (`auth/models.py`) that covers mutations
    *within* a tenant. See security-architecture.md §5.
    """

    __tablename__ = "platform_audit_events"
    __table_args__ = {"schema": _GLOBAL}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_superadmin_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey(_SUPERADMINS_FK))
    action: Mapped[str] = mapped_column(String(100), index=True)
    target_tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey(_TENANTS_FK))
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
