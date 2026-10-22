import gzip
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    InvitationApprovalStepFactory,
    InvitationFactory,
    InvitationVehicleFactory,
    InvitationVisitorFactory,
    RoleFactory,
    TenantFactory,
)
from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.auth.models import AuditLog
from vmss_api.core.config import settings
from vmss_api.invitations import retention
from vmss_api.invitations import tasks as invitation_tasks
from vmss_api.invitations.models import (
    Invitation,
    InvitationQRCode,
    InvitationVehicle,
    InvitationVisitor,
)
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant

_SCHEMA = "tenant_acme_test"
_RETENTION_DAYS = 365


@pytest.fixture(autouse=True)
def _retention_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "invitation_retention_days", _RETENTION_DAYS)
    monkeypatch.setattr(settings, "storage_root", str(tmp_path))
    monkeypatch.setattr(settings, "storage_backend", "local")


def _days_ago(days: int) -> date:
    return datetime.now(UTC).date() - timedelta(days=days)


async def _add_invitation(
    db_session: AsyncSession, branch: Branch, *, visit_days_ago: int | None, **overrides: object
) -> Invitation:
    overrides.setdefault("created_by_user_id", None)
    overrides.setdefault("registration_type", "individual")
    overrides.setdefault("source", "staff_pre_registration")
    overrides.setdefault("status", "approved")
    invitation = InvitationFactory.build(
        id=uuid.uuid4(),
        branch_id=branch.id,
        preferred_visit_date=None if visit_days_ago is None else _days_ago(visit_days_ago),
        **overrides,
    )
    db_session.add(invitation)
    await db_session.commit()
    return invitation


async def _add_children(db_session: AsyncSession, invitation_id: uuid.UUID) -> int:
    """One row in each dependent table; returns how many rows that is."""
    role = RoleFactory.build(id=uuid.uuid4(), name=f"approver-{uuid.uuid4().hex[:6]}")
    db_session.add(role)
    await db_session.flush()
    db_session.add_all(
        [
            InvitationVisitorFactory.build(id=uuid.uuid4(), invitation_id=invitation_id),
            InvitationVehicleFactory.build(id=uuid.uuid4(), invitation_id=invitation_id),
            InvitationQRCode(
                id=uuid.uuid4(),
                invitation_id=invitation_id,
                qr_token="token",
                image_storage_key="key",
            ),
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation_id,
                step_order=1,
                approver_role_id=role.id,
            ),
        ]
    )
    await db_session.commit()
    return 4


async def _count(db_session: AsyncSession, model: type) -> int:
    return (await db_session.execute(select(func.count()).select_from(model))).scalar_one()


def _backup_files(root: Path) -> list[Path]:
    return (
        [p for p in (root / "vmss").rglob("*") if p.is_file()] if (root / "vmss").exists() else []
    )


async def test_purges_old_keeps_recent_checked_in_and_writes_verified_backup(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, tmp_path: Path
) -> None:
    tenant_id = tenant.id
    old = await _add_invitation(db_session, branch, visit_days_ago=_RETENTION_DAYS + 30)
    old_id = old.id
    child_rows = await _add_children(db_session, old_id)
    # No visit date: falls back to the creation date.
    old_created = await _add_invitation(
        db_session,
        branch,
        visit_days_ago=None,
        created_at=datetime.now(UTC) - timedelta(days=_RETENTION_DAYS + 30),
    )
    recent = await _add_invitation(db_session, branch, visit_days_ago=10)
    inside = await _add_invitation(
        db_session,
        branch,
        visit_days_ago=_RETENTION_DAYS + 30,
        status="checked_in",
        check_in_status="checked_in",
    )
    old_created_id, recent_id, inside_id = old_created.id, recent.id, inside.id

    purged = await invitation_tasks.purge_expired_invitations(tenant_id, _SCHEMA)

    assert purged == 2
    remaining = set((await db_session.execute(select(Invitation.id))).scalars().all())
    assert remaining == {recent_id, inside_id}
    for model in (InvitationVisitor, InvitationVehicle, InvitationQRCode, InvitationApprovalStep):
        assert await _count(db_session, model) == 0

    # Backup holds exactly what was deleted: 2 invitations + the old one's children.
    (backup,) = _backup_files(tmp_path)
    lines = gzip.decompress(backup.read_bytes()).decode().splitlines()
    assert len(lines) == 2 + child_rows
    backed_up_ids = {
        json.loads(line)["row"]["id"]
        for line in lines
        if json.loads(line)["table"] == "invitations"
    }
    assert backed_up_ids == {str(old_id), str(old_created_id)}

    audit = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "invitations_purged"))
    ).scalar_one()
    assert audit.diff is not None
    assert audit.diff["count"] == 2
    assert len(audit.diff["backup_keys"]) == 1
    assert audit.diff["cutoff"] == _days_ago(_RETENTION_DAYS).isoformat()


async def test_retention_disabled_is_a_noop(
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _add_invitation(db_session, branch, visit_days_ago=_RETENTION_DAYS + 30)
    monkeypatch.setattr(settings, "invitation_retention_days", 0)

    await invitation_tasks._purge_tenant_invitations(str(tenant.id), _SCHEMA)

    assert await _count(db_session, Invitation) == 1
    assert _backup_files(tmp_path) == []


async def test_nothing_to_purge_creates_no_backup_or_audit(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, tmp_path: Path
) -> None:
    await _add_invitation(db_session, branch, visit_days_ago=10)

    assert await invitation_tasks.purge_expired_invitations(tenant.id, _SCHEMA) == 0

    assert _backup_files(tmp_path) == []
    assert await _count(db_session, AuditLog) == 0


async def test_backup_is_written_before_any_delete(
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _add_invitation(db_session, branch, visit_days_ago=_RETENTION_DAYS + 30)
    files_at_delete: list[int] = []
    real_delete = InvitationRepository.delete_with_children

    async def _spy(self: InvitationRepository, ids: list[uuid.UUID]) -> int:
        files_at_delete.append(len(_backup_files(tmp_path)))
        return await real_delete(self, ids)

    monkeypatch.setattr(InvitationRepository, "delete_with_children", _spy)

    await invitation_tasks.purge_expired_invitations(tenant.id, _SCHEMA)

    assert files_at_delete == [1]


async def test_backup_write_failure_deletes_nothing(
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _add_invitation(db_session, branch, visit_days_ago=_RETENTION_DAYS + 30)

    async def _boom(*args: object, **kwargs: object) -> str:
        raise OSError("storage unavailable")

    monkeypatch.setattr(retention.storage, "save", _boom)

    with pytest.raises(OSError):
        await invitation_tasks.purge_expired_invitations(tenant.id, _SCHEMA)

    assert await _count(db_session, Invitation) == 1
    assert await _count(db_session, AuditLog) == 0


async def test_backup_count_mismatch_deletes_nothing(
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _add_invitation(db_session, branch, visit_days_ago=_RETENTION_DAYS + 30)
    monkeypatch.setattr(retention, "_count_records", lambda payload: 0)

    with pytest.raises(retention.BackupVerificationError):
        await invitation_tasks.purge_expired_invitations(tenant.id, _SCHEMA)

    assert await _count(db_session, Invitation) == 1


async def test_repeated_run_is_harmless(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, tmp_path: Path
) -> None:
    await _add_invitation(db_session, branch, visit_days_ago=_RETENTION_DAYS + 30)

    assert await invitation_tasks.purge_expired_invitations(tenant.id, _SCHEMA) == 1
    assert await invitation_tasks.purge_expired_invitations(tenant.id, _SCHEMA) == 0

    assert len(_backup_files(tmp_path)) == 1
    assert await _count(db_session, AuditLog) == 1


async def test_purge_is_batched(
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for _ in range(3):
        await _add_invitation(db_session, branch, visit_days_ago=_RETENTION_DAYS + 30)
    monkeypatch.setattr(settings, "invitation_purge_batch_size", 2)

    assert await invitation_tasks.purge_expired_invitations(tenant.id, _SCHEMA) == 3

    assert len(_backup_files(tmp_path)) == 2
    assert await _count(db_session, Invitation) == 0


async def test_purge_does_not_touch_another_tenant_schema(
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    make_tenant_schema,
    open_tenant_session,
) -> None:
    other_schema = "tenant_other_retention_test"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other:
        other_branch = Branch(id=uuid.uuid4(), name="Other", code="OTH", **_branch_defaults(branch))
        other.add(other_branch)
        await other.flush()
        other.add(
            InvitationFactory.build(
                id=uuid.uuid4(),
                branch_id=other_branch.id,
                created_by_user_id=None,
                registration_type="individual",
                source="staff_pre_registration",
                status="approved",
                preferred_visit_date=_days_ago(_RETENTION_DAYS + 30),
            )
        )
        await other.commit()
    await _add_invitation(db_session, branch, visit_days_ago=_RETENTION_DAYS + 30)

    await invitation_tasks.purge_expired_invitations(tenant.id, _SCHEMA)

    async with open_tenant_session(other_schema) as other:
        assert (await other.execute(select(func.count()).select_from(Invitation))).scalar_one() == 1


def _branch_defaults(branch: Branch) -> dict[str, object]:
    return {
        c.name: getattr(branch, c.key)
        for c in Branch.__table__.columns
        if not c.primary_key and c.name not in {"name", "code"} and not c.unique
    }


async def test_dispatch_isolates_per_tenant_enqueue_failure(
    db_session: AsyncSession, tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    second = TenantFactory.build(
        id=uuid.uuid4(), slug="second-retention", schema_name="tenant_second_retention"
    )
    db_session.add(second)
    await db_session.commit()
    enqueued: list[str] = []

    def _delay(*, tenant_id: str, tenant_schema: str) -> None:
        if tenant_schema == "tenant_second_retention":
            raise RuntimeError("broker hiccup")
        enqueued.append(tenant_schema)

    monkeypatch.setattr(invitation_tasks.purge_tenant_invitations, "delay", _delay)

    await invitation_tasks._dispatch_invitation_purge()

    assert _SCHEMA in enqueued
