"""Tenant migration `a7c3e9f1b2d4_realign_invitation_expiry_to_visit_day`
(expire-invitation-at-end-of-visit-day): open invitations still carrying
the old `created_at + 168h` TTL are realigned to 23:59:59 on their visit
day in the visit timezone; terminal, staff-extended, and undated rows are
left alone. Runs the revision's `upgrade()` directly against the test
tenant schema, same as `test_grant_invitations_view_all_migration.py`.
"""

import importlib.util
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.ext.asyncio import AsyncSession

from factories import CompanyFactory, InvitationFactory
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant

_TENANT_SCHEMA = "tenant_acme_test"
_MIGRATION = (
    Path(__file__).parents[1]
    / "alembic_tenant/versions/a7c3e9f1b2d4_realign_invitation_expiry_to_visit_day.py"
)
_CREATED = datetime(2026, 9, 25, 9, 23, 52, tzinfo=UTC)
_OLD_TTL_EXPIRY = _CREATED + timedelta(hours=168, milliseconds=8)


def _load_migration():
    spec = importlib.util.spec_from_file_location("realign_invitation_expiry", _MIGRATION)
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


def _invitation(branch_id: uuid.UUID, **overrides):
    overrides.setdefault("status", "submitted")
    overrides.setdefault("preferred_visit_date", date(2026, 10, 2))
    overrides.setdefault("created_at", _CREATED)
    overrides.setdefault("expires_at", _OLD_TTL_EXPIRY)
    return InvitationFactory.build(
        id=uuid.uuid4(),
        branch_id=branch_id,
        created_by_user_id=None,
        registration_type="individual",
        source="staff_pre_registration",
        **overrides,
    )


async def test_realigns_only_open_rows_still_on_the_old_ttl(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> None:
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), default_timezone="Asia/Kolkata"))
    extended = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
    open_submitted = _invitation(branch.id)
    open_approved = _invitation(
        branch.id, status="approved", preferred_visit_date=date(2026, 10, 20)
    )
    denied = _invitation(branch.id, status="denied")
    checked_out = _invitation(branch.id, status="checked_out")
    staff_extended = _invitation(branch.id, status="approved", expires_at=extended)
    undated = _invitation(branch.id, preferred_visit_date=None)
    rows = [open_submitted, open_approved, denied, checked_out, staff_extended, undated]
    db_session.add_all(rows)
    await db_session.commit()

    await _run_upgrade(db_session)
    for row in rows:
        await db_session.refresh(row)

    assert open_submitted.expires_at == datetime(2026, 10, 2, 18, 29, 59, tzinfo=UTC)
    assert open_approved.expires_at == datetime(2026, 10, 20, 18, 29, 59, tzinfo=UTC)
    assert denied.expires_at == _OLD_TTL_EXPIRY
    assert checked_out.expires_at == _OLD_TTL_EXPIRY
    assert staff_extended.expires_at == extended
    assert undated.expires_at == _OLD_TTL_EXPIRY

    # Idempotent: a realigned row no longer matches the old-TTL signature.
    await _run_upgrade(db_session)
    await db_session.refresh(open_submitted)
    assert open_submitted.expires_at == datetime(2026, 10, 2, 18, 29, 59, tzinfo=UTC)


async def test_falls_back_to_tenant_timezone_without_a_company(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> None:
    """The `tenant` fixture pins `timezone="UTC"`."""
    row = _invitation(branch.id)
    db_session.add(row)
    await db_session.commit()

    await _run_upgrade(db_session)
    await db_session.refresh(row)

    assert row.expires_at == datetime(2026, 10, 2, 23, 59, 59, tzinfo=UTC)
