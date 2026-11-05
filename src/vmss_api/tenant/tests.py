from collections.abc import Callable

from httpx import AsyncClient

from vmss_api.auth.models import User
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.repository import TenantRepository


async def test_get_my_tenant(client: AsyncClient, user: User, tenant: Tenant) -> None:
    # Read before any request: `get_tenant` rolls back the registry session,
    # which this fixture shares with the app, expiring `tenant`.
    tenant_id = tenant.id
    login = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "correct-password"}
    )
    token = login.json()["data"]["accessToken"]

    response = await client.get("/api/v1/tenants/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["id"] == str(tenant_id)
    assert body["slug"] == "acme-test"
    assert body["name"]


async def test_get_my_tenant_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tenants/me")
    assert response.status_code == 401


async def test_get_my_tenant_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)

    response = await client.get("/api/v1/tenants/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


async def test_tenant_repository_has_no_tenant_schema_to_isolate_across(
    make_tenant_schema, open_tenant_session, tenant: Tenant
) -> None:
    """Documents testing-standards.md §2's tenant-isolation requirement as
    **not applicable** to `TenantRepository`, rather than skipping it
    silently — the same reasoning `audit-and-expand-api-test-coverage`
    applied to `platform`'s repositories, per design.md's "tenant feature's
    tenant-isolation non-applicability" decision in
    `complete-api-test-coverage`.

    `Tenant` extends `GlobalBase` (`tenant/models.py`), so it carries an
    explicit `schema="global"` and bypasses `schema_translate_map` entirely
    (database-architecture.md §2; see also the `db_session` fixture's own
    docstring in root `conftest.py`) — there is no per-tenant-schema copy of
    the registry table for a session to be isolated *from*. This is the
    mirror image of `auth/tests.py::test_tenant_schema_isolation`: that test
    proves a session bound to a different schema does **not** see another
    tenant's `users` row; this one proves a session bound to a completely
    unrelated schema still sees this `Tenant` row, because `TenantRepository`
    never resolves against whichever schema its session happens to be
    pointed at in the first place.
    """
    other_schema = "tenant_other_registry_test"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await TenantRepository(other_session).get(tenant.id)
        assert found is not None
        assert found.slug == tenant.slug


async def test_patch_tenant_settings_toggles_badge_print_flow(
    client: AsyncClient, user: User, tenant: Tenant, issue_token: Callable[[User], str]
) -> None:
    headers = {"Authorization": f"Bearer {issue_token(user)}"}

    before = await client.get("/api/v1/tenants/me", headers=headers)
    assert before.json()["data"]["badgePrintFlowEnabled"] is False

    response = await client.patch(
        "/api/v1/tenants/me/settings", json={"badgePrintFlowEnabled": True}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["badgePrintFlowEnabled"] is True

    after = await client.get("/api/v1/tenants/me", headers=headers)
    assert after.json()["data"]["badgePrintFlowEnabled"] is True


async def test_patch_tenant_settings_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    response = await client.patch(
        "/api/v1/tenants/me/settings",
        json={"badgePrintFlowEnabled": True},
        headers={"Authorization": f"Bearer {issue_token(user_without_permissions)}"},
    )
    assert response.status_code == 403


async def test_patch_tenant_settings_toggles_badge_print_id_verification(
    client: AsyncClient, user: User, tenant: Tenant, issue_token: Callable[[User], str]
) -> None:
    headers = {"Authorization": f"Bearer {issue_token(user)}"}

    before = await client.get("/api/v1/tenants/me", headers=headers)
    assert before.json()["data"]["badgePrintRequiresIdVerification"] is True

    response = await client.patch(
        "/api/v1/tenants/me/settings",
        json={"badgePrintRequiresIdVerification": False},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["badgePrintRequiresIdVerification"] is False
    # Untouched switches keep their value.
    assert response.json()["data"]["badgePrintFlowEnabled"] is False
