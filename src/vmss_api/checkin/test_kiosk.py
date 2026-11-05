"""Kiosk badge print flow (add-kiosk-badge-print-flow). Device-authenticated, no
bearer token. Reuses the staff flow's visit/photo helpers from `checkin/tests.py`."""

import io
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import BranchFactory, DeviceFactory
from vmss_api.auth.models import AuditLog
from vmss_api.checkin.repository import CheckinRepository
from vmss_api.checkin.tests import _png, _prints
from vmss_api.checkin.tests import _visit as _staff_visit
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.devices.models import Device
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant

_BASE = "/api/v1/kiosk/checkin"


@pytest.fixture(autouse=True)
def _default_tenant_slug_matches_test_tenant(monkeypatch) -> None:
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")


async def _visit(db_session, tenant_id, branch, **overrides):  # noqa: ANN001, ANN202
    """The factory randomises `preferred_visit_date`; kiosk scope needs today/undated."""
    overrides.setdefault("preferred_visit_date", None)
    return await _staff_visit(db_session, tenant_id, branch, **overrides)


async def _kiosk(db_session: AsyncSession, branch: Branch, **overrides) -> Device:
    values = {
        "device_id": f"kiosk-{uuid.uuid4().hex[:8]}",
        "operating_mode": "kiosk",
        "approval_status": "approved",
        "is_active": True,
        "building_id": None,
        **overrides,
    }
    device = DeviceFactory.build(id=uuid.uuid4(), branch_id=branch.id, **values)
    db_session.add(device)
    await db_session.commit()
    return device


@pytest.fixture
async def flow_on(db_session: AsyncSession, tenant: Tenant) -> None:
    tenant.badge_print_flow_enabled = True
    await db_session.commit()


@pytest.fixture
async def other_branch(db_session: AsyncSession) -> Branch:
    branch = BranchFactory.build(id=uuid.uuid4(), name="Other Branch", code="OTHR")
    db_session.add(branch)
    await db_session.commit()
    return branch


def _h(device: Device) -> dict[str, str]:
    return {"device-id": device.device_id}


# --- device authentication ------------------------------------------------------


async def test_no_bearer_token_needed(flow_on, client, db_session, tenant, branch) -> None:
    device = await _kiosk(db_session, branch)
    visit = await _visit(db_session, tenant.id, branch)
    response = await client.get(
        f"{_BASE}/search", params={"q": visit.tracking_id}, headers=_h(device)
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(visit.id)


async def test_missing_header_is_403(flow_on, client, db_session, tenant, branch) -> None:
    visit = await _visit(db_session, tenant.id, branch)
    response = await client.get(f"{_BASE}/search", params={"q": visit.tracking_id})
    assert response.status_code == 403


@pytest.mark.parametrize(
    "overrides",
    [
        {"approval_status": "pending", "is_active": False},
        {"is_active": False},
        {"operating_mode": "security"},
        {"deleted_at": datetime.now(UTC)},
    ],
    ids=["pending", "disabled", "security-mode", "deleted"],
)
async def test_unusable_device_gets_the_same_403(
    flow_on,
    client,
    db_session,
    tenant,
    branch,
    overrides,
) -> None:
    device = await _kiosk(db_session, branch, **overrides)
    visit = await _visit(db_session, tenant.id, branch)
    unknown = await client.get(
        f"{_BASE}/search", params={"q": visit.tracking_id}, headers={"device-id": "nope"}
    )
    response = await client.get(
        f"{_BASE}/search", params={"q": visit.tracking_id}, headers=_h(device)
    )
    assert response.status_code == unknown.status_code == 403
    assert response.json() == unknown.json()


async def test_flag_off_is_404(client, db_session, tenant, branch) -> None:
    device = await _kiosk(db_session, branch)
    response = await client.get(f"{_BASE}/search", params={"q": "INV-X"}, headers=_h(device))
    assert response.status_code == 404


async def test_staff_endpoint_still_needs_a_token(flow_on, client, db_session, branch) -> None:
    device = await _kiosk(db_session, branch)
    response = await client.get("/api/v1/checkin/search", params={"q": "x"}, headers=_h(device))
    assert response.status_code == 401


# --- search ---------------------------------------------------------------------


async def test_search_by_checkin_code_and_minimal_body(
    flow_on,
    client,
    db_session,
    tenant,
    branch,
) -> None:
    device = await _kiosk(db_session, branch)
    visit = await _visit(db_session, tenant.id, branch, checkin_code="12345678")
    response = await client.get(f"{_BASE}/search", params={"q": "12345678"}, headers=_h(device))
    data = response.json()["data"]
    assert data["id"] == str(visit.id)
    assert data["visitorFirstName"] == "Alice"
    assert data["hasPhoto"] is True and data["unmetConditions"] == []
    assert not {"phone", "email", "fullName", "hostName"} & set(data)


@pytest.mark.parametrize("q", ["alice", "Alice Visitor", "95442", "+91 95442 32271", "%"])
async def test_search_does_not_match_names_or_phones(
    flow_on,
    client,
    db_session,
    tenant,
    branch,
    q,
) -> None:
    device = await _kiosk(db_session, branch)
    await _visit(db_session, tenant.id, branch)
    response = await client.get(f"{_BASE}/search", params={"q": q}, headers=_h(device))
    assert response.status_code == 404


async def test_search_other_branch_is_404(
    flow_on,
    client,
    db_session,
    tenant,
    branch,
    other_branch,
) -> None:
    device = await _kiosk(db_session, other_branch)
    visit = await _visit(db_session, tenant.id, branch)
    response = await client.get(
        f"{_BASE}/search", params={"q": visit.tracking_id}, headers=_h(device)
    )
    assert response.status_code == 404


async def test_search_visit_dated_other_day_is_404(
    flow_on,
    client,
    db_session,
    tenant,
    branch,
) -> None:
    device = await _kiosk(db_session, branch)
    visit = await _visit(
        db_session,
        tenant.id,
        branch,
        preferred_visit_date=(datetime.now(UTC) + timedelta(days=3)).date(),
    )
    response = await client.get(
        f"{_BASE}/search", params={"q": visit.tracking_id}, headers=_h(device)
    )
    assert response.status_code == 404


# --- verify-id / photo / print ---------------------------------------------------------


async def test_verify_id_records_device_and_is_idempotent(
    flow_on,
    client,
    db_session,
    tenant,
    branch,
) -> None:
    device = await _kiosk(db_session, branch)
    visit = await _visit(db_session, tenant.id, branch, verified=False)
    first = await client.post(f"{_BASE}/{visit.id}/verify-id", headers=_h(device))
    second = await client.post(f"{_BASE}/{visit.id}/verify-id", headers=_h(device))
    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["idVerifiedAt"] == second.json()["data"]["idVerifiedAt"]
    await db_session.refresh(visit)
    assert visit.id_verified_by_device_id == device.id
    assert visit.id_verified_by_user_id is None


async def test_photo_upload_and_conflict(
    flow_on,
    client,
    db_session,
    tenant,
    branch,
) -> None:
    device = await _kiosk(db_session, branch)
    visit = await _visit(db_session, tenant.id, branch, photo=False)
    files = {"file": ("p.png", io.BytesIO(_png()), "image/png")}
    ok = await client.post(f"{_BASE}/{visit.id}/photo", files=files, headers=_h(device))
    assert ok.status_code == 200 and ok.json()["data"]["hasPhoto"] is True
    files = {"file": ("p.png", io.BytesIO(_png()), "image/png")}
    again = await client.post(f"{_BASE}/{visit.id}/photo", files=files, headers=_h(device))
    assert again.status_code == 409


async def test_photo_rejects_non_image(
    flow_on,
    client,
    db_session,
    tenant,
    branch,
) -> None:
    device = await _kiosk(db_session, branch)
    visit = await _visit(db_session, tenant.id, branch, photo=False)
    files = {"file": ("p.png", io.BytesIO(b"not an image"), "image/png")}
    response = await client.post(f"{_BASE}/{visit.id}/photo", files=files, headers=_h(device))
    assert response.status_code == 422


async def test_print_succeeds_and_records_device(
    flow_on,
    client,
    db_session,
    tenant,
    branch,
) -> None:
    device = await _kiosk(db_session, branch)
    visit = await _visit(db_session, tenant.id, branch)
    response = await client.post(f"{_BASE}/{visit.id}/badge", headers=_h(device))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["data"]["token"]
    (row,) = await _prints(db_session, visit.id)
    assert row.printed_by_device_id == device.id and row.printed_by_user_id is None
    again = await client.post(f"{_BASE}/{visit.id}/badge", headers=_h(device))
    assert again.status_code == 409


async def test_print_gate_lists_every_unmet_condition(
    flow_on,
    client,
    db_session,
    tenant,
    branch,
) -> None:
    device = await _kiosk(db_session, branch)
    visit = await _visit(db_session, tenant.id, branch, photo=False, verified=False)
    response = await client.post(f"{_BASE}/{visit.id}/badge", headers=_h(device))
    assert response.status_code == 409
    assert "photo_missing" in response.text and "id_not_verified" not in response.text


async def test_print_idempotency_key_creates_one_row(
    flow_on,
    client,
    db_session,
    tenant,
    branch,
) -> None:
    device = await _kiosk(db_session, branch)
    visit = await _visit(db_session, tenant.id, branch)
    headers = {**_h(device), "Idempotency-Key": uuid.uuid4().hex}
    first = await client.post(f"{_BASE}/{visit.id}/badge", headers=headers)
    second = await client.post(f"{_BASE}/{visit.id}/badge", headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["token"] == second.json()["data"]["token"]
    assert len(await _prints(db_session, visit.id)) == 1


async def test_visit_in_other_branch_cannot_be_acted_on(
    flow_on,
    client,
    db_session,
    tenant,
    branch,
    other_branch,
) -> None:
    device = await _kiosk(db_session, other_branch)
    visit = await _visit(db_session, tenant.id, branch)
    for method, path in (("post", "verify-id"), ("post", "badge")):
        response = await getattr(client, method)(f"{_BASE}/{visit.id}/{path}", headers=_h(device))
        assert response.status_code == 404
    assert await _prints(db_session, visit.id) == []


# --- reprint --------------------------------------------------------------------


async def test_reprint_revokes_previous_badge(
    flow_on,
    client,
    db_session,
    tenant,
    branch,
) -> None:
    device = await _kiosk(db_session, branch)
    visit = await _visit(db_session, tenant.id, branch)
    await client.post(f"{_BASE}/{visit.id}/badge", headers=_h(device))
    response = await client.get(
        f"{_BASE}/{visit.id}/badge", params={"reason": "lost"}, headers=_h(device)
    )
    assert response.status_code == 200
    rows = await _prints(db_session, visit.id)
    assert [r.active for r in rows] == [False, True]
    assert rows[1].reprint_reason == "lost" and rows[1].printed_by_device_id == device.id


async def test_reprint_blank_reason_and_before_first_print(
    flow_on,
    client,
    db_session,
    tenant,
    branch,
) -> None:
    device = await _kiosk(db_session, branch)
    visit = await _visit(db_session, tenant.id, branch)
    blank = await client.get(
        f"{_BASE}/{visit.id}/badge", params={"reason": "  "}, headers=_h(device)
    )
    assert blank.status_code == 422
    never = await client.get(
        f"{_BASE}/{visit.id}/badge", params={"reason": "lost"}, headers=_h(device)
    )
    assert never.status_code == 409


# --- audit, rate limit, isolation ---------------------------------------------------------


async def test_print_is_audited_with_device_and_no_user(
    flow_on,
    client,
    db_session,
    tenant,
    branch,
) -> None:
    device = await _kiosk(db_session, branch)
    visit = await _visit(db_session, tenant.id, branch)
    await client.post(f"{_BASE}/{visit.id}/badge", headers=_h(device))
    rows = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "kiosk_badge_printed")))
        .scalars()
        .all()
    )
    assert rows and rows[0].actor_user_id is None
    assert rows[0].diff["device_id"] == device.device_id


async def test_rate_limit_trips(flow_on, client, db_session, branch, monkeypatch) -> None:
    monkeypatch.setattr(limiter, "enabled", True)
    device = await _kiosk(db_session, branch)
    responses = [
        await client.get(f"{_BASE}/search", params={"q": "INV-NONE"}, headers=_h(device))
        for _ in range(45)
    ]
    assert any(r.status_code == 429 for r in responses)


async def test_kiosk_lookup_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    db_session,
    tenant,
    branch,
) -> None:
    visit = await _visit(db_session, tenant.id, branch)
    await make_tenant_schema("tenant_other_test_kiosk")
    async with open_tenant_session("tenant_other_test_kiosk") as other:
        found = await CheckinRepository(other).find_kiosk_visit(
            visit.tracking_id, branch_id=branch.id, today=datetime.now(UTC).date()
        )
        assert found is None
