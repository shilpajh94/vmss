"""Tenant migration `bff38dfa42e7_grant_reception_invitations_checkout`
(grant-reception-checkout-permission): the standard `reception` role gains
`invitations:checkout`; `host` and custom roles don't. Runs the revision's
`upgrade()`/`downgrade()` directly against the test tenant schema through an
Alembic operations context, same as `test_grant_invitations_view_all_migration.py`.
"""

import importlib.util
import uuid
from collections.abc import Callable
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import PermissionFactory, RoleFactory
from vmss_api.auth.models import Permission, role_permissions

_TENANT_SCHEMA = "tenant_acme_test"
_MIGRATION = (
    Path(__file__).parents[1]
    / "alembic_tenant/versions/bff38dfa42e7_grant_reception_invitations_checkout.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "grant_reception_invitations_checkout", _MIGRATION
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run(db_session: AsyncSession, step: Callable[[object], None]) -> None:
    migration = _load_migration()

    def _apply(sync_conn) -> None:
        context = MigrationContext.configure(
            sync_conn, opts={"version_table_schema": _TENANT_SCHEMA}
        )
        with Operations.context(context):
            step(migration)

    connection = await db_session.connection()
    await connection.run_sync(_apply)
    await db_session.commit()


async def _codes(db_session: AsyncSession, role_id: uuid.UUID) -> set[str]:
    rows = await db_session.execute(
        select(Permission.code)
        .join(role_permissions, role_permissions.c.permission_id == Permission.id)
        .where(role_permissions.c.role_id == role_id)
    )
    return set(rows.scalars())


async def test_grants_checkout_to_reception_only_and_is_idempotent(
    db_session: AsyncSession,
) -> None:
    deny = PermissionFactory.build(
        id=uuid.uuid4(), code="invitations:deny", description="invitations:deny"
    )
    reception = RoleFactory.build(id=uuid.uuid4(), name="reception", permissions=[deny])
    host = RoleFactory.build(id=uuid.uuid4(), name="host", permissions=[deny])
    manager = RoleFactory.build(id=uuid.uuid4(), name="manager", permissions=[deny])
    db_session.add_all([deny, reception, host, manager])
    await db_session.commit()
    reception_id, host_id, manager_id = reception.id, host.id, manager.id

    await _run(db_session, lambda m: m.upgrade())
    await _run(db_session, lambda m: m.upgrade())

    assert await _codes(db_session, reception_id) == {"invitations:deny", "invitations:checkout"}
    assert await _codes(db_session, host_id) == {"invitations:deny"}
    assert await _codes(db_session, manager_id) == {"invitations:deny"}
    catalog_rows = await db_session.scalar(
        select(func.count())
        .select_from(Permission)
        .where(Permission.code == "invitations:checkout")
    )
    assert catalog_rows == 1


async def test_downgrade_removes_only_the_reception_grant(db_session: AsyncSession) -> None:
    checkout = PermissionFactory.build(
        id=uuid.uuid4(), code="invitations:checkout", description="invitations:checkout"
    )
    reception = RoleFactory.build(id=uuid.uuid4(), name="reception", permissions=[checkout])
    security = RoleFactory.build(id=uuid.uuid4(), name="security", permissions=[checkout])
    db_session.add_all([checkout, reception, security])
    await db_session.commit()
    reception_id, security_id = reception.id, security.id

    await _run(db_session, lambda m: m.downgrade())

    assert await _codes(db_session, reception_id) == set()
    assert await _codes(db_session, security_id) == {"invitations:checkout"}
    catalog_rows = await db_session.scalar(
        select(func.count())
        .select_from(Permission)
        .where(Permission.code == "invitations:checkout")
    )
    assert catalog_rows == 1
