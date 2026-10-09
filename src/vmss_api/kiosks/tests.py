import uuid
from collections.abc import Callable

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.kiosks.models import Kiosk
from vmss_api.kiosks.repository import KioskRepository
from vmss_api.tenant.models import Tenant


def _auth(user: User, issue_token: Callable[[User], str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token(user)}"}


async def _make_kiosk(db_session: AsyncSession, name: str = "Lobby Kiosk", **kwargs) -> Kiosk:
    kiosk = Kiosk(id=uuid.uuid4(), name=name, is_active=True, is_hidden=False, **kwargs)
    db_session.add(kiosk)
    await db_session.commit()
    return kiosk


async def test_create_kiosk_success(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    response = await client.post(
        "/api/v1/kiosks",
        json={"name": "Main Lobby", "description": "Ground floor"},
        headers=_auth(user, issue_token),
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["name"] == "Main Lobby"
    assert body["isActive"] is True
    assert body["isHidden"] is False


async def test_create_kiosk_duplicate_name_conflict(
    client: AsyncClient, user: User, issue_token: Callable[[User], str], db_session: AsyncSession
) -> None:
    await _make_kiosk(db_session, "Dup")
    response = await client.post(
        "/api/v1/kiosks", json={"name": "dup"}, headers=_auth(user, issue_token)
    )
    assert response.status_code == 409


async def test_create_kiosk_reuses_deleted_name(
    client: AsyncClient, user: User, issue_token: Callable[[User], str], db_session: AsyncSession
) -> None:
    kiosk = await _make_kiosk(db_session, "Reuse")
    headers = _auth(user, issue_token)
    assert (await client.delete(f"/api/v1/kiosks/{kiosk.id}", headers=headers)).status_code == 204
    response = await client.post("/api/v1/kiosks", json={"name": "Reuse"}, headers=headers)
    assert response.status_code == 201


async def test_list_kiosks_hides_hidden_by_default(
    client: AsyncClient, user: User, issue_token: Callable[[User], str], db_session: AsyncSession
) -> None:
    await _make_kiosk(db_session, "Visible")
    await _make_kiosk(db_session, "Secret", description=None)
    secret = (await db_session.execute(select(Kiosk).where(Kiosk.name == "Secret"))).scalar_one()
    secret.is_hidden = True
    await db_session.commit()
    headers = _auth(user, issue_token)

    default = await client.get("/api/v1/kiosks", headers=headers)
    assert {k["name"] for k in default.json()["data"]} == {"Visible"}

    everything = await client.get("/api/v1/kiosks?includeHidden=true", headers=headers)
    assert {k["name"] for k in everything.json()["data"]} == {"Visible", "Secret"}


async def test_list_kiosks_invalid_sort_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    response = await client.get("/api/v1/kiosks?sortBy=bogus", headers=_auth(user, issue_token))
    assert response.status_code == 422


async def test_get_and_update_kiosk(
    client: AsyncClient, user: User, issue_token: Callable[[User], str], db_session: AsyncSession
) -> None:
    kiosk = await _make_kiosk(db_session)
    headers = _auth(user, issue_token)
    got = await client.get(f"/api/v1/kiosks/{kiosk.id}", headers=headers)
    assert got.status_code == 200
    updated = await client.put(
        f"/api/v1/kiosks/{kiosk.id}",
        json={"description": "Updated", "isActive": False},
        headers=headers,
    )
    assert updated.status_code == 200
    data = updated.json()["data"]
    assert data["description"] == "Updated"
    assert data["isActive"] is False
    assert data["name"] == "Lobby Kiosk"


async def test_get_unknown_kiosk_404(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    response = await client.get(f"/api/v1/kiosks/{uuid.uuid4()}", headers=_auth(user, issue_token))
    assert response.status_code == 404


async def test_hide_and_unhide_kiosk(
    client: AsyncClient, user: User, issue_token: Callable[[User], str], db_session: AsyncSession
) -> None:
    kiosk = await _make_kiosk(db_session)
    headers = _auth(user, issue_token)
    hidden = await client.patch(
        f"/api/v1/kiosks/{kiosk.id}/visibility", json={"isHidden": True}, headers=headers
    )
    assert hidden.status_code == 200
    assert hidden.json()["data"]["isHidden"] is True
    assert hidden.json()["data"]["isActive"] is True
    assert (await client.get("/api/v1/kiosks", headers=headers)).json()["data"] == []
    # get-by-id still works for a hidden kiosk
    assert (await client.get(f"/api/v1/kiosks/{kiosk.id}", headers=headers)).status_code == 200

    await client.patch(
        f"/api/v1/kiosks/{kiosk.id}/visibility", json={"isHidden": False}, headers=headers
    )
    assert len((await client.get("/api/v1/kiosks", headers=headers)).json()["data"]) == 1


async def test_delete_kiosk_soft_deletes(
    client: AsyncClient, user: User, issue_token: Callable[[User], str], db_session: AsyncSession
) -> None:
    kiosk = await _make_kiosk(db_session)
    headers = _auth(user, issue_token)
    assert (await client.delete(f"/api/v1/kiosks/{kiosk.id}", headers=headers)).status_code == 204
    assert (await client.get(f"/api/v1/kiosks/{kiosk.id}", headers=headers)).status_code == 404
    await db_session.refresh(kiosk)
    assert kiosk.deleted_at is not None


async def test_kiosk_endpoints_require_authentication(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/kiosks", json={"name": "x"})).status_code == 401


async def test_kiosk_get_endpoints_are_public(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "default_tenant_slug", tenant.slug)
    kiosk = await _make_kiosk(db_session)
    assert (await client.get("/api/v1/kiosks")).status_code == 200
    assert (await client.get(f"/api/v1/kiosks/{kiosk.id}")).status_code == 200


async def test_kiosk_endpoints_require_permission(
    client: AsyncClient,
    user_without_permissions: User,
    issue_token: Callable[[User], str],
    db_session: AsyncSession,
) -> None:
    kiosk = await _make_kiosk(db_session)
    headers = _auth(user_without_permissions, issue_token)
    assert (
        await client.post("/api/v1/kiosks", json={"name": "x"}, headers=headers)
    ).status_code == 403
    assert (
        await client.put(f"/api/v1/kiosks/{kiosk.id}", json={"name": "y"}, headers=headers)
    ).status_code == 403
    assert (
        await client.patch(
            f"/api/v1/kiosks/{kiosk.id}/visibility", json={"isHidden": True}, headers=headers
        )
    ).status_code == 403
    assert (await client.delete(f"/api/v1/kiosks/{kiosk.id}", headers=headers)).status_code == 403


async def test_kiosk_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, db_session: AsyncSession
) -> None:
    kiosk = await _make_kiosk(db_session)
    other_schema = "tenant_other_test_org"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        assert await KioskRepository(other_session).get(kiosk.id) is None
