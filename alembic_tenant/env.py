import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import context

# `Base` and `GlobalBase` share one MetaData object (core/database.py), so
# this import also pulls the global-schema `Permission` class into the same
# metadata. `include_object` below (not the import list) is what actually
# keeps this environment's autogenerate scoped to tenant tables only — see
# `alembic/env.py`'s matching comment for the global side of this.
from vmss_api.approvals.models import InvitationApprovalStep  # noqa: F401
from vmss_api.audit_trail.models import AuditReportJob  # noqa: F401
from vmss_api.auth.models import (  # noqa: F401
    AuditLog,
    Permission,
    Role,
    User,
    UserBranchRole,
    role_permissions,
)
from vmss_api.core.config import settings
from vmss_api.core.database import Base
from vmss_api.devices.models import Device, TenantSettings  # noqa: F401
from vmss_api.form_builder.models import (  # noqa: F401
    FormConfigVersion,
    FormField,
    FormStep,
)
from vmss_api.invitations.models import (  # noqa: F401
    Invitation,
    InvitationVehicle,
    InvitationVisitor,
)
from vmss_api.kiosks.models import Kiosk  # noqa: F401
from vmss_api.notifications.models import DeviceToken  # noqa: F401
from vmss_api.org_structure.models import (  # noqa: F401
    Branch,
    Building,
    Company,
    Department,
    Floor,
    ReceptionDesk,
    SecurityGate,
)
from vmss_api.sso.models import SsoProvider, SsoRoleMapping  # noqa: F401
from vmss_api.visit_info.models import VisitDuration, VisitPurpose  # noqa: F401
from vmss_api.visitors.models import ApprovalWorkflowRule, VisitorCategory  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(object_, name, type_, reflected, compare_to):
    """Restricts autogenerate to tenant-scoped (schema-less) tables — see the
    import comment above.
    """
    if type_ == "table":
        return object_.schema is None
    return True


def _tenant_schema() -> str:
    """The schema this run targets.

    Programmatic callers (`platform/service.py::_run_tenant_migrations_sync`)
    set `config.attributes["tenant_schema"]`; manual CLI use passes
    `-x tenant_schema=<name>` instead. Either way, the schema must already
    exist — `CREATE SCHEMA` is the provisioning service's job
    (`platform/service.py::_create_schema`), not a migration's.
    """
    from_attributes = context.config.attributes.get("tenant_schema")
    if from_attributes:
        return from_attributes
    schema = context.get_x_argument(as_dictionary=True).get("tenant_schema")
    if not schema:
        raise RuntimeError(
            "alembic_tenant requires a target schema: pass -x tenant_schema=<name> "
            "on the CLI, or set config.attributes['tenant_schema'] programmatically."
        )
    return schema


def run_migrations_offline() -> None:
    schema = _tenant_schema()
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=schema,
        include_schemas=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection, schema: str) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=schema,
        include_schemas=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    schema = _tenant_schema()
    connectable: AsyncEngine = create_async_engine(settings.database_url).execution_options(
        schema_translate_map={None: schema}
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations, schema)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
