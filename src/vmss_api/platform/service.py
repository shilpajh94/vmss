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
from vmss_api.core.database import AsyncSessionLocal, get_db, tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.core.masking import mask_identifier
from vmss_api.core.security import create_platform_access_token, verify_password
from vmss_api.core.tenancy import get_bearer_payload
from vmss_api.form_builder.service import seed_default_form_config
from vmss_api.platform.models import SuperAdmin
from vmss_api.platform.repository import (
    PlatformAuditRepository,
    SuperAdminRepository,
    TenantSchemaVersionRepository,
)
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.repository import TenantRepository


def _find_repo_root() -> Path:
    """`alembic_tenant.ini`/`alembic_tenant/` aren't part of the wheel
    (`pyproject.toml`'s wheel `packages` is `src/vmss_api` only) — they're
    copied straight into `WORKDIR /app` by the Dockerfile. A fixed
    `Path(__file__).resolve().parents[N]` guess breaks once the project is
    installed `--no-editable` (the production image): `__file__` then
    resolves under `.venv/lib/.../site-packages/vmss_api/...`, with no
    `src/` layer above it to walk up through. The container and `ddev exec
    uv run ...` both always run with cwd at the repo root, so anchor there
    first and only fall back to walking up from this file for other
    invocation styles (e.g. an editable dev install run from elsewhere).
    """
    for candidate in (Path.cwd(), *Path(__file__).resolve().parents):
        if (candidate / "alembic_tenant.ini").is_file():
            return candidate
    return Path.cwd()


_REPO_ROOT = _find_repo_root()
_TENANT_ALEMBIC_INI = _REPO_ROOT / "alembic_tenant.ini"


class TenantMigrationHeadsAmbiguousError(RuntimeError):
    """`alembic_tenant`'s revision tree currently has more than one head —
    a branch was authored against a stale `down_revision` and never
    reconciled with a merge revision. Raised instead of letting Alembic's
    own `CommandError` propagate, so callers can detect and report this
    distinctly from an ordinary "tenant behind head" (`tenant-schema-
    maintenance` spec's multi-head scenarios).
    """

    def __init__(self, heads: list[str]) -> None:
        self.heads = heads
        super().__init__(
            "alembic_tenant has multiple migration heads and needs a merge "
            f"revision: {', '.join(sorted(heads))}"
        )


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


def _run_tenant_migrations_sync(schema_name: str) -> str:
    """Runs the tenant Alembic environment (`alembic_tenant/`) against
    exactly `schema_name`. Alembic's command API is sync — called via
    `anyio.to_thread.run_sync` per database-architecture.md §7.

    The database URL isn't passed through `Config` — `alembic_tenant/env.py`
    builds its engine from `settings.database_url` directly, not from
    `sqlalchemy.url` in the ini. Passing it here would just be dead
    configuration, and `Config.set_main_option` chokes on a literal `%`
    (e.g. a URL-encoded `@` in the password) since `ConfigParser` treats `%`
    as its own interpolation syntax.

    Shared by `create_tenant` (a brand-new schema) and
    `upgrade_tenant_schema` (an existing schema catching up to a later
    migration head) — both cases are just "run every pending revision", so
    there's nothing tenant-creation-specific about this function.
    """
    cfg = Config(str(_TENANT_ALEMBIC_INI))
    cfg.attributes["tenant_schema"] = schema_name
    command.upgrade(cfg, "head")
    return ScriptDirectory.from_config(cfg).get_current_head() or "unknown"


def get_tenant_migration_head() -> str:
    """The current `alembic_tenant` migration head, independent of any
    tenant's applied revision — used to detect drift without needing a
    connection into every tenant schema.

    Raises `TenantMigrationHeadsAmbiguousError` if the revision tree
    currently has more than one head, checked via `get_heads()` (which
    never raises) rather than `get_current_head()` (which raises
    Alembic's own undifferentiated `CommandError` for the same
    condition).
    """
    cfg = Config(str(_TENANT_ALEMBIC_INI))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    if len(heads) > 1:
        raise TenantMigrationHeadsAmbiguousError(list(heads))
    return heads[0] if heads else "unknown"


async def upgrade_tenant_schema(db: AsyncSession, *, tenant: Tenant) -> str:
    """Brings an *existing* tenant fully up to date: applies any pending
    `alembic_tenant` revisions, then re-runs the same two seed steps
    `create_tenant` runs for a brand-new schema (`seed_default_roles`,
    `seed_default_form_config`) — both already idempotent, both already
    designed to backfill a catalog addition onto a tenant seeded before that
    addition existed (see `seed_default_roles`'s own docstring). Without
    this, a migration that adds a new permission-gated feature (form-builder)
    leaves an existing tenant's schema current but its admin role still
    403'd on that feature — confirmed directly against the dev tenant.
    """
    revision = await anyio.to_thread.run_sync(_run_tenant_migrations_sync, tenant.schema_name)
    async with tenant_session_scope(tenant.schema_name) as tenant_db:
        await seed_default_roles(tenant_db)
        await seed_default_form_config(tenant_db)
        await tenant_db.commit()
    await TenantSchemaVersionRepository(db).record(tenant_id=tenant.id, revision=revision)
    await db.commit()
    logger.info(
        "tenant_schema_upgraded", tenant_id=str(tenant.id), slug=tenant.slug, revision=revision
    )
    return revision


async def upgrade_all_tenant_schemas(db: AsyncSession) -> list[tuple[Tenant, str]]:
    """Applies pending `alembic_tenant` revisions to every tenant, and always
    re-syncs every tenant's RBAC/form-builder seed data via
    `upgrade_tenant_schema` regardless of migration state — catalog drift (a
    permission added to `auth/rbac_catalog.py` without any accompanying
    Alembic revision) and schema drift (a pending migration) are
    independent, so a tenant already at the migration head can still be
    missing a catalog permission. An earlier version of this function
    skipped tenants already at head entirely, which silently skipped their
    reseed too — confirmed directly: that's exactly why re-running it against
    the dev tenant after the schema-only fix still left its admin role
    403'd on `form-builder:view` until this was corrected.

    Returns only the (tenant, new revision) pairs whose *migration* revision
    actually changed — a tenant already at head but re-seeded isn't reported
    as "upgraded" from a migration point of view, matching
    `tenant-schema-maintenance`'s "left unchanged" scenario for the
    migration itself (both the Alembic call and the seed calls are cheap,
    idempotent no-ops for such a tenant, so nothing is wasted by still
    running them).

    Raises `TenantMigrationHeadsAmbiguousError` (via `get_tenant_migration_head`)
    before touching any tenant if the `alembic_tenant` revision tree
    currently has more than one head — no tenant is partially migrated
    from just one of the unmerged branches (`tenant-schema-maintenance`
    spec's multi-head scenario).
    """
    head = get_tenant_migration_head()
    tenants = await TenantRepository(db).list(limit=10_000)
    current_versions = await TenantSchemaVersionRepository(db).get_all()

    upgraded: list[tuple[Tenant, str]] = []
    for tenant in tenants:
        was_at_head = current_versions.get(tenant.id) == head
        revision = await upgrade_tenant_schema(db, tenant=tenant)
        if not was_at_head:
            upgraded.append((tenant, revision))
    return upgraded


async def find_tenants_behind_head(db: AsyncSession) -> list[Tenant]:
    """Tenants whose recorded `tenant_schema_versions` revision doesn't match
    the current `alembic_tenant` head — read-only, used by the startup drift
    check. A tenant with no recorded version at all (shouldn't happen post
    `create_tenant`, but treated defensively) counts as behind.

    Raises `TenantMigrationHeadsAmbiguousError` (via `get_tenant_migration_head`)
    if the revision tree currently has more than one head — the caller
    (`backend_pre_start.py::check_tenant_schema_drift`) is expected to
    handle this as a distinct, higher-severity condition, not conflate it
    with an empty "no tenant is behind" result.
    """
    head = get_tenant_migration_head()
    tenants = await TenantRepository(db).list(limit=10_000)
    current_versions = await TenantSchemaVersionRepository(db).get_all()
    return [tenant for tenant in tenants if current_versions.get(tenant.id) != head]


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
    revision = await anyio.to_thread.run_sync(_run_tenant_migrations_sync, schema_name)

    async with tenant_session_scope(schema_name) as tenant_db:
        await seed_default_roles(tenant_db)
        await seed_default_form_config(tenant_db)
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

    async def _audit_failure(reason: str) -> None:
        # Inline, not a background task: FastAPI skips background tasks
        # when the route raises, and a failed login is the event that most
        # needs to be on the platform trail.
        PlatformAuditRepository(db).add(
            action="platform_login_failed",
            actor_superadmin_id=admin.id if admin is not None else None,
            metadata={"email": mask_identifier(email), "reason": reason},
        )
        await db.commit()

    if admin is None or not admin.is_active:
        logger.warning(
            "platform_login_failed", email=mask_identifier(email), reason="not_found_or_inactive"
        )
        await _audit_failure("not_found_or_inactive")
        raise invalid_credentials
    if not verify_password(password, admin.hashed_password):
        logger.warning(
            "platform_login_failed", email=mask_identifier(email), reason="invalid_password"
        )
        await _audit_failure("invalid_password")
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


async def list_tenants(db: AsyncSession) -> list[Tenant]:
    return await TenantRepository(db).list()


async def record_platform_event(
    *,
    action: str,
    actor_superadmin_id: uuid.UUID | None = None,
    target_tenant_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Background-task writer for a platform audit event, with its own
    global-schema session (the request's has closed by the time it runs)."""
    async with AsyncSessionLocal() as session:
        PlatformAuditRepository(session).add(
            action=action,
            actor_superadmin_id=actor_superadmin_id,
            target_tenant_id=target_tenant_id,
            metadata=metadata,
        )
        await session.commit()
