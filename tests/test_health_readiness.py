"""`GET /health/ready` — see
`environment-configuration` capability's "Readiness Reporting Verifies the
Configured Default Tenant and Branch Resolve" requirement
(harden-default-tenant-resolution-and-readiness). Before this change, this
endpoint only checked Postgres/Redis connectivity, so a deployment whose
`TENANT_DEFAULT_SLUG`/`REGISTRATION_DEFAULT_BRANCH_CODE` didn't resolve to an
active row reported "ready" right up until a real caller hit one of the
public endpoints that depend on that fallback and got a 401/404.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.config import settings
from vmss_api.core.database import get_db
from vmss_api.main import app
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant


async def test_health_ready_success_when_default_tenant_and_branch_are_active(
    client: AsyncClient, tenant: Tenant, branch: Branch, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "default_tenant_slug", tenant.slug)
    monkeypatch.setattr(settings, "registration_default_branch_code", branch.code)

    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


async def test_health_ready_reports_unready_when_default_tenant_unresolved(
    client: AsyncClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "default_tenant_slug", "no-such-tenant-slug")

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert "default tenant" in response.json()["message"].lower()


async def test_health_ready_reports_unready_when_default_tenant_inactive(
    client: AsyncClient, tenant: Tenant, db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "default_tenant_slug", tenant.slug)
    await db_session.execute(update(Tenant).where(Tenant.id == tenant.id).values(is_active=False))
    await db_session.commit()

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert "default tenant" in response.json()["message"].lower()


async def test_health_ready_reports_unready_when_default_branch_unresolved(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "default_tenant_slug", tenant.slug)
    monkeypatch.setattr(settings, "registration_default_branch_code", "NO-SUCH-BRANCH")

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert "default walk-in branch" in response.json()["message"].lower()


async def test_health_ready_reports_unready_when_default_branch_inactive(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "default_tenant_slug", tenant.slug)
    monkeypatch.setattr(settings, "registration_default_branch_code", branch.code)
    await db_session.execute(update(Branch).where(Branch.id == branch.id).values(is_active=False))
    await db_session.commit()

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert "default walk-in branch" in response.json()["message"].lower()


async def test_health_ready_db_unreachable_surfaces_as_unhandled_exception(
    client: AsyncClient,
) -> None:
    """Pre-existing Postgres-connectivity check, unaffected by the new
    default-tenant/branch check added after it — an unreachable database
    still surfaces the same way it always has: `core/middleware.py`'s
    `unhandled_exception_handler` builds a 500 response, but Starlette's
    `ServerErrorMiddleware` re-raises the original exception afterward (so a
    real deployment's server logs still see it), and this test's
    `ASGITransport` (default `raise_server_exceptions=True`) surfaces that
    re-raise here rather than a response object — distinct from the new
    503 misconfiguration responses above, which return normally with no
    exception involved.
    """

    async def _broken_db() -> AsyncGenerator[AsyncSession]:
        class _BrokenSession:
            async def execute(self, *_args: object, **_kwargs: object) -> None:
                raise ConnectionError("database unreachable")

        yield _BrokenSession()  # type: ignore[misc]

    app.dependency_overrides[get_db] = _broken_db
    try:
        with pytest.raises(ConnectionError):
            await client.get("/health/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)


async def test_health_ready_redis_unreachable_surfaces_as_unhandled_exception(
    client: AsyncClient, monkeypatch
) -> None:
    """Pre-existing Redis-connectivity check, same posture as the DB check
    above — unaffected by the new default-tenant/branch check.
    """

    async def _broken_get_redis() -> None:
        raise ConnectionError("redis unreachable")

    monkeypatch.setattr("vmss_api.main.get_redis", _broken_get_redis)

    with pytest.raises(ConnectionError):
        await client.get("/health/ready")
