import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from factories import BranchFactory, BuildingFactory, DeviceFactory, InvitationFactory
from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.devices.models import Device, TenantSettings
from vmss_api.devices.repository import DeviceRepository, TenantSettingsRepository
from vmss_api.invitations import qr_token
from vmss_api.org_structure.models import Branch, Building
from vmss_api.tenant.models import Tenant


@pytest.fixture(autouse=True)
def _default_tenant_slug_matches_test_tenant(monkeypatch) -> None:
    """Public endpoints resolve the tenant from `settings.default_tenant_slug`."""
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")


def _auth(user: User, issue_token: Callable[[User], str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token(user)}"}


async def _building(db_session: AsyncSession, branch: Branch, code: str = "TWR-A") -> Building:
    building = BuildingFactory.build(id=uuid.uuid4(), branch_id=branch.id, code=code)
    db_session.add(building)
    await db_session.commit()
    return building


async def _device(db_session: AsyncSession, branch: Branch, **overrides) -> Device:
    device = DeviceFactory.build(id=uuid.uuid4(), branch_id=branch.id, **overrides)
    db_session.add(device)
    await db_session.commit()
    return device


def _register_payload(branch: Branch, **overrides) -> dict:
    return {
        "name": "Lobby iPad",
        "deviceId": "ipad-001",
        "branchId": str(branch.id),
        "operatingMode": "kiosk",
        **overrides,
    }


async def _invitation(
    db_session: AsyncSession, branch: Branch, building: Building | None = None, **overrides
):
    defaults = {
        "status": "approved",
        "approved_at": datetime.now(UTC),
        "check_in_status": "unused",
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "preferred_visit_date": None,
        "created_by_user_id": None,
        "registration_type": "individual",
        "source": "staff_pre_registration",
        "submitted_at": datetime.now(UTC),
    }
    invitation = InvitationFactory.build(
        id=uuid.uuid4(),
        branch_id=branch.id,
        building_id=building.id if building else None,
        **{**defaults, **overrides},
    )
    db_session.add(invitation)
    await db_session.commit()
    return invitation


# --- registration ------------------------------------------------------------


async def test_register_creates_pending_disabled_device(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    building = await _building(db_session, branch)
    response = await client.post(
        "/api/v1/devices/register",
        json=_register_payload(branch, buildingId=str(building.id), operatingMode="security"),
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["approvalStatus"] == "pending"
    assert body["isActive"] is False


async def test_register_is_idempotent_and_never_relocates(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    first = await client.post("/api/v1/devices/register", json=_register_payload(branch))
    other = BranchFactory.build(id=uuid.uuid4(), name="Other", code="OTH")
    db_session.add(other)
    await db_session.commit()
    second = await client.post(
        "/api/v1/devices/register",
        json=_register_payload(other, operatingMode="security"),
    )
    assert second.status_code == 200
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    stored = await db_session.get(Device, uuid.UUID(first.json()["data"]["id"]))
    assert stored is not None
    await db_session.refresh(stored)
    assert stored.branch_id == branch.id
    assert stored.operating_mode == "kiosk"


async def test_register_rejects_building_from_other_branch(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    other = BranchFactory.build(id=uuid.uuid4(), name="Other", code="OTH")
    db_session.add(other)
    await db_session.commit()
    foreign = await _building(db_session, other, "FOREIGN")
    response = await client.post(
        "/api/v1/devices/register",
        json=_register_payload(branch, buildingId=str(foreign.id)),
    )
    assert response.status_code == 422


async def test_register_rejects_invalid_operating_mode(
    client: AsyncClient, tenant: Tenant, branch: Branch
) -> None:
    response = await client.post(
        "/api/v1/devices/register", json=_register_payload(branch, operatingMode="tablet")
    )
    assert response.status_code == 422


async def test_deleted_device_id_can_register_again(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    user: User,
    issue_token: Callable[[User], str],
    db_session: AsyncSession,
) -> None:
    headers = _auth(user, issue_token)
    payload = _register_payload(branch)
    created = await client.post("/api/v1/devices/register", json=payload)
    pk = created.json()["data"]["id"]
    deleted = await client.delete(f"/api/v1/devices/{pk}", headers=headers)
    assert deleted.status_code == 204
    again = await client.post("/api/v1/devices/register", json=payload)
    assert again.status_code == 201
    assert again.json()["data"]["id"] != pk


# --- approval status lookup ----------------------------------------------------


@pytest.mark.parametrize(
    ("approval_status", "is_active", "approved"),
    [("pending", False, False), ("approved", True, True), ("approved", False, False)],
)
async def test_approval_status_reflects_device_state(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    approval_status: str,
    is_active: bool,
    approved: bool,
) -> None:
    await _device(
        db_session, branch, device_id="ipad-s", approval_status=approval_status, is_active=is_active
    )
    response = await client.get("/api/v1/devices/approval-status", params={"deviceId": "ipad-s"})
    assert response.status_code == 200
    assert response.json()["data"] == {
        "deviceId": "ipad-s",
        "operatingMode": "kiosk",
        "approvalStatus": approval_status,
        "isActive": is_active,
        "approved": approved,
    }


async def test_approval_status_unknown_or_deleted_device_is_404_and_creates_nothing(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    await _device(db_session, branch, device_id="gone", deleted_at=datetime.now(UTC))
    for device_id in ("never-registered", "gone"):
        response = await client.get(
            "/api/v1/devices/approval-status", params={"deviceId": device_id}
        )
        assert response.status_code == 404
    assert await DeviceRepository(db_session).get_by_device_id("never-registered") is None


async def test_approval_status_requires_device_id(client: AsyncClient, tenant: Tenant) -> None:
    assert (await client.get("/api/v1/devices/approval-status")).status_code == 422
    empty = await client.get("/api/v1/devices/approval-status", params={"deviceId": ""})
    assert empty.status_code == 422


async def test_approval_status_does_not_shadow_device_lookup(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    user: User,
    issue_token: Callable[[User], str],
    db_session: AsyncSession,
) -> None:
    device = await _device(db_session, branch)
    response = await client.get(f"/api/v1/devices/{device.id}", headers=_auth(user, issue_token))
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(device.id)


async def test_approval_status_rate_limit_trips(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    monkeypatch.setattr(limiter, "enabled", True)
    responses = [
        await client.get("/api/v1/devices/approval-status", params={"deviceId": "x"})
        for _ in range(65)
    ]
    assert any(r.status_code == 429 for r in responses)


# --- admin lifecycle -----------------------------------------------------------


async def test_approve_disable_enable_flow(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    user: User,
    issue_token: Callable[[User], str],
    db_session: AsyncSession,
) -> None:
    headers = _auth(user, issue_token)
    device = await _device(db_session, branch, approval_status="pending", is_active=False)

    pending = await client.get(f"/api/v1/devices/{device.id}", headers=headers)
    assert pending.json()["data"]["canApprove"] is True
    assert pending.json()["data"]["canEnable"] is False

    approved = await client.post(f"/api/v1/devices/{device.id}/approve", headers=headers)
    assert approved.status_code == 200
    data = approved.json()["data"]
    assert (data["approvalStatus"], data["isActive"]) == ("approved", True)
    assert data["canDisable"] is True

    disabled = await client.post(f"/api/v1/devices/{device.id}/disable", headers=headers)
    assert disabled.json()["data"]["isActive"] is False
    assert disabled.json()["data"]["approvalStatus"] == "approved"
    repeat = await client.post(f"/api/v1/devices/{device.id}/disable", headers=headers)
    assert repeat.status_code == 200

    enabled = await client.post(f"/api/v1/devices/{device.id}/enable", headers=headers)
    assert enabled.json()["data"]["isActive"] is True


async def test_enable_and_disable_blocked_while_pending(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    user: User,
    issue_token: Callable[[User], str],
    db_session: AsyncSession,
) -> None:
    headers = _auth(user, issue_token)
    device = await _device(db_session, branch, approval_status="pending", is_active=False)
    for action in ("enable", "disable"):
        response = await client.post(f"/api/v1/devices/{device.id}/{action}", headers=headers)
        assert response.status_code == 409


async def test_list_filters_and_names(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    user: User,
    issue_token: Callable[[User], str],
    db_session: AsyncSession,
) -> None:
    headers = _auth(user, issue_token)
    building = await _building(db_session, branch)
    branch_name, building_name = branch.name, building.name
    await _device(db_session, branch, name="K-pending", approval_status="pending", is_active=False)
    await _device(db_session, branch, name="K-on", building_id=building.id)
    await _device(db_session, branch, name="K-off", is_active=False)
    await _device(db_session, branch, name="S-on", operating_mode="security")

    def names(response) -> set[str]:
        return {d["name"] for d in response.json()["data"]}

    pending = await client.get("/api/v1/devices?approvalStatus=pending", headers=headers)
    assert names(pending) == {"K-pending"}
    security = await client.get("/api/v1/devices?operatingMode=security", headers=headers)
    assert names(security) == {"S-on"}
    disabled = await client.get(
        "/api/v1/devices?approvalStatus=approved&status=inactive", headers=headers
    )
    assert names(disabled) == {"K-off"}
    everything = await client.get("/api/v1/devices?operatingMode=kiosk", headers=headers)
    row = next(d for d in everything.json()["data"] if d["name"] == "K-on")
    assert row["branchName"] == branch_name
    assert row["buildingName"] == building_name
    assert everything.json()["pagination"]["total"] == 3


async def test_list_rejects_invalid_sort(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    response = await client.get(
        "/api/v1/devices?sortBy=device_id", headers=_auth(user, issue_token)
    )
    assert response.status_code == 422


async def test_delete_device_soft_deletes(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    user: User,
    issue_token: Callable[[User], str],
    db_session: AsyncSession,
) -> None:
    headers = _auth(user, issue_token)
    device = await _device(db_session, branch)
    assert (await client.delete(f"/api/v1/devices/{device.id}", headers=headers)).status_code == 204
    await db_session.refresh(device)
    assert device.deleted_at is not None
    assert (await client.get(f"/api/v1/devices/{device.id}", headers=headers)).status_code == 404


async def test_admin_endpoints_require_permission_and_auth(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    user_without_permissions: User,
    issue_token: Callable[[User], str],
    db_session: AsyncSession,
) -> None:
    device_pk = (await _device(db_session, branch, approval_status="pending", is_active=False)).id
    headers = _auth(user_without_permissions, issue_token)
    assert (await client.get("/api/v1/devices", headers=headers)).status_code == 403
    assert (
        await client.post(f"/api/v1/devices/{device_pk}/approve", headers=headers)
    ).status_code == 403
    assert (
        await client.post(f"/api/v1/devices/{device_pk}/enable", headers=headers)
    ).status_code == 403
    assert (await client.delete(f"/api/v1/devices/{device_pk}", headers=headers)).status_code == 403
    assert (await client.get("/api/v1/devices")).status_code == 401


# --- check-in / check-out traceability ----------------------------------------


async def test_tracking_check_in_records_device(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    device = await _device(db_session, branch)
    invitation = await _invitation(db_session, branch)
    response = await client.patch(
        f"/api/v2/invitations/{invitation.tracking_id}/check-in",
        headers={"device-id": device.device_id},
    )
    assert response.status_code == 200
    assert response.json()["data"]["checkInDevice"]["deviceId"] == device.device_id
    await db_session.refresh(invitation)
    assert invitation.check_in_device_id == device.id


async def test_check_in_without_header_records_no_device(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = await _invitation(db_session, branch)
    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 200
    assert response.json()["data"]["checkInDevice"] is None
    await db_session.refresh(invitation)
    assert invitation.check_in_device_id is None


async def test_unusable_devices_are_rejected_with_no_state_change(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    pending = await _device(db_session, branch, approval_status="pending", is_active=False)
    disabled = await _device(db_session, branch, is_active=False)
    invitation = await _invitation(db_session, branch)
    for device_id in (pending.device_id, disabled.device_id, "never-registered"):
        response = await client.patch(
            f"/api/v2/invitations/{invitation.tracking_id}/check-in",
            headers={"device-id": device_id},
        )
        assert response.status_code == 403
    await db_session.refresh(invitation)
    assert invitation.check_in_status == "unused"


async def test_qr_check_in_and_check_out_record_devices(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    entry = await _device(db_session, branch, name="Entry")
    exit_ = await _device(db_session, branch, name="Exit", operating_mode="security")
    invitation = await _invitation(db_session, branch)
    qr = qr_token.encrypt_invitation_token(invitation.id)

    checked_in = await client.patch(
        f"/api/v2/invitations/qr/{qr}/check-in", headers={"device-id": entry.device_id}
    )
    assert checked_in.json()["data"]["checkInDevice"]["name"] == "Entry"
    checked_out = await client.patch(
        f"/api/v2/invitations/qr/{qr}/check-out", headers={"device-id": exit_.device_id}
    )
    data = checked_out.json()["data"]
    assert data["checkInDevice"]["name"] == "Entry"
    assert data["checkOutDevice"]["name"] == "Exit"


async def test_repeat_check_in_does_not_overwrite_device_and_reentry_does(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    first = await _device(db_session, branch, name="First")
    second = await _device(db_session, branch, name="Second")
    invitation = await _invitation(db_session, branch)
    url = f"/api/v2/invitations/{invitation.tracking_id}/check-in"
    qr = qr_token.encrypt_invitation_token(invitation.id)

    await client.patch(url, headers={"device-id": first.device_id})
    repeat = await client.patch(url, headers={"device-id": second.device_id})
    assert repeat.status_code == 200
    assert repeat.json()["data"]["checkInDevice"]["name"] == "First"

    await client.patch(
        f"/api/v2/invitations/qr/{qr}/check-out", headers={"device-id": first.device_id}
    )
    reentry = await client.patch(url, headers={"device-id": second.device_id})
    data = reentry.json()["data"]
    assert data["checkInDevice"]["name"] == "Second"
    assert data["checkOutDevice"] is None


async def test_staff_check_out_records_device(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    user: User,
    issue_token: Callable[[User], str],
    db_session: AsyncSession,
) -> None:
    device = await _device(db_session, branch)
    invitation = await _invitation(
        db_session, branch, status="checked_in", check_in_status="checked_in"
    )
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/check-out",
        headers={**_auth(user, issue_token), "device-id": device.device_id},
    )
    assert response.status_code == 200
    assert response.json()["data"]["checkOutDevice"]["deviceId"] == device.device_id


# --- branch / building validation ---------------------------------------------


async def test_branch_mismatch_blocks_check_in(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    other = BranchFactory.build(id=uuid.uuid4(), name="Other", code="OTH")
    db_session.add(other)
    await db_session.commit()
    device = await _device(db_session, other)
    invitation = await _invitation(db_session, branch)
    response = await client.patch(
        f"/api/v2/invitations/{invitation.tracking_id}/check-in",
        headers={"device-id": device.device_id},
    )
    assert response.status_code == 422
    assert "branch" in response.json()["message"].lower()
    await db_session.refresh(invitation)
    assert invitation.check_in_status == "unused"
    assert invitation.check_in_device_id is None


async def test_building_mismatch_blocks_qr_check_in(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    building_a = await _building(db_session, branch, "A")
    building_b = await _building(db_session, branch, "B")
    device = await _device(db_session, branch, building_id=building_a.id)
    invitation = await _invitation(db_session, branch, building_b)
    qr = qr_token.encrypt_invitation_token(invitation.id)
    response = await client.patch(
        f"/api/v2/invitations/qr/{qr}/check-in", headers={"device-id": device.device_id}
    )
    assert response.status_code == 422
    assert "building" in response.json()["message"].lower()


async def test_repeat_check_in_from_wrong_device_is_rejected(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    other = BranchFactory.build(id=uuid.uuid4(), name="Other", code="OTH")
    db_session.add(other)
    await db_session.commit()
    good = await _device(db_session, branch, device_id="good-dev")
    wrong = await _device(db_session, other, device_id="wrong-dev")
    invitation = await _invitation(db_session, branch)
    qr = qr_token.encrypt_invitation_token(invitation.id)
    first = await client.patch(
        f"/api/v2/invitations/qr/{qr}/check-in", headers={"device-id": good.device_id}
    )
    assert first.status_code == 200
    for url in (
        f"/api/v2/invitations/qr/{qr}/check-in",
        f"/api/v2/invitations/{invitation.tracking_id}/check-in",
    ):
        repeat = await client.patch(url, headers={"device-id": wrong.device_id})
        assert repeat.status_code == 422


async def test_matching_location_and_building_less_invitation_pass(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    building = await _building(db_session, branch)
    device = await _device(db_session, branch, building_id=building.id)
    matching = await _invitation(db_session, branch, building)
    no_building = await _invitation(db_session, branch)
    for invitation in (matching, no_building):
        response = await client.patch(
            f"/api/v2/invitations/{invitation.tracking_id}/check-in",
            headers={"device-id": device.device_id},
        )
        assert response.status_code == 200


async def test_mismatch_allowed_when_enforcement_off(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    user: User,
    issue_token: Callable[[User], str],
    db_session: AsyncSession,
) -> None:
    other = BranchFactory.build(id=uuid.uuid4(), name="Other", code="OTH")
    db_session.add(other)
    await db_session.commit()
    device = await _device(db_session, other)
    invitation = await _invitation(db_session, branch)
    device_pk, device_id, tracking_id = device.id, device.device_id, invitation.tracking_id

    toggled = await client.put(
        "/api/v1/admin/settings/kiosk-location-validation",
        json={"enforceKioskLocationValidation": False},
        headers=_auth(user, issue_token),
    )
    assert toggled.status_code == 200
    response = await client.patch(
        f"/api/v2/invitations/{tracking_id}/check-in", headers={"device-id": device_id}
    )
    assert response.status_code == 200
    await db_session.refresh(invitation)
    assert invitation.check_in_device_id == device_pk


# --- setting -------------------------------------------------------------------


async def test_setting_defaults_to_true_and_persists(
    client: AsyncClient, tenant: Tenant, user: User, issue_token: Callable[[User], str]
) -> None:
    headers = _auth(user, issue_token)
    url = "/api/v1/admin/settings/kiosk-location-validation"
    assert (await client.get(url, headers=headers)).json()["data"] == {
        "enforceKioskLocationValidation": True
    }
    await client.put(url, json={"enforceKioskLocationValidation": False}, headers=headers)
    assert (await client.get(url, headers=headers)).json()["data"][
        "enforceKioskLocationValidation"
    ] is False
    await client.put(url, json={"enforceKioskLocationValidation": True}, headers=headers)
    assert (await client.get(url, headers=headers)).json()["data"][
        "enforceKioskLocationValidation"
    ] is True


async def test_setting_requires_permission(
    client: AsyncClient,
    tenant: Tenant,
    user_without_permissions: User,
    issue_token: Callable[[User], str],
) -> None:
    headers = _auth(user_without_permissions, issue_token)
    url = "/api/v1/admin/settings/kiosk-location-validation"
    assert (await client.get(url, headers=headers)).status_code == 403
    put = await client.put(url, json={"enforceKioskLocationValidation": False}, headers=headers)
    assert put.status_code == 403


# --- tenant isolation ----------------------------------------------------------


async def test_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, tenant: Tenant, branch: Branch, db_session
) -> None:
    await _device(db_session, branch, name="Mine")
    await make_tenant_schema("tenant_other_devices")
    async with open_tenant_session("tenant_other_devices") as other_session:
        other_session.add(TenantSettings(id=uuid.uuid4(), enforce_kiosk_location_validation=False))
        await other_session.commit()
        assert (await DeviceRepository(other_session).list(limit=10, offset=0)) == []
    assert (await TenantSettingsRepository(db_session).get()) is None
