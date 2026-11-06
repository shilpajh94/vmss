"""Zone access control (add-zone-access-control). Real Postgres, same fixtures
as the other features; the flag is switched on per test via `zones_on`."""

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import DeviceFactory, UserFactory, VisitorCategoryFactory, ZoneFactory
from vmss_api.access_control.decision import DenyReason, can_enter
from vmss_api.access_control.models import (
    InvitationZone,
    VisitorCategoryZone,
    Zone,
    ZoneAccessEvent,
    ZoneGate,
)
from vmss_api.auth.models import AuditLog, User
from vmss_api.checkin import badge_token
from vmss_api.checkin.models import BadgePrint
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.devices.models import Device
from vmss_api.invitations.models import Invitation
from vmss_api.invitations.tests.helpers import _build_invitation
from vmss_api.notifications import service as notifications_service
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant


@pytest.fixture
async def zones_on(db_session: AsyncSession, tenant: Tenant) -> None:
    tenant.zone_access_enabled = True
    await db_session.commit()


def _auth(issue_token: Callable[[User], str], user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token(user)}"}


async def _gate(db: AsyncSession, branch: Branch, code: str = "G1") -> Device:
    gate = DeviceFactory.build(
        id=uuid.uuid4(),
        branch_id=branch.id,
        building_id=None,
        device_id=f"dev-{code}-{uuid.uuid4().hex[:6]}",
        name=code,
        operating_mode="security",
    )
    db.add(gate)
    await db.flush()
    return gate


async def _zone(db: AsyncSession, branch: Branch, *gates: Device, code: str = "LAB", **kw) -> Zone:
    zone = ZoneFactory.build(id=uuid.uuid4(), branch_id=branch.id, code=code, name=code, **kw)
    db.add(zone)
    await db.flush()
    for gate in gates:
        db.add(ZoneGate(zone_id=zone.id, gate_id=gate.id))
    await db.commit()
    return zone


async def _visit(
    db: AsyncSession, tenant: Tenant, branch: Branch, **overrides
) -> tuple[Invitation, str]:
    """A checked-in, approved visit with an active badge; returns it and its QR token."""
    fields: dict = {
        "status": "checked_in",
        "check_in_status": "checked_in",
        "primary_contact_full_name": "Alice Visitor",
        "host_name_or_email": "Host One",
        "expires_at": datetime.now(UTC) + timedelta(days=1),
        "preferred_visit_date": None,
        "watchlist_flagged": False,
        "watchlist_override_at": None,
        "visitor_category_id": None,
        "deleted_at": None,
    }
    fields.update(overrides)
    visit = _build_invitation(db, branch.id, **fields)
    db.add(visit)
    await db.flush()
    today = datetime.now(UTC).date()
    jti = uuid.uuid4().hex
    db.add(
        BadgePrint(
            id=uuid.uuid4(),
            visit_id=visit.id,
            printed_at=datetime.now(UTC),
            jti=jti,
            day=today,
            active=True,
        )
    )
    await db.commit()
    token = badge_token.issue_badge_token(
        visit_id=visit.id, tenant_id=tenant.id, day=today, jti=jti, timezone="UTC"
    )
    return visit, token


async def _scan(
    client: AsyncClient,
    headers: dict[str, str],
    token: str,
    gate: Device,
    zone: Zone,
    direction: str = "entry",
    **extra_headers: str,
):
    return await client.post(
        "/api/v1/access/scan",
        json={
            "token": token,
            "gateId": str(gate.id),
            "zoneId": str(zone.id),
            "direction": direction,
        },
        headers={**headers, **extra_headers},
    )


async def _events(db: AsyncSession, visit_id: uuid.UUID) -> list[ZoneAccessEvent]:
    rows = await db.execute(
        select(ZoneAccessEvent)
        .where(ZoneAccessEvent.invitation_id == visit_id)
        .order_by(ZoneAccessEvent.occurred_at, ZoneAccessEvent.id)
    )
    return list(rows.scalars())


# --- allow/deny matrix (pure) --------------------------------------------------

_NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
_TODAY = date(2026, 11, 4)


def _facts(**visit_overrides):
    branch_id = uuid.uuid4()
    zone = SimpleNamespace(id=uuid.uuid4(), branch_id=branch_id, is_active=True, deleted_at=None)
    visit = SimpleNamespace(
        status="checked_in",
        check_in_status="checked_in",
        branch_id=branch_id,
        expires_at=_NOW + timedelta(hours=2),
        preferred_visit_date=_TODAY,
        watchlist_flagged=False,
        watchlist_override_at=None,
    )
    for key, value in visit_overrides.items():
        setattr(visit, key, value)
    return visit, zone


def _decide(visit, zone, *, gate=True, allowed=True):
    return can_enter(
        visit,
        zone,
        gate_serves_zone=gate,
        allowed_zone_ids={zone.id} if allowed else set(),
        now=_NOW,
        local_today=_TODAY,
    )


def test_matrix_allows_when_every_condition_is_met() -> None:
    visit, zone = _facts()
    decision = _decide(visit, zone)
    assert decision.allowed and decision.reason is None


@pytest.mark.parametrize(
    ("visit_overrides", "zone_overrides", "gate", "allowed", "reason"),
    [
        ({}, {"is_active": False}, True, True, DenyReason.zone_inactive),
        ({}, {"deleted_at": _NOW}, True, True, DenyReason.zone_inactive),
        ({}, {"branch_id": uuid.uuid4()}, True, True, DenyReason.zone_inactive),
        ({}, {}, False, True, DenyReason.gate_not_linked),
        ({"check_in_status": "unused"}, {}, True, True, DenyReason.not_checked_in),
        ({"status": "checked_out"}, {}, True, True, DenyReason.not_checked_in),
        ({"status": "submitted"}, {}, True, True, DenyReason.not_approved),
        ({"status": "denied"}, {}, True, True, DenyReason.not_approved),
        ({"watchlist_flagged": True}, {}, True, True, DenyReason.blacklisted),
        (
            {"expires_at": _NOW - timedelta(minutes=1)},
            {},
            True,
            True,
            DenyReason.outside_time_window,
        ),
        (
            {"preferred_visit_date": _TODAY + timedelta(days=1)},
            {},
            True,
            True,
            DenyReason.outside_time_window,
        ),
        ({}, {}, True, False, DenyReason.zone_not_allowed),
    ],
)
def test_matrix_denies_with_the_matching_reason(
    visit_overrides, zone_overrides, gate, allowed, reason
) -> None:
    visit, zone = _facts(**visit_overrides)
    for key, value in zone_overrides.items():
        setattr(zone, key, value)
    decision = _decide(visit, zone, gate=gate, allowed=allowed)
    assert not decision.allowed and decision.reason is reason


def test_matrix_first_failing_check_wins() -> None:
    visit, zone = _facts(watchlist_flagged=True, status="submitted", check_in_status="unused")
    assert _decide(visit, zone, allowed=False).reason is DenyReason.not_checked_in
    visit, zone = _facts(watchlist_flagged=True)
    assert _decide(visit, zone, allowed=False).reason is DenyReason.blacklisted


def test_matrix_watchlist_override_clears_blacklisted() -> None:
    visit, zone = _facts(watchlist_flagged=True, watchlist_override_at=_NOW)
    assert _decide(visit, zone).allowed


# --- flag off ---------------------------------------------------------------------


async def test_every_route_is_404_when_toggle_off(
    client: AsyncClient, user: User, issue_token, branch: Branch, tenant: Tenant
) -> None:
    assert tenant.zone_access_enabled is False
    headers = _auth(issue_token, user)
    some_id = uuid.uuid4()
    calls = [
        client.get("/api/v1/zones", headers=headers),
        client.post("/api/v1/zones", json={}, headers=headers),
        client.get(f"/api/v1/zones/{some_id}", headers=headers),
        client.get(f"/api/v1/visitor-categories/{some_id}/zones", headers=headers),
        client.put(f"/api/v1/invitations/{some_id}/zones", json={"zoneIds": []}, headers=headers),
        client.post("/api/v1/access/scan", json={}, headers=headers),
        client.get("/api/v1/emergency/inside", headers=headers),
    ]
    for call in calls:
        assert (await call).status_code == 404


# --- zone CRUD ------------------------------------------------------------------


async def test_zone_crud_and_soft_delete(
    zones_on, client: AsyncClient, user: User, issue_token, db_session: AsyncSession, branch
) -> None:
    headers = _auth(issue_token, user)
    gate = await _gate(db_session, branch)
    await db_session.commit()
    created = await client.post(
        "/api/v1/zones",
        json={"branchId": str(branch.id), "name": "Lab", "code": "LAB", "gateIds": [str(gate.id)]},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    zone_id = created.json()["data"]["id"]
    assert created.json()["data"]["gateIds"] == [str(gate.id)]

    duplicate = await client.post(
        "/api/v1/zones",
        json={"branchId": str(branch.id), "name": "Lab 2", "code": "LAB"},
        headers=headers,
    )
    assert duplicate.status_code == 409

    updated = await client.put(
        f"/api/v1/zones/{zone_id}", json={"name": "Clean Lab", "gateIds": []}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "Clean Lab"
    assert updated.json()["data"]["gateIds"] == []

    listed = await client.get("/api/v1/zones", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["pagination"]["total"] == 1

    deleted = await client.delete(f"/api/v1/zones/{zone_id}", headers=headers)
    assert deleted.status_code == 204
    row = (await db_session.execute(select(Zone).where(Zone.id == uuid.UUID(zone_id)))).scalar_one()
    await db_session.refresh(row)
    assert row.deleted_at is not None
    assert (await client.get(f"/api/v1/zones/{zone_id}", headers=headers)).status_code == 404
    # The code is free again once soft-deleted.
    again = await client.post(
        "/api/v1/zones",
        json={"branchId": str(branch.id), "name": "Lab", "code": "LAB"},
        headers=headers,
    )
    assert again.status_code == 201
    actions = (await db_session.execute(select(AuditLog.action))).scalars().all()
    assert {"zone_created", "zone_updated", "zone_deleted"} <= set(actions)


async def test_zone_rejects_gate_from_another_branch(
    zones_on, client: AsyncClient, user: User, issue_token, db_session: AsyncSession, branch
) -> None:
    from factories import BranchFactory

    other = BranchFactory.build(id=uuid.uuid4(), name="Other", code="OTH")
    db_session.add(other)
    await db_session.flush()
    foreign_gate = await _gate(db_session, other, "FG")
    await db_session.commit()
    response = await client.post(
        "/api/v1/zones",
        json={
            "branchId": str(branch.id),
            "name": "Lab",
            "code": "LAB",
            "gateIds": [str(foreign_gate.id)],
        },
        headers=_auth(issue_token, user),
    )
    assert response.status_code == 422


async def test_zone_write_denied_without_permission(
    zones_on,
    client: AsyncClient,
    user_without_permissions: User,
    issue_token,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    headers = _auth(issue_token, user_without_permissions)
    zone = await _zone(db_session, branch)
    assert (
        await client.post(
            "/api/v1/zones",
            json={"branchId": str(branch.id), "name": "X", "code": "X"},
            headers=headers,
        )
    ).status_code == 403
    assert (
        await client.put(f"/api/v1/zones/{zone.id}", json={}, headers=headers)
    ).status_code == 403
    assert (await client.delete(f"/api/v1/zones/{zone.id}", headers=headers)).status_code == 403
    assert (
        await client.put(
            f"/api/v1/visitor-categories/{uuid.uuid4()}/zones",
            json={"zoneIds": []},
            headers=headers,
        )
    ).status_code == 403


# --- allowed-zone mapping --------------------------------------------------------


async def test_invitation_mapping_overrides_category_default(
    zones_on, client, user, issue_token, db_session: AsyncSession, tenant, branch
) -> None:
    headers = _auth(issue_token, user)
    gate = await _gate(db_session, branch)
    lab = await _zone(db_session, branch, gate, code="LAB")
    vault = await _zone(db_session, branch, gate, code="VAULT")
    category = VisitorCategoryFactory.build(id=uuid.uuid4(), name="Vendor", code="VEN")
    db_session.add(category)
    await db_session.commit()
    set_default = await client.put(
        f"/api/v1/visitor-categories/{category.id}/zones",
        json={"zoneIds": [str(lab.id)]},
        headers=headers,
    )
    assert set_default.status_code == 200, set_default.text
    visit, token = await _visit(db_session, tenant, branch, visitor_category_id=category.id)

    # Category default applies while the invitation has no mapping of its own.
    assert (await _scan(client, headers, token, gate, lab)).json()["data"]["allowed"] is True
    assert (await _scan(client, headers, token, gate, vault)).json()["data"]["reason"] == (
        "zone_not_allowed"
    )

    mapped = await client.put(
        f"/api/v1/invitations/{visit.id}/zones", json={"zoneIds": [str(vault.id)]}, headers=headers
    )
    assert mapped.status_code == 200, mapped.text
    # Now the invitation's own list replaces the default.
    assert (await _scan(client, headers, token, gate, vault)).json()["data"]["allowed"] is True
    assert (await _scan(client, headers, token, gate, lab)).json()["data"]["reason"] == (
        "zone_not_allowed"
    )
    rows = (await db_session.execute(select(InvitationZone))).scalars().all()
    assert [r.zone_id for r in rows] == [vault.id]
    assert (await db_session.execute(select(VisitorCategoryZone))).scalars().all()


async def test_no_mapping_denies_every_zone(
    zones_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    gate = await _gate(db_session, branch)
    zone = await _zone(db_session, branch, gate)
    _, token = await _visit(db_session, tenant, branch)
    data = (await _scan(client, _auth(issue_token, user), token, gate, zone)).json()["data"]
    assert data == {"allowed": False, "reason": "zone_not_allowed", "visitorName": "Alice Visitor"}


async def test_invitation_mapping_rejects_zone_of_another_branch(
    zones_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    from factories import BranchFactory

    other = BranchFactory.build(id=uuid.uuid4(), name="Other", code="OTH")
    db_session.add(other)
    await db_session.flush()
    foreign = await _zone(db_session, other, code="FZ")
    visit, _ = await _visit(db_session, tenant, branch)
    response = await client.put(
        f"/api/v1/invitations/{visit.id}/zones",
        json={"zoneIds": [str(foreign.id)]},
        headers=_auth(issue_token, user),
    )
    assert response.status_code == 422


async def test_invitation_mapping_denied_without_edit_permission(
    zones_on, client, user_without_permissions, issue_token, db_session, tenant, branch
) -> None:
    visit, _ = await _visit(db_session, tenant, branch)
    response = await client.put(
        f"/api/v1/invitations/{visit.id}/zones",
        json={"zoneIds": []},
        headers=_auth(issue_token, user_without_permissions),
    )
    assert response.status_code == 403


# --- gate scan ---------------------------------------------------------------------


async def _allowed_setup(db_session, tenant, branch, **visit_overrides):
    gate = await _gate(db_session, branch)
    zone = await _zone(db_session, branch, gate)
    visit, token = await _visit(db_session, tenant, branch, **visit_overrides)
    db_session.add(InvitationZone(invitation_id=visit.id, zone_id=zone.id))
    await db_session.commit()
    return gate, zone, visit, token


async def test_allowed_entry_and_exit_are_logged(
    zones_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    headers = _auth(issue_token, user)
    gate, zone, visit, token = await _allowed_setup(db_session, tenant, branch)
    entry = await _scan(client, headers, token, gate, zone)
    assert entry.status_code == 200, entry.text
    assert entry.json()["data"]["allowed"] is True
    assert token not in entry.text
    exit_ = await _scan(client, headers, token, gate, zone, "exit")
    assert exit_.json()["data"]["allowed"] is True
    events = await _events(db_session, visit.id)
    assert [(e.direction, e.decision, e.reason) for e in events] == [
        ("entry", "allowed", None),
        ("exit", "allowed", None),
    ]


async def test_exit_is_never_denied(
    zones_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    headers = _auth(issue_token, user)
    gate = await _gate(db_session, branch)
    zone = await _zone(db_session, branch, gate)  # not mapped, never entered
    _, token = await _visit(db_session, tenant, branch)
    response = await _scan(client, headers, token, gate, zone, "exit")
    assert response.json()["data"]["allowed"] is True


async def test_denied_entry_logs_audits_and_alerts_security_once(
    zones_on, client, user, issue_token, db_session, tenant, branch, monkeypatch
) -> None:
    alerts: list[dict] = []

    async def _fake_notify(tenant_db, **kwargs):
        alerts.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_role_at_branch", _fake_notify)
    # The alert resolves the Security role by name; seed one.
    from factories import RoleFactory

    db_session.add(RoleFactory.build(id=uuid.uuid4(), name="security", permissions=[]))
    await db_session.commit()

    headers = _auth(issue_token, user)
    gate, zone, visit, token = await _allowed_setup(
        db_session, tenant, branch, watchlist_flagged=True
    )
    for _ in range(2):
        response = await _scan(client, headers, token, gate, zone)
        assert response.status_code == 200
        assert response.json()["data"] == {
            "allowed": False,
            "reason": "blacklisted",
            "visitorName": "Alice Visitor",
        }
    events = await _events(db_session, visit.id)
    assert [e.decision for e in events] == ["denied", "denied"]
    audit = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "zone_entry_denied")))
        .scalars()
        .all()
    )
    assert len(audit) == 2  # every denial is audited
    assert len(alerts) == 1  # but Security is alerted once per dedupe window
    assert alerts[0]["branch_id"] == branch.id
    assert "Alice" not in alerts[0]["body"] and zone.name in alerts[0]["body"]


async def test_denial_without_security_role_still_succeeds(
    zones_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    gate, zone, visit, token = await _allowed_setup(
        db_session, tenant, branch, watchlist_flagged=True
    )
    response = await _scan(client, _auth(issue_token, user), token, gate, zone)
    assert response.status_code == 200
    assert response.json()["data"]["allowed"] is False


@pytest.mark.parametrize("kind", ["tampered", "other_day", "inactive", "foreign_tenant"])
async def test_invalid_tokens_get_one_generic_response(
    kind, zones_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    gate, zone, visit, token = await _allowed_setup(db_session, tenant, branch)
    if kind == "tampered":
        token = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    elif kind == "other_day":
        row = (await db_session.execute(select(BadgePrint))).scalars().one()
        token = badge_token.issue_badge_token(
            visit_id=visit.id,
            tenant_id=tenant.id,
            day=row.day - timedelta(days=1),
            jti=row.jti,
            timezone="UTC",
        )
    elif kind == "inactive":
        row = (await db_session.execute(select(BadgePrint))).scalars().one()
        row.active = False
        await db_session.commit()
    else:
        row = (await db_session.execute(select(BadgePrint))).scalars().one()
        token = badge_token.issue_badge_token(
            visit_id=visit.id, tenant_id=uuid.uuid4(), day=row.day, jti=row.jti, timezone="UTC"
        )
    response = await _scan(client, _auth(issue_token, user), token, gate, zone)
    assert response.status_code == 400
    assert response.json()["message"] == "Invalid badge token"
    assert await _events(db_session, visit.id) == []


async def test_scan_denied_without_permission(
    zones_on, client, user_without_permissions, issue_token, db_session, tenant, branch
) -> None:
    gate, zone, _, token = await _allowed_setup(db_session, tenant, branch)
    response = await _scan(client, _auth(issue_token, user_without_permissions), token, gate, zone)
    assert response.status_code == 403


async def test_scan_with_idempotency_key_logs_one_event(
    zones_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    headers = _auth(issue_token, user)
    gate, zone, visit, token = await _allowed_setup(db_session, tenant, branch)
    key = {"Idempotency-Key": uuid.uuid4().hex}
    first = await _scan(client, headers, token, gate, zone, **key)
    second = await _scan(client, headers, token, gate, zone, **key)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(await _events(db_session, visit.id)) == 1


async def test_scan_rate_limit_trips(zones_on, client, user, issue_token, monkeypatch) -> None:
    monkeypatch.setattr(limiter, "enabled", True)
    headers = _auth(issue_token, user)
    body = {
        "token": "junk",
        "gateId": str(uuid.uuid4()),
        "zoneId": str(uuid.uuid4()),
        "direction": "entry",
    }
    statuses = [
        (await client.post("/api/v1/access/scan", json=body, headers=headers)).status_code
        for _ in range(70)
    ]
    assert 429 in statuses


# --- tenant isolation --------------------------------------------------------------


async def test_tenant_schema_isolation(
    zones_on, db_session: AsyncSession, branch, make_tenant_schema, open_tenant_session
) -> None:
    await make_tenant_schema("tenant_other_zones_test")
    zone = await _zone(db_session, branch, code="ISO")
    async with open_tenant_session("tenant_other_zones_test") as other:
        from vmss_api.access_control.repository import ZoneRepository

        assert await ZoneRepository(other).get(zone.id) is None
        assert (await other.execute(select(Zone))).scalars().all() == []
        assert (await other.execute(select(ZoneAccessEvent))).scalars().all() == []


async def test_other_tenant_user_cannot_scan_this_tenants_badge(
    zones_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    gate, zone, _, token = await _allowed_setup(db_session, tenant, branch)
    # A token minted for a different tenant id is rejected before any lookup.
    forged = badge_token.issue_badge_token(
        visit_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        day=datetime.now(UTC).date(),
        jti="abc",
        timezone="UTC",
    )
    response = await _scan(client, _auth(issue_token, user), forged, gate, zone)
    assert response.status_code == 400


_ = (UserFactory,)


# --- timeline integration ------------------------------------------------------------


async def test_zone_events_appear_in_the_timeline_and_vanish_when_toggle_off(
    zones_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    headers = _auth(issue_token, user)
    gate, zone, visit, token = await _allowed_setup(db_session, tenant, branch)
    await _scan(client, headers, token, gate, zone)
    await _scan(client, headers, token, gate, zone, "exit")
    other = await _zone(db_session, branch, gate, code="VAULT")
    await _scan(client, headers, token, gate, other)  # not mapped -> denied

    url = f"/api/v1/invitations/{visit.id}/timeline"
    body = (await client.get(url, headers=headers)).json()
    zone_events = {
        e["eventType"]: e["summary"] for e in body["data"] if e["eventType"].startswith("zone_")
    }
    assert zone_events == {
        "zone_entered": f"Entered zone: {zone.name}",
        "zone_exited": f"Left zone: {zone.name}",
        "zone_entry_denied": "Zone entry denied: VAULT (zone not permitted for this visitor)",
    }
    # The denial's audit row must not produce a second, duplicate timeline event:
    # the only other event is the badge print the fixture created.
    assert body["pagination"]["total"] == 4
    assert sorted(
        e["eventType"] for e in body["data"] if not e["eventType"].startswith("zone_")
    ) == ["badge_printed"]

    tenant.zone_access_enabled = False
    await db_session.commit()
    off = (await client.get(url, headers=headers)).json()
    assert [e for e in off["data"] if e["eventType"].startswith("zone_")] == []


# --- per-tenant toggle ---------------------------------------------------------------


async def test_toggle_is_set_through_tenant_settings_and_reported(
    client, user, issue_token, tenant, db_session
) -> None:
    headers = _auth(issue_token, user)
    assert (await client.get("/api/v1/zones", headers=headers)).status_code == 404
    patched = await client.patch(
        "/api/v1/tenants/me/settings", json={"zoneAccessEnabled": True}, headers=headers
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["zoneAccessEnabled"] is True
    assert patched.json()["data"]["badgePrintFlowEnabled"] is False  # untouched
    assert (await client.get("/api/v1/zones", headers=headers)).status_code == 200
    me = await client.get("/api/v1/tenants/me", headers=headers)
    assert me.json()["data"]["zoneAccessEnabled"] is True
    empty = await client.patch("/api/v1/tenants/me/settings", json={}, headers=headers)
    assert empty.status_code == 422


async def test_missing_permission_is_403_not_404_when_toggle_on(
    zones_on, client, user_without_permissions, issue_token
) -> None:
    response = await client.get(
        "/api/v1/zones", headers=_auth(issue_token, user_without_permissions)
    )
    assert response.status_code == 403


# --- gates are security-mode devices ---------------------------------------------------


@pytest.mark.parametrize("problem", ["kiosk_mode", "deleted"])
async def test_only_live_security_devices_can_be_linked_or_scanned(
    problem, zones_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    headers = _auth(issue_token, user)
    device = await _gate(db_session, branch, "BAD")
    if problem == "kiosk_mode":
        device.operating_mode = "kiosk"
    else:
        device.deleted_at = datetime.now(UTC)
    await db_session.commit()

    created = await client.post(
        "/api/v1/zones",
        json={
            "branchId": str(branch.id),
            "name": "Lab",
            "code": "LAB",
            "gateIds": [str(device.id)],
        },
        headers=headers,
    )
    assert created.status_code == 422
    assert "security device" in created.json()["message"]

    zone = await _zone(db_session, branch, code="LAB2")
    _, token = await _visit(db_session, tenant, branch)
    scanned = await _scan(client, headers, token, device, zone)
    assert scanned.status_code == 404


async def test_security_device_id_is_what_gate_ids_and_events_carry(
    zones_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    headers = _auth(issue_token, user)
    device = await _gate(db_session, branch, "GATE")
    await db_session.commit()
    created = await client.post(
        "/api/v1/zones",
        json={
            "branchId": str(branch.id),
            "name": "Lab",
            "code": "LAB",
            "gateIds": [str(device.id)],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["data"]["gateIds"] == [str(device.id)]

    zone_id = uuid.UUID(created.json()["data"]["id"])
    visit, token = await _visit(db_session, tenant, branch)
    db_session.add(InvitationZone(invitation_id=visit.id, zone_id=zone_id))
    await db_session.commit()
    zone = (await db_session.execute(select(Zone).where(Zone.id == zone_id))).scalar_one()
    assert (await _scan(client, headers, token, device, zone)).json()["data"]["allowed"] is True
    assert [e.gate_id for e in await _events(db_session, visit.id)] == [device.id]


# --- front-desk QR check-in is also a zone entry ------------------------------------------


@pytest.fixture(autouse=True)
def _default_tenant_is_the_test_tenant(monkeypatch) -> None:
    """The public QR check-in resolves its tenant from `default_tenant_slug`
    (`invitations/tests/conftest.py` does the same for its own tests)."""
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")


async def _qr_visit(db: AsyncSession, branch: Branch, **overrides) -> tuple[Invitation, str]:
    from vmss_api.invitations import qr_token

    fields: dict = {
        "status": "approved",
        "approved_at": datetime.now(UTC),
        "check_in_status": "unused",
        "preferred_visit_date": None,
        "expires_at": datetime.now(UTC) + timedelta(hours=2),
        "watchlist_flagged": False,
        "visitor_category_id": None,
        "deleted_at": None,
    }
    fields.update(overrides)
    visit = _build_invitation(db, branch.id, **fields)
    db.add(visit)
    await db.commit()
    return visit, qr_token.encrypt_invitation_token(visit.id)


def _check_in(client: AsyncClient, qr: str, device: Device | None = None):
    headers = {"device-id": device.device_id} if device else {}
    return client.patch(f"/api/v2/invitations/qr/{qr}/check-in", headers=headers)


async def test_qr_check_in_logs_an_entry_at_the_devices_zone(
    zones_on, client, db_session, tenant, branch
) -> None:
    gate = await _gate(db_session, branch)
    zone = await _zone(db_session, branch, gate)
    visit, qr = await _qr_visit(db_session, branch)
    db_session.add(InvitationZone(invitation_id=visit.id, zone_id=zone.id))
    await db_session.commit()

    response = await _check_in(client, qr, gate)
    assert response.status_code == 200, response.text
    await db_session.refresh(visit)
    assert visit.check_in_status == "checked_in"
    events = await _events(db_session, visit.id)
    assert [(e.zone_id, e.gate_id, e.direction, e.decision) for e in events] == [
        (zone.id, gate.id, "entry", "allowed")
    ]


async def test_qr_check_in_is_blocked_and_logged_when_the_zone_is_not_allowed(
    zones_on, client, db_session, tenant, branch, monkeypatch
) -> None:
    alerts: list[dict] = []

    async def _fake_notify(tenant_db, **kwargs):
        alerts.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_role_at_branch", _fake_notify)
    from factories import RoleFactory

    db_session.add(RoleFactory.build(id=uuid.uuid4(), name="security", permissions=[]))
    gate = await _gate(db_session, branch)
    zone = await _zone(db_session, branch, gate)
    visit, qr = await _qr_visit(db_session, branch)  # no zone mapping: default deny
    await db_session.commit()

    response = await _check_in(client, qr, gate)
    assert response.status_code == 403
    await db_session.refresh(visit)
    assert visit.check_in_status == "unused"  # not checked in
    events = await _events(db_session, visit.id)
    assert [(e.zone_id, e.decision, e.reason) for e in events] == [
        (zone.id, "denied", "zone_not_allowed")
    ]
    audit = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "zone_entry_denied")))
        .scalars()
        .all()
    )
    assert len(audit) == 1
    assert len(alerts) == 1 and alerts[0]["branch_id"] == branch.id


async def test_qr_check_in_is_unchanged_when_toggle_off(client, db_session, tenant, branch) -> None:
    gate = await _gate(db_session, branch)
    await _zone(db_session, branch, gate)
    visit, qr = await _qr_visit(db_session, branch)  # would be denied if zones were on
    assert (await _check_in(client, qr, gate)).status_code == 200
    assert await _events(db_session, visit.id) == []


@pytest.mark.parametrize("case", ["no_device", "kiosk_device", "no_zone", "two_zones"])
async def test_qr_check_in_logs_nothing_when_device_is_not_tied_to_one_zone(
    case, zones_on, client, db_session, tenant, branch
) -> None:
    gate = await _gate(db_session, branch)
    device: Device | None = gate
    if case == "no_device":
        device = None
        await _zone(db_session, branch, gate)
    elif case == "kiosk_device":
        gate.operating_mode = "kiosk"
        await _zone(db_session, branch, gate)
    elif case == "two_zones":
        await _zone(db_session, branch, gate, code="A")
        await _zone(db_session, branch, gate, code="B")
    await db_session.commit()
    visit, qr = await _qr_visit(db_session, branch)  # unmapped: would be denied if checked

    response = await _check_in(client, qr, device)
    assert response.status_code == 200, response.text
    assert await _events(db_session, visit.id) == []


async def test_repeat_qr_scan_does_not_log_a_second_entry(
    zones_on, client, db_session, tenant, branch
) -> None:
    gate = await _gate(db_session, branch)
    zone = await _zone(db_session, branch, gate)
    visit, qr = await _qr_visit(db_session, branch)
    db_session.add(InvitationZone(invitation_id=visit.id, zone_id=zone.id))
    await db_session.commit()
    assert (await _check_in(client, qr, gate)).status_code == 200
    assert (await _check_in(client, qr, gate)).status_code == 200  # idempotent no-op
    assert len(await _events(db_session, visit.id)) == 1


# --- default zone (add-default-zone-for-all-visitors) ---------------------------


async def _default_zone(db: AsyncSession, branch: Branch, *gates: Device, code: str = "LOBBY"):
    zone = await _zone(db, branch, *gates, code=code, is_default=True)
    return zone


async def test_default_zone_is_allowed_with_no_assignment(
    zones_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    headers = _auth(issue_token, user)
    gate = await _gate(db_session, branch)
    lobby = await _default_zone(db_session, branch, gate)
    lab = await _zone(db_session, branch, gate, code="LAB")
    visit, token = await _visit(db_session, tenant, branch)  # nothing mapped
    assert (await _scan(client, headers, token, gate, lobby)).json()["data"]["allowed"] is True
    denied = (await _scan(client, headers, token, gate, lab)).json()["data"]
    assert denied["allowed"] is False and denied["reason"] == "zone_not_allowed"
    assert len(await _events(db_session, visit.id)) == 2


async def test_default_zone_stays_allowed_beside_explicit_assignment(
    zones_on, db_session, tenant, branch
) -> None:
    from vmss_api.access_control.repository import ZoneMappingRepository

    gate = await _gate(db_session, branch)
    lobby = await _default_zone(db_session, branch, gate)
    lab = await _zone(db_session, branch, gate, code="LAB")
    visit, _ = await _visit(db_session, tenant, branch)
    db_session.add(InvitationZone(invitation_id=visit.id, zone_id=lab.id))
    await db_session.commit()
    ids = await ZoneMappingRepository(db_session).effective_zone_ids(
        visit.id, None, visit.branch_id
    )
    assert ids == {lab.id, lobby.id}


async def test_inactive_deleted_or_other_branch_default_is_not_added(
    zones_on, db_session, tenant, branch
) -> None:
    from vmss_api.access_control.repository import ZoneMappingRepository

    visit, _ = await _visit(db_session, tenant, branch)
    mapping = ZoneMappingRepository(db_session)
    other_branch = Branch(
        id=uuid.uuid4(), name="Other", code=f"OB{uuid.uuid4().hex[:4]}", is_active=True
    )
    db_session.add(other_branch)
    await db_session.flush()
    await _default_zone(db_session, other_branch, code="OTHER")
    assert await mapping.effective_zone_ids(visit.id, None, branch.id) == set()
    zone = await _default_zone(db_session, branch)
    zone.is_active = False
    await db_session.commit()
    assert await mapping.effective_zone_ids(visit.id, None, branch.id) == set()
    zone.is_active, zone.deleted_at = True, datetime.now(UTC)
    await db_session.commit()
    assert await mapping.effective_zone_ids(visit.id, None, branch.id) == set()


async def test_default_zone_does_not_bypass_other_checks(
    zones_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    headers = _auth(issue_token, user)
    gate = await _gate(db_session, branch)
    unlinked_gate = await _gate(db_session, branch, "G2")
    lobby = await _default_zone(db_session, branch, gate)
    _, flagged = await _visit(db_session, tenant, branch, watchlist_flagged=True)
    _, pending = await _visit(db_session, tenant, branch, status="pending")
    _, fine = await _visit(db_session, tenant, branch)
    assert (await _scan(client, headers, flagged, gate, lobby)).json()["data"]["reason"] == (
        "blacklisted"
    )
    assert (await _scan(client, headers, pending, gate, lobby)).json()["data"]["reason"] == (
        "not_approved"
    )
    assert (await _scan(client, headers, fine, unlinked_gate, lobby)).json()["data"]["reason"] == (
        "gate_not_linked"
    )


async def test_qr_check_in_at_default_zone_device_is_allowed_without_assignment(
    zones_on, client, db_session, tenant, branch
) -> None:
    gate = await _gate(db_session, branch)
    lobby = await _default_zone(db_session, branch, gate)
    visit, qr = await _qr_visit(db_session, branch)  # no assignment
    response = await _check_in(client, qr, gate)
    assert response.status_code == 200, response.text
    events = await _events(db_session, visit.id)
    assert [(e.zone_id, e.direction, e.decision) for e in events] == [
        (lobby.id, "entry", "allowed")
    ]


async def test_set_clear_and_replace_default_zone(
    zones_on, client, user, issue_token, db_session, branch
) -> None:
    headers = _auth(issue_token, user)
    first = (
        await client.post(
            "/api/v1/zones",
            json={"branchId": str(branch.id), "name": "Lobby", "code": "L1", "isDefault": True},
            headers=headers,
        )
    ).json()["data"]
    assert first["isDefault"] is True
    second = (
        await client.post(
            "/api/v1/zones",
            json={"branchId": str(branch.id), "name": "Cafe", "code": "C1"},
            headers=headers,
        )
    ).json()["data"]
    assert second["isDefault"] is False
    swapped = await client.put(
        f"/api/v1/zones/{second['id']}", json={"isDefault": True}, headers=headers
    )
    assert swapped.json()["data"]["isDefault"] is True
    old = await client.get(f"/api/v1/zones/{first['id']}", headers=headers)
    assert old.json()["data"]["isDefault"] is False
    only = await client.get("/api/v1/zones?isDefault=true", headers=headers)
    assert [z["id"] for z in only.json()["data"]] == [second["id"]]
    audits = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "zone_default_changed")
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 2
    cleared = await client.put(
        f"/api/v1/zones/{second['id']}", json={"isDefault": False}, headers=headers
    )
    assert cleared.json()["data"]["isDefault"] is False
    assert (await client.get("/api/v1/zones?isDefault=true", headers=headers)).json()["pagination"][
        "total"
    ] == 0


async def test_default_zone_is_protected_and_must_be_active(
    zones_on, client, user, issue_token, db_session, branch
) -> None:
    headers = _auth(issue_token, user)
    lobby = await _default_zone(db_session, branch)
    other = await _zone(db_session, branch, code="OTH")
    assert (await client.delete(f"/api/v1/zones/{lobby.id}", headers=headers)).status_code == 409
    assert (
        await client.put(f"/api/v1/zones/{lobby.id}", json={"isActive": False}, headers=headers)
    ).status_code == 409
    other.is_active = False
    await db_session.commit()
    assert (
        await client.put(f"/api/v1/zones/{other.id}", json={"isDefault": True}, headers=headers)
    ).status_code == 422
    await db_session.refresh(lobby)
    assert lobby.is_default and lobby.deleted_at is None and lobby.is_active


async def test_database_allows_only_one_default_zone_per_branch(
    zones_on, db_session, branch
) -> None:
    from sqlalchemy.exc import IntegrityError

    await _default_zone(db_session, branch, code="D1")
    with pytest.raises(IntegrityError):
        await _default_zone(db_session, branch, code="D2")
    await db_session.rollback()


async def test_default_zone_write_denied_without_permission(
    zones_on, client, user_without_permissions, issue_token, branch, db_session
) -> None:
    headers = _auth(issue_token, user_without_permissions)
    zone = await _zone(db_session, branch)
    assert (
        await client.put(f"/api/v1/zones/{zone.id}", json={"isDefault": True}, headers=headers)
    ).status_code == 403
    assert (
        await client.post(
            "/api/v1/zones",
            json={"branchId": str(branch.id), "name": "X", "code": "X", "isDefault": True},
            headers=headers,
        )
    ).status_code == 403
    await db_session.refresh(zone)
    assert zone.is_default is False


async def test_default_zone_is_isolated_per_tenant_schema(
    zones_on, db_session, branch, make_tenant_schema, open_tenant_session
) -> None:
    from vmss_api.access_control.repository import ZoneRepository

    await make_tenant_schema("tenant_other_default_zone_test")
    await _default_zone(db_session, branch, code="ISO")
    async with open_tenant_session("tenant_other_default_zone_test") as other:
        assert await ZoneRepository(other).get_default_for_branch(branch.id) is None
