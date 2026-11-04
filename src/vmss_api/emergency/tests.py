"""Who's inside by zone (add-zone-access-control)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.access_control.models import ZoneAccessEvent
from vmss_api.access_control.tests import _auth, _gate, _visit, _zone
from vmss_api.auth.models import User
from vmss_api.tenant.models import Tenant

_URL = "/api/v1/emergency/inside"


@pytest.fixture
async def zones_on(db_session: AsyncSession, tenant: Tenant) -> None:
    tenant.zone_access_enabled = True
    await db_session.commit()


def _event(visit, zone, gate, direction, decision="allowed", minutes=0) -> ZoneAccessEvent:
    return ZoneAccessEvent(
        id=uuid.uuid4(),
        invitation_id=visit.id,
        zone_id=zone.id,
        gate_id=gate.id,
        direction=direction,
        decision=decision,
        reason=None if decision == "allowed" else "zone_not_allowed",
        occurred_at=datetime.now(UTC) - timedelta(hours=1) + timedelta(minutes=minutes),
    )


async def test_occupancy_rules(
    zones_on, client: AsyncClient, user: User, issue_token, db_session: AsyncSession, tenant, branch
) -> None:
    gate = await _gate(db_session, branch)
    lab = await _zone(db_session, branch, gate, code="LAB")
    vault = await _zone(db_session, branch, gate, code="VAULT")
    inside, _ = await _visit(db_session, tenant, branch, primary_contact_full_name="In Lab")
    left, _ = await _visit(db_session, tenant, branch, primary_contact_full_name="Left Lab")
    denied, _ = await _visit(db_session, tenant, branch, primary_contact_full_name="Denied")
    gone, _ = await _visit(
        db_session,
        tenant,
        branch,
        primary_contact_full_name="Checked Out",
        status="checked_out",
        check_in_status="checked_out",
    )
    never, _ = await _visit(db_session, tenant, branch, primary_contact_full_name="Lobby Only")
    db_session.add_all(
        [
            _event(inside, lab, gate, "entry"),
            _event(left, lab, gate, "entry", minutes=0),
            _event(left, lab, gate, "exit", minutes=5),
            _event(denied, vault, gate, "entry", decision="denied"),
            # A denied re-entry must not undo an earlier allowed entry.
            _event(inside, lab, gate, "entry", decision="denied", minutes=10),
            _event(gone, lab, gate, "entry"),
        ]
    )
    await db_session.commit()

    response = await client.get(_URL, headers=_auth(issue_token, user))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert [z["zoneName"] for z in data["zones"]] == ["LAB"]
    assert [v["visitorName"] for v in data["zones"][0]["visitors"]] == ["In Lab"]
    assert sorted(v["visitorName"] for v in data["unzoned"]) == ["Denied", "Left Lab", "Lobby Only"]
    assert data["totalInside"] == 4
    assert set(data["zones"][0]["visitors"][0]) == {
        "invitationId",
        "visitorName",
        "hostName",
        "badgeNumber",
        "enteredAt",
    }
    assert never.id in {uuid.UUID(v["invitationId"]) for v in data["unzoned"]}


async def test_query_count_is_constant(
    zones_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    gate = await _gate(db_session, branch)
    lab = await _zone(db_session, branch, gate)
    statements: list[str] = []
    engine = db_session.bind.sync_engine  # type: ignore[union-attr]

    def _count(conn, cursor, statement, *args) -> None:  # noqa: ANN001
        statements.append(statement)

    async def _measure() -> int:
        statements.clear()
        event.listen(engine, "before_cursor_execute", _count)
        try:
            response = await client.get(_URL, headers=_auth(issue_token, user))
        finally:
            event.remove(engine, "before_cursor_execute", _count)
        assert response.status_code == 200
        return len(statements)

    for _ in range(2):
        visit, _ = await _visit(db_session, tenant, branch)
        db_session.add(_event(visit, lab, gate, "entry"))
    await db_session.commit()
    few = await _measure()
    for _ in range(20):
        visit, _ = await _visit(db_session, tenant, branch)
        db_session.add(_event(visit, lab, gate, "entry"))
    await db_session.commit()
    assert await _measure() == few


async def test_denied_without_permission(
    zones_on, client, user_without_permissions, issue_token
) -> None:
    response = await client.get(_URL, headers=_auth(issue_token, user_without_permissions))
    assert response.status_code == 403


async def test_404_when_toggle_off(client, user, issue_token, tenant) -> None:
    assert tenant.zone_access_enabled is False
    assert (await client.get(_URL, headers=_auth(issue_token, user))).status_code == 404


async def test_other_tenant_schema_sees_no_occupants(
    zones_on, db_session, tenant, branch, make_tenant_schema, open_tenant_session
) -> None:
    from vmss_api.core.schemas import BranchScope  # noqa: F401
    from vmss_api.emergency.repository import InsideRepository

    gate = await _gate(db_session, branch)
    lab = await _zone(db_session, branch, gate)
    visit, _ = await _visit(db_session, tenant, branch)
    db_session.add(_event(visit, lab, gate, "entry"))
    await db_session.commit()
    await make_tenant_schema("tenant_other_inside_test")
    async with open_tenant_session("tenant_other_inside_test") as other:
        repo = InsideRepository(other)
        assert await repo.occupants_by_zone("all") == []
        assert await repo.unzoned("all") == []
