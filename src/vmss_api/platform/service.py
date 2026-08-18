import uuid
from pathlib import Path
from typing import Annotated, Any

import anyio
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from alembic import command
from vmss_api.auth.rbac_catalog import seed_default_roles
from vmss_api.core.config import settings
from vmss_api.core.database import get_db, tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.core.security import create_platform_access_token, verify_password
from vmss_api.core.tenancy import get_bearer_payload
from vmss_api.platform.models import SuperAdmin
from vmss_api.platform.repository import (
    SuperAdminRepository,
    TenantSchemaVersionRepository,
)
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.repository import TenantRepository

# repo root: src/vmss_api/platform/service.py -> platform -> vmss_api -> src -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_TENANT_ALEMBIC_INI = _REPO_ROOT / "alembic_tenant.ini"


async def _create_schema(schema_name: str) -> None:
    """A short-lived engine, not the app's shared pooled one — provisioning
    is rare enough that pooling doesn't matter, and reading
    `settings.database_url` fresh on every call (rather than baking in
    whatever it was at process-start, like the shared `engine` does) is what
    makes this testable against a different database.
    """
    admin_engine = create_async_engine(settings.database_url)
    async with admin_engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
    await admin_engine.dispose()


def _run_tenant_migrations_sync(schema_name: str, database_url: str) -> str:
    """Runs the tenant Alembic environment (`alembic_tenant/`) against
    exactly `schema_name`. Alembic's command API is sync — called via
    `anyio.to_thread.run_sync` per database-architecture.md §7.
    """
    cfg = Config(str(_TENANT_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", database_url)
    cfg.attributes["tenant_schema"] = schema_name
    command.upgrade(cfg, "head")
    return ScriptDirectory.from_config(cfg).get_current_head() or "unknown"


async def create_tenant(db: AsyncSession, *, name: str, slug: str) -> Tenant:
    """Provisions a brand-new tenant end to end: creates its Postgres schema,
    runs every tenant migration against it, then records the registry row
    and bookkeeping revision. Schema creation/migration happen *before* the
    `tenants` row is inserted — if provisioning fails partway, there's no
    dangling registry row pointing at a broken schema, just an empty or
    partially-migrated schema that a retry (idempotent: `CREATE SCHEMA IF
    NOT EXISTS` + Alembic's own already-applied-revision tracking) can
    finish.
    """
    if await TenantRepository(db).get_by_slug(slug) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Tenant slug already exists"
        )

    schema_name = f"{settings.tenant_schema_prefix}{slug}"
    await _create_schema(schema_name)
    revision = await anyio.to_thread.run_sync(
        _run_tenant_migrations_sync, schema_name, settings.database_url
    )

    async with tenant_session_scope(schema_name) as tenant_db:
        await seed_default_roles(tenant_db)
        await tenant_db.commit()

    tenant = await TenantRepository(db).create(name=name, slug=slug, schema_name=schema_name)
    await TenantSchemaVersionRepository(db).record(tenant_id=tenant.id, revision=revision)
    await db.commit()

    logger.info("tenant_provisioned", tenant_id=str(tenant.id), slug=slug, schema=schema_name)
    return tenant


async def authenticate_superadmin(db: AsyncSession, email: str, password: str) -> SuperAdmin:
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
    )
    admin = await SuperAdminRepository(db).get_by_email(email)
    if admin is None or not admin.is_active:
        logger.warning("platform_login_failed", email=email, reason="not_found_or_inactive")
        raise invalid_credentials
    if not verify_password(password, admin.hashed_password):
        logger.warning("platform_login_failed", email=email, reason="invalid_password")
        raise invalid_credentials
    return admin


def issue_platform_token(admin: SuperAdmin) -> str:
    return create_platform_access_token(admin.id)


async def get_current_superadmin(
    payload: Annotated[dict[str, Any], Depends(get_bearer_payload)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuperAdmin:
    """Superadmin's own auth chain — deliberately separate from
    `core/tenancy.py`'s tenant-user chain: a `platform_access` token carries
    no `tenant_id` and must never be accepted where a tenant-user `access`
    token is expected, or vice versa.
    """
    if payload.get("type") != "platform_access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a platform token")
    admin = await SuperAdminRepository(db).get_by_id(uuid.UUID(payload["sub"]))
    if admin is None or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Superadmin not found or inactive"
        )
    return admin
