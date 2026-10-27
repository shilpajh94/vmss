import gzip
import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import InvitationFactory
from vmss_api.audit_trail.tests import _build_user_with_permissions
from vmss_api.auth.models import AuditLog, User
from vmss_api.core.config import settings
from vmss_api.invitations import retention, service
from vmss_api.invitations import tasks as invitation_tasks
from vmss_api.invitations.models import (
    Invitation,
    InvitationQRCode,
    InvitationVehicle,
    InvitationVisitor,
)
from vmss_api.invitations.test_retention import (
    _add_children,
    _backup_files,
    _branch_defaults,
    _count,
)
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant

_SCHEMA = "tenant_acme_test"
_URL = "/api/v1/invitations/clear-all"


@pytest.fixture(autouse=True)
def _storage_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "storage_root", str(tmp_path))
    monkeypatch.setattr(settings, "storage_backend", "local")


async def _add_on(
    db_session: AsyncSession, branch: Branch, visit_date: date | None, **overrides: object
) -> uuid.UUID:
    overrides.setdefault("created_by_user_id", None)
    overrides.setdefault("registration_type", "individual")
    overrides.setdefault("source", "staff_pre_registration")
    overrides.setdefault("status", "approved")
    invitation = InvitationFactory.build(
        id=uuid.uuid4(), branch_id=branch.id, preferred_visit_date=visit_date, **overrides
    )
    db_session.add(invitation)
    await db_session.commit()
    return invitation.id


async def _remaining(db_session: AsyncSession) -> set[uuid.UUID]:
    return set((await db_session.execute(select(Invitation.id))).scalars().all())


async def _clear(tenant: Tenant, user_id: uuid.UUID, **kwargs: object) -> int:
    params: dict[str, object] = {
        "include_checked_in": False,
        "from_date": None,
        "to_date": None,
    }
    params.update(kwargs)
    return await invitation_tasks.clear_invitations(
        tenant.id,
        _SCHEMA,
        actor_user_id=user_id,
        **params,  # type: ignore[arg-type]
    )


# --- task: full clear -----------------------------------------------------------


async def test_clear_all_removes_everything_with_children_backup_and_audit(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, user: User, tmp_path: Path
) -> None:
    first = await _add_on(db_session, branch, date(2026, 9, 1))
    child_rows = await _add_children(db_session, first)
    await _add_on(db_session, branch, None)

    assert await _clear(tenant, user.id) == 2

    assert await _count(db_session, Invitation) == 0
    for model in (InvitationVisitor, InvitationVehicle, InvitationQRCode):
        assert await _count(db_session, model) == 0
    (backup,) = _backup_files(tmp_path)
    assert len(gzip.decompress(backup.read_bytes()).decode().splitlines()) == 2 + child_rows

    audit = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "invitations_cleared"))
    ).scalar_one()
    assert audit.actor_user_id == user.id
    assert audit.diff is not None
    assert audit.diff["count"] == 2
    assert audit.diff["scope"] is None
    assert len(audit.diff["backup_keys"]) == 1


async def test_clear_all_second_run_is_a_noop(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, user: User, tmp_path: Path
) -> None:
    await _add_on(db_session, branch, date(2026, 9, 1))

    assert await _clear(tenant, user.id) == 1
    assert await _clear(tenant, user.id) == 0

    assert len(_backup_files(tmp_path)) == 1
    assert await _count(db_session, AuditLog) == 1


# --- task: checked-in protection ------------------------------------------------


async def test_checked_in_skipped_by_default_and_removed_when_opted_in(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, user: User
) -> None:
    await _add_on(db_session, branch, date(2026, 9, 1))
    inside = await _add_on(
        db_session, branch, date(2026, 9, 1), status="checked_in", check_in_status="checked_in"
    )

    assert await _clear(tenant, user.id) == 1
    assert await _remaining(db_session) == {inside}

    assert await _clear(tenant, user.id, include_checked_in=True) == 1
    assert await _remaining(db_session) == set()


# --- task: date scope -----------------------------------------------------------


async def test_range_scope_is_inclusive_and_skips_undated(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, user: User
) -> None:
    before = await _add_on(db_session, branch, date(2026, 8, 31))
    await _add_on(db_session, branch, date(2026, 9, 1))
    await _add_on(db_session, branch, date(2026, 9, 5))
    after = await _add_on(db_session, branch, date(2026, 9, 6))
    undated = await _add_on(db_session, branch, None)

    deleted = await _clear(tenant, user.id, from_date=date(2026, 9, 1), to_date=date(2026, 9, 5))

    assert deleted == 2
    assert await _remaining(db_session) == {before, after, undated}
    audit = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "invitations_cleared"))
    ).scalar_one()
    assert audit.diff is not None
    assert audit.diff["scope"] == {"from_date": "2026-09-01", "to_date": "2026-09-05"}


async def test_open_ended_bounds(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, user: User
) -> None:
    early = await _add_on(db_session, branch, date(2026, 1, 1))
    await _add_on(db_session, branch, date(2026, 9, 1))

    assert await _clear(tenant, user.id, from_date=date(2026, 6, 1)) == 1
    assert await _remaining(db_session) == {early}


async def test_backup_failure_aborts_deletion(
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _add_on(db_session, branch, date(2026, 9, 1))

    async def _boom(*args: object, **kwargs: object) -> str:
        raise OSError("storage unavailable")

    monkeypatch.setattr(retention.storage, "save", _boom)

    with pytest.raises(OSError):
        await _clear(tenant, user.id)

    assert await _count(db_session, Invitation) == 1
    assert await _count(db_session, AuditLog) == 0


async def test_clear_does_not_touch_another_tenant_schema(
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    user: User,
    make_tenant_schema,
    open_tenant_session,
) -> None:
    other_schema = "tenant_other_clear_test"
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
                preferred_visit_date=date(2026, 9, 1),
            )
        )
        await other.commit()
    await _add_on(db_session, branch, date(2026, 9, 1))

    await _clear(tenant, user.id, from_date=date(2026, 9, 1), to_date=date(2026, 9, 30))

    async with open_tenant_session(other_schema) as other:
        assert (await other.execute(select(func.count()).select_from(Invitation))).scalar_one() == 1


# --- API ------------------------------------------------------------------------


class _FakeRedis:
    def __init__(self, locked: bool = False) -> None:
        self.locked = locked

    async def exists(self, key: str) -> int:
        return int(self.locked)


@pytest.fixture
def enqueued(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    calls: list[dict] = []
    monkeypatch.setattr(
        invitation_tasks.clear_tenant_invitations, "delay", lambda **kw: calls.append(kw)
    )

    async def _redis() -> _FakeRedis:
        return _FakeRedis()

    monkeypatch.setattr(service, "get_redis", _redis)
    return calls


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_api_full_clear_enqueues(
    client: AsyncClient, user: User, issue_token, enqueued: list[dict]
) -> None:
    response = await client.post(
        _URL, json={"confirm": "CLEAR ALL INVITATIONS"}, headers=_headers(issue_token(user))
    )

    assert response.status_code == 202
    assert response.json()["data"]["accepted"] is True
    (call,) = enqueued
    assert call["from_date"] is None and call["to_date"] is None
    assert call["include_checked_in"] is False
    assert call["actor_user_id"] == str(user.id)


async def test_api_month_scope_is_expanded_to_dates(
    client: AsyncClient, user: User, issue_token, enqueued: list[dict]
) -> None:
    response = await client.post(
        _URL,
        json={"confirm": "CLEAR INVITATIONS", "month": "2026-02"},
        headers=_headers(issue_token(user)),
    )

    assert response.status_code == 202
    (call,) = enqueued
    assert (call["from_date"], call["to_date"]) == ("2026-02-01", "2026-02-28")
    data = response.json()["data"]
    assert data["fromDate"] == "2026-02-01" and data["toDate"] == "2026-02-28"


async def test_api_december_month_rolls_over_year(
    client: AsyncClient, user: User, issue_token, enqueued: list[dict]
) -> None:
    await client.post(
        _URL,
        json={"confirm": "CLEAR INVITATIONS", "month": "2026-12"},
        headers=_headers(issue_token(user)),
    )
    assert (enqueued[0]["from_date"], enqueued[0]["to_date"]) == ("2026-12-01", "2026-12-31")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"confirm": "yes"},
        {"confirm": "CLEAR INVITATIONS"},  # scoped phrase without a scope
        {"confirm": "CLEAR ALL INVITATIONS", "month": "2026-09"},  # full phrase with a scope
        {"confirm": "CLEAR INVITATIONS", "month": "2026-09", "fromDate": "2026-09-01"},
        {"confirm": "CLEAR INVITATIONS", "fromDate": "2026-09-10", "toDate": "2026-09-01"},
        {"confirm": "CLEAR INVITATIONS", "month": "2026-13"},
        {"confirm": "CLEAR INVITATIONS", "month": "September"},
    ],
)
async def test_api_invalid_body_is_422_and_enqueues_nothing(
    client: AsyncClient, user: User, issue_token, enqueued: list[dict], body: dict
) -> None:
    response = await client.post(_URL, json=body, headers=_headers(issue_token(user)))

    assert response.status_code == 422
    assert enqueued == []


async def test_api_requires_clear_all_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    issue_token,
    enqueued: list[dict],
) -> None:
    limited = await _build_user_with_permissions(
        db_session,
        tenant,
        email="export-only@acme-test.example",
        permission_codes=["invitations:view-all", "invitations:export"],
    )
    response = await client.post(
        _URL, json={"confirm": "CLEAR ALL INVITATIONS"}, headers=_headers(issue_token(limited))
    )

    assert response.status_code == 403
    assert enqueued == []


async def test_api_returns_409_when_lock_held(
    client: AsyncClient, user: User, issue_token, enqueued: list[dict], monkeypatch
) -> None:
    async def _locked() -> _FakeRedis:
        return _FakeRedis(locked=True)

    monkeypatch.setattr(service, "get_redis", _locked)

    response = await client.post(
        _URL, json={"confirm": "CLEAR ALL INVITATIONS"}, headers=_headers(issue_token(user))
    )

    assert response.status_code == 409
    assert enqueued == []


async def test_task_loses_lock_race_silently(
    tenant: Tenant, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Redis:
        async def set(self, *args: object, **kwargs: object) -> bool:
            return False

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(invitation_tasks, "redis_from_url", lambda *a, **k: _Redis())
    monkeypatch.setattr(invitation_tasks, "engine", SimpleNamespace(dispose=_noop))

    assert (
        await invitation_tasks._clear_tenant_invitations(
            str(tenant.id), _SCHEMA, user.id, False, None, None
        )
        == 0
    )


async def _noop() -> None:
    return None
