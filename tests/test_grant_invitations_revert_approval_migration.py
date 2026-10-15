"""Tenant migration `6054f5200ed1_grant_invitations_revert_approval`
(add-invitation-approval-revert): the standard `admin`, `reception`, and
`host` roles gain `invitations:revert-approval`; `security` and custom roles
don't. Same direct `upgrade()`/`downgrade()` harness as
`test_grant_reception_invitations_checkout_migration.py`.
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
    / "alembic_tenant/versions/6054f5200ed1_grant_invitations_revert_approval.py"
)
_REVERT = "invitations:revert-approval"


def _load_migration():
    spec = importlib.util.spec_from_file_location("grant_invitations_revert_approval", _MIGRATION)
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


async def _catalog_rows(db_session: AsyncSession) -> int | None:
    return await db_session.scalar(
        select(func.count()).select_from(Permission).where(Permission.code == _REVERT)
    )


async def test_grants_revert_to_approving_standard_roles_and_is_idempotent(
    db_session: AsyncSession,
) -> None:
    deny = PermissionFactory.build(
        id=uuid.uuid4(), code="invitations:deny", description="invitations:deny"
    )
    names = ("admin", "reception", "host", "security", "manager")
    roles = {
        name: RoleFactory.build(id=uuid.uuid4(), name=name, permissions=[deny]) for name in names
    }
    db_session.add_all([deny, *roles.values()])
    await db_session.commit()
    role_ids = {name: role.id for name, role in roles.items()}

    await _run(db_session, lambda m: m.upgrade())
    await _run(db_session, lambda m: m.upgrade())

    for name in ("admin", "reception", "host"):
        assert await _codes(db_session, role_ids[name]) == {"invitations:deny", _REVERT}, name
    for name in ("security", "manager"):
        assert await _codes(db_session, role_ids[name]) == {"invitations:deny"}, name
    assert await _catalog_rows(db_session) == 1


async def test_downgrade_removes_only_the_standard_role_grants(db_session: AsyncSession) -> None:
    revert = PermissionFactory.build(id=uuid.uuid4(), code=_REVERT, description=_REVERT)
    reception = RoleFactory.build(id=uuid.uuid4(), name="reception", permissions=[revert])
    manager = RoleFactory.build(id=uuid.uuid4(), name="manager", permissions=[revert])
    db_session.add_all([revert, reception, manager])
    await db_session.commit()
    reception_id, manager_id = reception.id, manager.id

    await _run(db_session, lambda m: m.downgrade())

    assert await _codes(db_session, reception_id) == set()
    assert await _codes(db_session, manager_id) == {_REVERT}
    assert await _catalog_rows(db_session) == 1
