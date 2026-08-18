from httpx import AsyncClient

from vmss_api.auth.models import User
from vmss_api.tenant.models import Tenant


async def test_get_my_tenant(client: AsyncClient, user: User, tenant: Tenant) -> None:
    login = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "correct-password"}
    )
    token = login.json()["data"]["accessToken"]

    response = await client.get("/api/v1/tenants/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["id"] == str(tenant.id)
    assert body["slug"] == "acme-test"


async def test_get_my_tenant_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tenants/me")
    assert response.status_code == 401


async def test_get_my_tenant_requires_permission(
    client: AsyncClient, user_without_permissions: User
) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": user_without_permissions.email, "password": "correct-password"},
    )
    token = login.json()["data"]["accessToken"]

    response = await client.get("/api/v1/tenants/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
