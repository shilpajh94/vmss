import asyncio
from logging.config import fileConfig

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.schema import SchemaItem

from alembic import context

# `Base` and `GlobalBase` share one MetaData object (core/database.py), so
# importing *any* model module — including transitively, e.g. `auth.models`
# for `Permission` also pulls in that module's tenant-scoped `Role`/`User`/
# `AuditLog` — populates the same shared metadata with both families'
# tables. `include_object` below (not the import list) is what actually
# keeps this environment's autogenerate scoped to the global schema only.
from vmss_api.auth.models import Permission  # noqa: F401
from vmss_api.core.config import settings
from vmss_api.core.database import GlobalBase
from vmss_api.platform import models as platform_models  # noqa: F401
from vmss_api.tenant import models as tenant_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = GlobalBase.metadata


def include_object(
    object_: SchemaItem,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: SchemaItem | None,
) -> bool:
    """Restricts autogenerate to the global schema — see the import comment
    above for why `target_metadata` alone isn't enough of a filter anymore.
    """
    if type_ == "table":
        return object_.schema == settings.global_schema_name
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=settings.global_schema_name,
        include_schemas=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=settings.global_schema_name,
        include_schemas=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable: AsyncEngine = create_async_engine(settings.database_url)
    async with connectable.begin() as connection:
        await connection.execute(
            text(f'CREATE SCHEMA IF NOT EXISTS "{settings.global_schema_name}"')
        )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
