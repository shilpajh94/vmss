import os
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

os.environ.setdefault("APP_ENV", "test")

# Point the whole process at `vmss_test` *before* any `vmss_api` import.
# `core/database.py` builds its module-level `engine` — and everything on
# top of it: `get_tenant_db`, `tenant_session_scope`, used directly by
# `auth/service.py`'s login flow, not just via an overridable `Depends()` —
# once, at import time, from `settings.database_url` (a computed field built
# from `DB_*` env vars, see `core/config.py`). Patching that after the fact
# (e.g. in a fixture) can't reach the already-built engine, so this has to
# happen first, the same way `ENVIRONMENT` is set above.
os.environ["DB_NAME"] = "vmss_test"

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from factories import (
    BranchFactory,
    PermissionFactory,
    RoleFactory,
    SuperAdminFactory,
    TenantFactory,
    UserFactory,
)
from vmss_api.auth.models import User, UserBranchRole
from vmss_api.core.config import settings
from vmss_api.core.database import Base, GlobalBase, get_db
from vmss_api.core.security import create_access_token, hash_password
from vmss_api.core.tenancy import get_tenant_db
from vmss_api.invitations import qr_token
from vmss_api.main import app
from vmss_api.org_structure.models import Branch
from vmss_api.platform.models import SuperAdmin, TenantUserIndex
from vmss_api.tenant.models import Tenant

# `settings.database_url` already resolves to `vmss_test` (the `DB_NAME`
# override above takes effect before `Settings()` is ever constructed).
# `_dev_url` targets Postgres's always-present `postgres` maintenance
# database instead — needed to run `CREATE DATABASE vmss_test` itself, since
# you can't connect to a database that doesn't exist yet to create it.
_test_url = make_url(settings.database_url)
_dev_url = _test_url.set(database="postgres")

_TENANT_SCHEMA = "tenant_acme_test"


async def _create_schema_and_tables(engine, schema_name: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
    tenant_engine = engine.execution_options(schema_translate_map={None: schema_name})
    async with tenant_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _test_database() -> AsyncGenerator[None]:
    """Creates the dedicated `vmss_test` database, the global schema (with
    its tables), and the default test tenant's schema (with its tables),
    once per run. Real Postgres, not SQLite — see project-rules.md
    §Testing — specifically so schema-per-tenant behavior (`CREATE SCHEMA`,
    `schema_translate_map`, cross-schema FKs) is exercised for real, not
    assumed.
    """
    admin_engine = create_async_engine(_dev_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        exists = await conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": _test_url.database}
        )
        if exists.scalar() is None:
            await conn.execute(text(f'CREATE DATABASE "{_test_url.database}"'))
    await admin_engine.dispose()

    test_engine = create_async_engine(_test_url)
    async with test_engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{settings.global_schema_name}"'))
        await conn.run_sync(GlobalBase.metadata.create_all)
    await _create_schema_and_tables(test_engine, _TENANT_SCHEMA)
    await test_engine.dispose()
    yield


@pytest.fixture(autouse=True)
def _qr_token_encryption_key(monkeypatch) -> None:
    """QR-token generation is now part of the core invitation-approval path
    (`add-qr-checkin-security`), not an opt-in feature the way SSO's own
    `sso_encryption_key` is — so, unlike `sso/tests.py`'s per-test
    `monkeypatch.setattr`, this needs to be configured for every test by
    default, not just the ones that exercise it directly.
    """
    monkeypatch.setattr(settings, "qr_token_encryption_key", Fernet.generate_key().decode())
    qr_token._fernet.cache_clear()


@pytest_asyncio.fixture
async def make_tenant_schema() -> AsyncGenerator[Callable[[str], Awaitable[None]]]:
    """Factory for provisioning an extra tenant schema on demand, for tests
    that need more than one (e.g. tenant-isolation tests) — most tests only
    need the default one the session fixture above already sets up.

    Drops the schema first: callers use a fixed literal name (e.g.
    `tenant_other_category_test`) rather than a per-run unique one, and
    `CREATE SCHEMA IF NOT EXISTS` alone leaves any row a previous test run
    committed into it still there — a test that inserts a uniquely-named
    row (not just reads) collides with its own leftover data on the next
    run otherwise.
    """
    engine = create_async_engine(_test_url)

    async def _make(schema_name: str) -> None:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        await _create_schema_and_tables(engine, schema_name)

    yield _make
    await engine.dispose()


@pytest_asyncio.fixture
async def open_tenant_session() -> AsyncGenerator[Callable[[str], AsyncIterator[AsyncSession]]]:
    """Factory returning an async-context-managed session bound to an
    arbitrary tenant schema — for tests (tenant-isolation, cross-schema
    checks) that need to look at a schema other than the default one
    `db_session`/`client` are bound to.
    """
    engines = []

    @asynccontextmanager
    async def _open(schema_name: str) -> AsyncGenerator[AsyncSession]:
        engine = create_async_engine(_test_url).execution_options(
            schema_translate_map={None: schema_name}
        )
        engines.append(engine)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            yield session

    yield _open
    for engine in engines:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """Bound to the default test tenant's schema for `Base` (tenant) table
    queries; `GlobalBase` tables (`Tenant`, `Permission`, `TenantUserIndex`,
    ...) resolve to the global schema regardless, since they carry an
    explicit schema and bypass the translate map — see database-architecture.md §2.
    """
    engine = create_async_engine(_test_url).execution_options(
        schema_translate_map={None: _TENANT_SCHEMA}
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        for table in reversed(GlobalBase.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()
    await engine.dispose()


@pytest_asyncio.fixture
async def tenant(db_session: AsyncSession) -> Tenant:
    # `timezone` is forced explicitly: `Tenant.timezone`'s Python-side
    # `default="UTC"` (tenant/models.py) only applies to a row inserted with
    # no value at all — polyfactory's `SQLAlchemyFactory` always generates a
    # value for a plain `String` column instead of honoring that default, so
    # `TenantFactory.build()` alone would produce a random hex string that
    # isn't a valid IANA zone name (`dashboard/service.py` resolves this via
    # `zoneinfo.ZoneInfo`).
    tenant = TenantFactory.build(
        id=uuid.uuid4(),
        name="Acme Test Co",
        slug="acme-test",
        schema_name=_TENANT_SCHEMA,
        timezone="UTC",
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant


@pytest_asyncio.fixture
async def branch(db_session: AsyncSession) -> Branch:
    branch = BranchFactory.build(id=uuid.uuid4(), name="Main Branch", code="MAIN")
    db_session.add(branch)
    await db_session.commit()
    return branch


ADMIN_PERMISSION_CODES = [
    "visitors:checkin",
    "tenants:read",
    "branches:view",
    "branches:manage",
    "branches:provision",
    "reports:view",
    "users:manage",
    "companies:view",
    "companies:manage",
    "buildings:view",
    "buildings:manage",
    "floors:view",
    "floors:manage",
    "departments:view",
    "departments:manage",
    "desks:view",
    "desks:manage",
    "gates:view",
    "gates:manage",
    "employees:view",
    "employees:manage",
    "visitor-categories:view",
    "visitor-categories:manage",
    "approval-workflow-rules:view",
    "approval-workflow-rules:manage",
    "invitations:create",
    "invitations:view",
    "invitations:cancel",
    "invitations:approve",
    "invitations:approve-override",
    "invitations:deny",
    "invitations:checkin",
    "invitations:checkout",
    "invitations:reschedule",
    "invitations:extend",
    "invitations:badge",
    "invitations:watchlist-override",
    "roles:view",
    "roles:manage",
    "sso-config:view",
    "sso-config:manage",
    "audit-logs:view",
    "audit-logs:export",
]


@pytest_asyncio.fixture
async def user(db_session: AsyncSession, tenant: Tenant) -> User:
    """A company-wide Admin — its `UserBranchRole.branch_id` is `None`, so
    `has_permission`/`has_branch_access` (auth/models.py) grant it at every
    branch, not just one. See `org_structure/tests.py` for a branch-scoped
    (single-location) role fixture.
    """
    permissions = [
        PermissionFactory.build(id=uuid.uuid4(), code=code, description=code)
        for code in ADMIN_PERMISSION_CODES
    ]
    role = RoleFactory.build(id=uuid.uuid4(), name="admin", permissions=permissions)
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=None)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email="admin@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Admin User",
        branch_roles=[branch_role],
    )
    db_session.add_all([*permissions, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


@pytest_asyncio.fixture
async def user_without_permissions(db_session: AsyncSession, tenant: Tenant) -> User:
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email="no-permissions@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="No Permissions User",
    )
    db_session.add(test_user)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


@pytest.fixture
def issue_token(tenant: Tenant) -> Callable[[User], str]:
    """Mints a valid access token directly (the same helper `POST
    /auth/login`/the SSO exchange endpoint use internally), bypassing the
    password-login endpoint entirely. `separate-admin-staff-login` made
    `POST /auth/login` reject any non-Admin account, so RBAC/branch-scoping
    tests that need a bearer token for an arbitrary role — purely to
    exercise a permission or branch-scoping check, not to test login
    itself — use this instead of the per-file `_login()` HTTP helper.
    Real login-flow behavior (including the Admin-only gate) stays covered
    by `auth/tests.py`'s and `sso/tests.py`'s own login tests, which still
    go through the real endpoints.
    """

    def _issue(user: User) -> str:
        return create_access_token(user.id, tenant.id)

    return _issue


@pytest_asyncio.fixture
async def superadmin(db_session: AsyncSession) -> SuperAdmin:
    admin = SuperAdminFactory.build(
        id=uuid.uuid4(),
        email="root@platform.example",
        hashed_password=hash_password("correct-password"),
        full_name="Platform Root",
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def _override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    # `get_tenant_db` builds its own tenant-bound session rather than
    # depending on `get_db`, so overriding `get_db` alone wouldn't reach it.
    # Routing it through the same `db_session` the test itself uses (rather
    # than a second, real connection — now correctly `vmss_test`-bound too,
    # see the module-level `DATABASE_URL` swap above, but still a separate
    # session) keeps everything a request touches visible to, and cleaned up
    # by, one fixture.
    app.dependency_overrides[get_tenant_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
