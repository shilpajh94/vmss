import uuid

from httpx import AsyncClient
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import Permission, Role, User
from vmss_api.auth.rbac_catalog import ROLE_PERMISSIONS
from vmss_api.core.database import tenant_session_scope
from vmss_api.core.rate_limit import limiter
from vmss_api.platform import service
from vmss_api.platform.models import SuperAdmin, TenantSchemaVersion
from vmss_api.tenant.models import Tenant


async def test_platform_login_success(client: AsyncClient, superadmin: SuperAdmin) -> None:
    response = await client.post(
        "/api/v1/platform/auth/login",
        json={"email": superadmin.email, "password": "correct-password"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["accessToken"]


async def test_platform_login_wrong_password(client: AsyncClient, superadmin: SuperAdmin) -> None:
    response = await client.post(
        "/api/v1/platform/auth/login",
        json={"email": superadmin.email, "password": "wrong-password"},
    )
    assert response.status_code == 401


async def test_platform_login_password_too_long_rejected(
    client: AsyncClient, superadmin: SuperAdmin
) -> None:
    """`PlatformLoginRequest.password`'s `max_length=128` bound
    (`security-architecture.md` §4) — a DoS guard on the Argon2-hashing
    input, not a restriction on legitimate passphrases; `superadmin`'s own
    fixture password ("correct-password") is far under this.
    """
    response = await client.post(
        "/api/v1/platform/auth/login",
        json={"email": superadmin.email, "password": "a" * 129},
    )
    assert response.status_code == 422


async def test_platform_login_rate_limit_trips(
    client: AsyncClient, superadmin: SuperAdmin, monkeypatch
) -> None:
    """`slowapi`'s `Limiter` is disabled outright in the test environment
    (`core/rate_limit.py`: `enabled=settings.environment != "test"`) —
    flipped on here for just this one test to exercise the 429 path
    (security-architecture.md §2), mirroring
    `invitations/tests.py::test_track_rate_limit_trips`.
    """
    monkeypatch.setattr(limiter, "enabled", True)
    responses = [
        await client.post(
            "/api/v1/platform/auth/login",
            json={"email": superadmin.email, "password": "wrong-password"},
        )
        for _ in range(10)
    ]
    assert any(r.status_code == 429 for r in responses)


async def test_create_tenant_rate_limit_trips(
    client: AsyncClient, superadmin: SuperAdmin, tenant: Tenant, monkeypatch
) -> None:
    """Reuses the already-existing `tenant` fixture's slug on every request
    so every call 409s on the slug-conflict check
    (`platform/service.py::create_tenant` checks this before ever creating
    a schema) rather than actually provisioning a new tenant schema each
    time — only the 429 path is being exercised here.
    """
    login = await client.post(
        "/api/v1/platform/auth/login",
        json={"email": superadmin.email, "password": "correct-password"},
    )
    token = login.json()["data"]["accessToken"]

    monkeypatch.setattr(limiter, "enabled", True)
    responses = [
        await client.post(
            "/api/v1/platform/tenants",
            json={"name": "Duplicate Co", "slug": tenant.slug},
            headers={"Authorization": f"Bearer {token}"},
        )
        for _ in range(6)
    ]
    assert any(r.status_code == 429 for r in responses)
    assert all(r.status_code in {409, 429} for r in responses)


async def test_create_tenant_duplicate_slug_returns_409(
    client: AsyncClient, superadmin: SuperAdmin, tenant: Tenant
) -> None:
    """Deterministic version of the slug-conflict check exercised
    incidentally by `test_create_tenant_rate_limit_trips` above — the
    limiter stays at its test-environment default (disabled), so this
    isolates the 409 from the 429 path.
    """
    login = await client.post(
        "/api/v1/platform/auth/login",
        json={"email": superadmin.email, "password": "correct-password"},
    )
    token = login.json()["data"]["accessToken"]

    response = await client.post(
        "/api/v1/platform/tenants",
        json={"name": "Duplicate Co", "slug": tenant.slug},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


async def test_create_tenant_success_via_endpoint(
    client: AsyncClient, superadmin: SuperAdmin, db_session: AsyncSession
) -> None:
    """HTTP-level happy path for `POST /platform/tenants` — distinct from
    `test_create_tenant_provisions_real_schema` below, which calls
    `service.create_tenant()` directly and never exercises the router's own
    `require_permission`/response-envelope/status-code contract. Drops the
    schema it provisions in a `finally`, same reasoning as that test.
    """
    login = await client.post(
        "/api/v1/platform/auth/login",
        json={"email": superadmin.email, "password": "correct-password"},
    )
    token = login.json()["data"]["accessToken"]
    slug = f"endpoint-test-{uuid.uuid4().hex[:8]}"

    try:
        response = await client.post(
            "/api/v1/platform/tenants",
            json={"name": "Endpoint Test Co", "slug": slug},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "Endpoint Test Co"
        assert data["slug"] == slug
        assert data["isActive"] is True
        assert uuid.UUID(data["id"])
    finally:
        await db_session.execute(text(f'DROP SCHEMA IF EXISTS "tenant_{slug}" CASCADE'))
        await db_session.commit()


async def test_list_tenants_requires_superadmin_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/platform/tenants")
    assert response.status_code == 401


async def test_create_tenant_requires_superadmin_auth(client: AsyncClient) -> None:
    """Negative-auth counterpart to `test_create_tenant_success_via_endpoint`
    — `POST /platform/tenants` only had a positive-path test before; every
    other platform endpoint's negative case is covered.
    """
    response = await client.post(
        "/api/v1/platform/tenants", json={"name": "Should Not Exist", "slug": "no-auth-tenant"}
    )
    assert response.status_code == 401


async def test_tenant_user_token_rejected_by_platform_endpoints(
    client: AsyncClient, user: User
) -> None:
    """A tenant-user `access` token must not work against a superadmin-only
    endpoint — the two auth chains (`core/tenancy.py` vs
    `platform/service.py::get_current_superadmin`) are deliberately kept
    separate by their JWT `type` claim.
    """
    login = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "correct-password"}
    )
    token = login.json()["data"]["accessToken"]

    response = await client.get(
        "/api/v1/platform/tenants", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_list_tenants_success(
    client: AsyncClient, superadmin: SuperAdmin, tenant: Tenant
) -> None:
    login = await client.post(
        "/api/v1/platform/auth/login",
        json={"email": superadmin.email, "password": "correct-password"},
    )
    token = login.json()["data"]["accessToken"]

    response = await client.get(
        "/api/v1/platform/tenants", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    slugs = {t["slug"] for t in response.json()["data"]}
    assert "acme-test" in slugs


async def test_list_tenants_sort_by_slug(
    client: AsyncClient, superadmin: SuperAdmin, tenant: Tenant, db_session: AsyncSession
) -> None:
    """verify-full-api-test-and-validation-coverage task 7.2/7.4 — the
    `sortBy`/`sortOrder` params on `GET /platform/tenants`
    (`platform/router.py::list_tenants`) are additive-only per
    `api-conventions.md` §2, but had no HTTP-level test proving they
    actually reorder the response. `tenant` fixture's slug is `acme-test`;
    provisioning a second tenant with a lexicographically earlier slug
    gives a real, order-sensitive comparison. Drops the schema it
    provisions in a `finally`, same reasoning as
    `test_create_tenant_success_via_endpoint` above.
    """
    login = await client.post(
        "/api/v1/platform/auth/login",
        json={"email": superadmin.email, "password": "correct-password"},
    )
    token = login.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    slug = f"aardvark-corp-{uuid.uuid4().hex[:8]}"

    try:
        await client.post(
            "/api/v1/platform/tenants",
            json={"name": "Aardvark Corp", "slug": slug},
            headers=headers,
        )

        asc_response = await client.get(
            "/api/v1/platform/tenants",
            params={"sortBy": "slug", "sortOrder": "asc"},
            headers=headers,
        )
        asc_slugs = [t["slug"] for t in asc_response.json()["data"]]
        assert asc_slugs.index(slug) < asc_slugs.index("acme-test")

        desc_response = await client.get(
            "/api/v1/platform/tenants",
            params={"sortBy": "slug", "sortOrder": "desc"},
            headers=headers,
        )
        desc_slugs = [t["slug"] for t in desc_response.json()["data"]]
        assert desc_slugs.index(slug) > desc_slugs.index("acme-test")
    finally:
        await db_session.execute(text(f'DROP SCHEMA IF EXISTS "tenant_{slug}" CASCADE'))
        await db_session.commit()


async def test_create_tenant_provisions_real_schema(db_session: AsyncSession) -> None:
    """Service-level test (testing-standards.md §3) for the one thing an
    HTTP-level test can't cheaply cover: that provisioning actually creates
    a working Postgres schema with every tenant migration applied, *and* the
    RBAC catalog (`auth/rbac_catalog.py`) is queryable immediately — a
    tenant provisioned through this API path must not need
    `scripts/seed_dev_data.py` run by hand before RBAC works. Safe to run
    against the real `settings.database_url` here — conftest.py points the
    whole test process at `vmss_test` before `vmss_api` is even imported, so
    this hits the same disposable database as everything else.

    Drops the schema it provisions once done: seeding the catalog writes
    `role_permissions` rows referencing the *shared* global `permissions`
    table — left behind, those rows would FK-block every later test's
    `db_session` teardown from clearing that same global table.
    """
    slug = f"provision-test-{uuid.uuid4().hex[:8]}"

    tenant = await service.create_tenant(db_session, name="Provision Test Co", slug=slug)
    try:
        assert tenant.schema_name == f"tenant_{slug}"

        tables = (
            (
                await db_session.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = :schema"
                    ),
                    {"schema": tenant.schema_name},
                )
            )
            .scalars()
            .all()
        )
        assert {"users", "roles", "audit_logs"} <= set(tables)

        version_row = await db_session.get(TenantSchemaVersion, tenant.id)
        assert version_row is not None
        assert version_row.revision

        async with tenant_session_scope(tenant.schema_name) as tenant_db:
            role_names = set((await tenant_db.execute(select(Role.name))).scalars().all())
        assert set(ROLE_PERMISSIONS.keys()) <= role_names
    finally:
        await db_session.execute(text(f'DROP SCHEMA IF EXISTS "{tenant.schema_name}" CASCADE'))
        await db_session.commit()


async def test_find_tenants_behind_head_reports_none_when_current(db_session: AsyncSession) -> None:
    """A freshly provisioned tenant's bookkeeping row is recorded at the
    current `alembic_tenant` head (`create_tenant`), so it must not show up
    as lagging.
    """
    slug = f"drift-current-{uuid.uuid4().hex[:8]}"
    tenant = await service.create_tenant(db_session, name="Drift Current Co", slug=slug)
    try:
        lagging = await service.find_tenants_behind_head(db_session)
        assert tenant.id not in {t.id for t in lagging}
    finally:
        await db_session.execute(text(f'DROP SCHEMA IF EXISTS "{tenant.schema_name}" CASCADE'))
        await db_session.commit()


async def test_upgrade_all_tenant_schemas_is_noop_when_already_current(
    db_session: AsyncSession,
) -> None:
    slug = f"upgrade-noop-{uuid.uuid4().hex[:8]}"
    tenant = await service.create_tenant(db_session, name="Upgrade Noop Co", slug=slug)
    try:
        upgraded = await service.upgrade_all_tenant_schemas(db_session)
        assert tenant.id not in {t.id for t, _ in upgraded}
    finally:
        await db_session.execute(text(f'DROP SCHEMA IF EXISTS "{tenant.schema_name}" CASCADE'))
        await db_session.commit()


async def test_upgrade_tenant_schema_corrects_stale_bookkeeping(db_session: AsyncSession) -> None:
    """Reproduces the exact drift the `afb2544db111` (form-builder) migration
    hit in dev: a tenant's `tenant_schema_versions` row lagging the current
    `alembic_tenant` head because nothing re-ran the upgrade for that
    already-provisioned tenant. `find_tenants_behind_head` must catch it, and
    `upgrade_tenant_schema`/`upgrade_all_tenant_schemas` must both re-run the
    (idempotent) Alembic upgrade and correct the bookkeeping row.
    """
    slug = f"upgrade-drift-{uuid.uuid4().hex[:8]}"
    tenant = await service.create_tenant(db_session, name="Upgrade Drift Co", slug=slug)
    try:
        await db_session.execute(
            update(TenantSchemaVersion)
            .where(TenantSchemaVersion.tenant_id == tenant.id)
            .values(revision="stale-revision")
        )
        await db_session.commit()

        lagging = await service.find_tenants_behind_head(db_session)
        assert tenant.id in {t.id for t in lagging}

        upgraded = await service.upgrade_all_tenant_schemas(db_session)
        upgraded_ids = {t.id for t, _ in upgraded}
        assert tenant.id in upgraded_ids

        head = service.get_tenant_migration_head()
        version_row = await db_session.get(TenantSchemaVersion, tenant.id)
        assert version_row is not None
        assert version_row.revision == head

        lagging_after = await service.find_tenants_behind_head(db_session)
        assert tenant.id not in {t.id for t in lagging_after}
    finally:
        await db_session.execute(text(f'DROP SCHEMA IF EXISTS "{tenant.schema_name}" CASCADE'))
        await db_session.commit()


async def test_upgrade_tenant_schema_backfills_missing_role_permission(
    db_session: AsyncSession,
) -> None:
    """specs/tenant-schema-maintenance/spec.md (delta) "Upgrading a Tenant
    Also Re-Syncs Its Standard Role Grants and Default Form Config" —
    reproduces the second half of the exact bug this change fixes: a
    standard role missing a catalog permission (simulating a tenant seeded
    before that permission existed) is granted it once `upgrade_tenant_schema`
    re-runs `seed_default_roles`, without losing a grant the role already
    held beyond the catalog.
    """
    slug = f"upgrade-rbac-{uuid.uuid4().hex[:8]}"
    tenant = await service.create_tenant(db_session, name="Upgrade RBAC Co", slug=slug)
    try:
        async with tenant_session_scope(tenant.schema_name) as tenant_db:
            admin_role = (
                await tenant_db.execute(select(Role).where(Role.name == "admin"))
            ).scalar_one()
            permission = (
                await tenant_db.execute(
                    select(Permission).where(Permission.code == "form-builder:view")
                )
            ).scalar_one()
            admin_role.permissions.remove(permission)
            await tenant_db.commit()

        await service.upgrade_tenant_schema(db_session, tenant=tenant)

        async with tenant_session_scope(tenant.schema_name) as tenant_db:
            admin_role = (
                await tenant_db.execute(select(Role).where(Role.name == "admin"))
            ).scalar_one()
            codes = {p.code for p in admin_role.permissions}
        assert "form-builder:view" in codes
        assert "form-builder:manage" in codes
    finally:
        await db_session.execute(text(f'DROP SCHEMA IF EXISTS "{tenant.schema_name}" CASCADE'))
        await db_session.commit()
