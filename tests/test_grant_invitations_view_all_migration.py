"""Tenant migration `d4e6f8a0b2c3_grant_invitations_view_all`
(restrict-delegated-invitation-visibility): every role holding
`invitations:view` except `host` gains `invitations:view-all`, including
custom roles `seed_default_roles` never touches. Runs the revision's
`upgrade()` directly against the test tenant schema through an Alembic
operations context, same as `test_heal_stale_form_config_migration.py`.
"""

import importlib.util
import uuid
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import PermissionFactory, RoleFactory
from vmss_api.auth.models import Permission, role_permissions

_TENANT_SCHEMA = "tenant_acme_test"
_MIGRATION = (
    Path(__file__).parents[1] / "alembic_tenant/versions/d4e6f8a0b2c3_grant_invitations_view_all.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("grant_invitations_view_all", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run_upgrade(db_session: AsyncSession) -> None:
    migration = _load_migration()

    def _upgrade(sync_conn) -> None:
        context = MigrationContext.configure(
            sync_conn, opts={"version_table_schema": _TENANT_SCHEMA}
        )
        with Operations.context(context):
            migration.upgrade()

    connection = await db_session.connection()
    await connection.run_sync(_upgrade)
    await db_session.commit()


async def _codes(db_session: AsyncSession, role_id: uuid.UUID) -> set[str]:
    rows = await db_session.execute(
        select(Permission.code)
        .join(role_permissions, role_permissions.c.permission_id == Permission.id)
        .where(role_permissions.c.role_id == role_id)
    )
    return set(rows.scalars())


async def test_grants_view_all_to_every_non_host_view_role_and_is_idempotent(
    db_session: AsyncSession,
) -> None:
    view = PermissionFactory.build(
        id=uuid.uuid4(), code="invitations:view", description="invitations:view"
    )
    manager = RoleFactory.build(id=uuid.uuid4(), name="manager", permissions=[view])
    host = RoleFactory.build(id=uuid.uuid4(), name="host", permissions=[view])
    bystander = RoleFactory.build(id=uuid.uuid4(), name="bystander", permissions=[])
    db_session.add_all([view, manager, host, bystander])
    await db_session.commit()
    manager_id, host_id, bystander_id = manager.id, host.id, bystander.id

    await _run_upgrade(db_session)
    await _run_upgrade(db_session)

    assert await _codes(db_session, manager_id) == {"invitations:view", "invitations:view-all"}
    assert await _codes(db_session, host_id) == {"invitations:view"}
    assert await _codes(db_session, bystander_id) == set()
    catalog_rows = await db_session.scalar(
        select(func.count())
        .select_from(Permission)
        .where(Permission.code == "invitations:view-all")
    )
    assert catalog_rows == 1
