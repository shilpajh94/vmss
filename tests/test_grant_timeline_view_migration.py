"""Tenant migration `a7c3e5f19b24_grant_timeline_view` (add-visit-timeline):
the standard admin, reception and security roles gain `timeline:view`; host
and custom roles are left alone. Runs the revision's `upgrade()` directly
against the test tenant schema, same as the other `test_grant_*` migrations.
"""

import importlib.util
import uuid
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import RoleFactory
from vmss_api.auth.models import Permission, role_permissions

_TENANT_SCHEMA = "tenant_acme_test"
_MIGRATION = (
    Path(__file__).parents[1] / "alembic_tenant/versions/a7c3e5f19b24_grant_timeline_view.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("grant_timeline_view", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run(db_session: AsyncSession, fn_name: str) -> None:
    migration = _load_migration()

    def _call(sync_conn) -> None:
        context = MigrationContext.configure(
            sync_conn, opts={"version_table_schema": _TENANT_SCHEMA}
        )
        with Operations.context(context):
            getattr(migration, fn_name)()

    connection = await db_session.connection()
    await connection.run_sync(_call)
    await db_session.commit()


async def _codes(db_session: AsyncSession, role_id: uuid.UUID) -> set[str]:
    rows = await db_session.execute(
        select(Permission.code)
        .join(role_permissions, role_permissions.c.permission_id == Permission.id)
        .where(role_permissions.c.role_id == role_id)
    )
    return set(rows.scalars())


async def test_grants_timeline_view_to_standard_roles_only_and_is_reversible(
    db_session: AsyncSession,
) -> None:
    roles = {
        name: RoleFactory.build(id=uuid.uuid4(), name=name, permissions=[])
        for name in ("admin", "reception", "security", "host", "custom")
    }
    db_session.add_all(roles.values())
    await db_session.commit()
    ids = {name: role.id for name, role in roles.items()}

    await _run(db_session, "upgrade")
    await _run(db_session, "upgrade")

    for name in ("admin", "reception", "security"):
        assert await _codes(db_session, ids[name]) == {"timeline:view"}
    for name in ("host", "custom"):
        assert await _codes(db_session, ids[name]) == set()

    await _run(db_session, "downgrade")
    for name in ids:
        assert await _codes(db_session, ids[name]) == set()
