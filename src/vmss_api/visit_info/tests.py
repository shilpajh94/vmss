import uuid

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from factories import (
    BranchFactory,
    DepartmentFactory,
    UserFactory,
    VisitDurationFactory,
    VisitPurposeFactory,
)
from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.core.security import hash_password
from vmss_api.org_structure.models import Branch, Department
from vmss_api.registrations.models import RegistrationDeviceKey
from vmss_api.tenant.models import Tenant


@pytest_asyncio.fixture
async def registration_device_raw_key(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> str:
    """Local copy of `registrations/tests.py`'s fixture of the same name —
    each feature's `tests.py` is self-contained (project convention), so this
    small setup is duplicated rather than imported cross-module.
    """
    raw_key = "test-device-raw-key-" + uuid.uuid4().hex
    db_session.add(
        RegistrationDeviceKey(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            branch_id=branch.id,
            key_hash=hash_password(raw_key),
            label="Test Kiosk",
            is_active=True,
        )
    )
    await db_session.commit()
    return raw_key


@pytest_asyncio.fixture
async def host(db_session: AsyncSession, department: Department) -> User:
    user = UserFactory.build(
        id=uuid.uuid4(),
        full_name="John Carter",
        email="john.carter@acme-test.example",
        employee_code="EMP-001",
        department_id=department.id,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def department(db_session: AsyncSession, branch: Branch) -> Department:
    department = DepartmentFactory.build(
        id=uuid.uuid4(), branch_id=branch.id, floor_id=None, code="ENG", name="Engineering"
    )
    db_session.add(department)
    await db_session.commit()
    return department


@pytest_asyncio.fixture(autouse=True)
async def _seeded_options(db_session: AsyncSession) -> None:
    """Every test in this module gets the same seeded-catalog shape the real
    `09a7eeb963d3` data migration produces — built via factories
    (testing-standards.md §1) rather than relying on the migration having
    run against the ephemeral test schema (`conftest.py` builds tables via
    `Base.metadata.create_all`, not by replaying `alembic_tenant`'s history).
    """
    purposes = [
        VisitPurposeFactory.build(id=uuid.uuid4(), name=name, sort_order=index)
        for index, name in enumerate(["Business Meeting", "Job Interview", "Other"])
    ]
    durations = [
        VisitDurationFactory.build(id=uuid.uuid4(), name=name, minutes=minutes, sort_order=index)
        for index, (name, minutes) in enumerate([("30 minutes", 30), ("Half day (4 hours)", 240)])
    ]
    db_session.add_all([*purposes, *durations])
    await db_session.commit()


def _auth_headers(device_key: str) -> dict[str, str]:
    return {"X-Device-Key": device_key}


# --- Host search --------------------------------------------------------------


async def test_search_hosts_partial_name_match(
    client: AsyncClient, registration_device_raw_key: str, host
) -> None:
    response = await client.get(
        "/api/v1/hosts/search",
        params={"query": "john"},
        headers=_auth_headers(registration_device_raw_key),
    )
    assert response.status_code == 200, response.text
    hosts = response.json()["data"]["hosts"]
    assert len(hosts) == 1
    assert hosts[0]["name"] == "John Carter"
    assert hosts[0]["email"] == "john.carter@acme-test.example"
    assert hosts[0]["department"] == "Engineering"


async def test_search_hosts_case_insensitive_email_match(
    client: AsyncClient, registration_device_raw_key: str, host
) -> None:
    response = await client.get(
        "/api/v1/hosts/search",
        params={"query": "JOHN.CARTER"},
        headers=_auth_headers(registration_device_raw_key),
    )
    assert len(response.json()["data"]["hosts"]) == 1


async def test_search_hosts_no_match_returns_empty_list(
    client: AsyncClient, registration_device_raw_key: str
) -> None:
    response = await client.get(
        "/api/v1/hosts/search",
        params={"query": "nobody-like-this"},
        headers=_auth_headers(registration_device_raw_key),
    )
    assert response.status_code == 200
    assert response.json()["data"]["hosts"] == []


async def test_search_hosts_deactivated_employee_excluded(
    client: AsyncClient, registration_device_raw_key: str, db_session: AsyncSession, host
) -> None:
    host.is_active = False
    db_session.add(host)
    await db_session.commit()

    response = await client.get(
        "/api/v1/hosts/search",
        params={"query": "john"},
        headers=_auth_headers(registration_device_raw_key),
    )
    assert response.json()["data"]["hosts"] == []


async def test_search_hosts_query_too_short_rejected(
    client: AsyncClient, registration_device_raw_key: str
) -> None:
    response = await client.get(
        "/api/v1/hosts/search",
        params={"query": "j"},
        headers=_auth_headers(registration_device_raw_key),
    )
    assert response.status_code == 422


async def test_search_hosts_limit_caps_result_count(
    client: AsyncClient, registration_device_raw_key: str, db_session: AsyncSession
) -> None:
    users = [
        UserFactory.build(
            id=uuid.uuid4(),
            full_name=f"Match Person {i}",
            email=f"match{i}@acme-test.example",
        )
        for i in range(5)
    ]
    db_session.add_all(users)
    await db_session.commit()

    response = await client.get(
        "/api/v1/hosts/search",
        params={"query": "Match Person", "limit": 2},
        headers=_auth_headers(registration_device_raw_key),
    )
    assert len(response.json()["data"]["hosts"]) == 2


async def test_search_hosts_omitted_query_returns_browsable_default_list(
    client: AsyncClient, registration_device_raw_key: str, host
) -> None:
    """`query` is optional (visit-info-lookup spec.md "Host Search Validates
    Query Length and Caps Result Count") — omitting it must not 422, and
    must return active employees instead of an empty/error response.
    """
    response = await client.get(
        "/api/v1/hosts/search", headers=_auth_headers(registration_device_raw_key)
    )
    assert response.status_code == 200, response.text
    names = [h["name"] for h in response.json()["data"]["hosts"]]
    assert "John Carter" in names


async def test_search_hosts_blank_query_returns_browsable_default_list(
    client: AsyncClient, registration_device_raw_key: str, host
) -> None:
    """A blank `query` is treated the same as an omitted one, not rejected
    as below the minimum length.
    """
    response = await client.get(
        "/api/v1/hosts/search",
        params={"query": ""},
        headers=_auth_headers(registration_device_raw_key),
    )
    assert response.status_code == 200, response.text
    names = [h["name"] for h in response.json()["data"]["hosts"]]
    assert "John Carter" in names


async def test_search_hosts_whitespace_only_query_returns_browsable_default_list(
    client: AsyncClient, registration_device_raw_key: str, host
) -> None:
    """A whitespace-only `query` (e.g. `?query=%20`) must be treated the
    same as blank/omitted, not rejected as below the minimum length —
    regression test for a bug where `.strip()`-ing a truthy-but-blank-after-
    stripping value left it counted as "supplied but too short."
    """
    response = await client.get(
        "/api/v1/hosts/search",
        params={"query": "   "},
        headers=_auth_headers(registration_device_raw_key),
    )
    assert response.status_code == 200, response.text
    names = [h["name"] for h in response.json()["data"]["hosts"]]
    assert "John Carter" in names


async def test_search_hosts_omitted_query_ordered_alphabetically_and_capped(
    client: AsyncClient, registration_device_raw_key: str, db_session: AsyncSession
) -> None:
    users = [
        UserFactory.build(
            id=uuid.uuid4(),
            full_name=name,
            email=f"{name.lower().replace(' ', '.')}@acme-test.example",
        )
        for name in ["Charlie Brown", "Alice Adams", "Bob Baker"]
    ]
    db_session.add_all(users)
    await db_session.commit()

    response = await client.get(
        "/api/v1/hosts/search",
        params={"limit": 2},
        headers=_auth_headers(registration_device_raw_key),
    )
    assert response.status_code == 200, response.text
    names = [h["name"] for h in response.json()["data"]["hosts"]]
    assert names == ["Alice Adams", "Bob Baker"]


async def test_search_hosts_tenant_schema_isolation(
    client: AsyncClient,
    registration_device_raw_key: str,
    make_tenant_schema,
    open_tenant_session,
) -> None:
    """testing-standards.md §2's tenant-isolation case — none of this
    file's three endpoints previously had one. A device key resolves to
    exactly one tenant/branch (`registrations/deps.py`), so a host seeded
    in a different tenant's schema must never appear in this tenant's
    search results.
    """
    other_schema = "tenant_other_test_visit_info"
    # A random suffix, not a literal — the extra schema `make_tenant_schema`
    # creates persists in the test database across separate `pytest`
    # invocations (unlike `db_session`'s per-test cleanup), so a fixed
    # `email` here would collide with `ix_users_email` on a second run.
    unique_email = f"other.host.{uuid.uuid4().hex[:8]}@other-tenant.example"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        other_session.add(
            UserFactory.build(id=uuid.uuid4(), full_name="Other Tenant Host", email=unique_email)
        )
        await other_session.commit()

    response = await client.get(
        "/api/v1/hosts/search",
        params={"query": "Other Tenant"},
        headers=_auth_headers(registration_device_raw_key),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["hosts"] == []


# --- Department listing -------------------------------------------------------


async def test_list_departments_scoped_to_resolved_branch(
    client: AsyncClient,
    registration_device_raw_key: str,
    department: Department,
    db_session: AsyncSession,
) -> None:
    other_branch = BranchFactory.build(id=uuid.uuid4(), code="OTHER-BR")
    other_branch_department = DepartmentFactory.build(
        id=uuid.uuid4(), branch_id=other_branch.id, floor_id=None, code="OTHER"
    )
    db_session.add_all([other_branch, other_branch_department])
    await db_session.commit()

    response = await client.get(
        "/api/v1/visit-info/departments", headers=_auth_headers(registration_device_raw_key)
    )
    assert response.status_code == 200, response.text
    names = [d["name"] for d in response.json()["data"]["departments"]]
    assert department.name in names
    assert other_branch_department.name not in names


async def test_list_departments_excludes_inactive_department(
    client: AsyncClient,
    registration_device_raw_key: str,
    department: Department,
    db_session: AsyncSession,
) -> None:
    department.is_active = False
    db_session.add(department)
    await db_session.commit()

    response = await client.get(
        "/api/v1/visit-info/departments", headers=_auth_headers(registration_device_raw_key)
    )
    assert response.json()["data"]["departments"] == []


# --- Visit-info options -------------------------------------------------------


async def test_visit_info_options_returns_seeded_purposes_and_durations(
    client: AsyncClient, registration_device_raw_key: str
) -> None:
    response = await client.get(
        "/api/v1/visit-info/options", headers=_auth_headers(registration_device_raw_key)
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    purpose_names = [p["name"] for p in data["purposes"]]
    assert purpose_names == ["Business Meeting", "Job Interview", "Other"]

    durations_by_name = {d["name"]: d["minutes"] for d in data["durations"]}
    assert durations_by_name["30 minutes"] == 30
    assert durations_by_name["Half day (4 hours)"] == 240


# --- Device-key-optional (mirrors registrations/tests.py's coverage for --
# --- walk-in — all three endpoints share the same `get_registration_device` /
# --- `get_registration_tenant_db` dependency chain, so device key is
# --- optional here too) --------------------------------------------------------


async def test_search_hosts_missing_device_key_falls_back_to_default_tenant_success(
    client: AsyncClient, tenant: Tenant, branch: Branch, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")
    monkeypatch.setattr(settings, "registration_default_branch_code", branch.code)

    response = await client.get("/api/v1/hosts/search")
    assert response.status_code == 200, response.text


async def test_list_departments_missing_device_key_falls_back_to_default_tenant_success(
    client: AsyncClient, tenant: Tenant, branch: Branch, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")
    monkeypatch.setattr(settings, "registration_default_branch_code", branch.code)

    response = await client.get("/api/v1/visit-info/departments")
    assert response.status_code == 200, response.text


async def test_visit_info_options_missing_device_key_falls_back_to_default_tenant_success(
    client: AsyncClient, tenant: Tenant, branch: Branch, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")
    monkeypatch.setattr(settings, "registration_default_branch_code", branch.code)

    response = await client.get("/api/v1/visit-info/options")
    assert response.status_code == 200, response.text


async def test_search_hosts_missing_device_key_no_default_tenant_logs_error(
    client: AsyncClient,
) -> None:
    """No `X-Device-Key` and no matching `default_tenant_slug` — a server
    misconfiguration, not a bad client credential, so it must use the
    distinct message/ERROR log level `registrations/deps.py` now applies,
    same as the walk-in coverage in `registrations/tests.py`.
    """
    with capture_logs() as captured:
        response = await client.get("/api/v1/hosts/search")

    assert response.status_code == 401
    assert (
        response.json()["message"] == "Registration service is not configured for this environment"
    )

    [entry] = [e for e in captured if e["event"] == "registration_default_tenant_unconfigured"]
    assert entry["log_level"] == "error"


# --- Rate limiting -------------------------------------------------------------


async def test_hosts_search_rate_limit_trips(
    client: AsyncClient, registration_device_raw_key: str, monkeypatch
) -> None:
    monkeypatch.setattr(limiter, "enabled", True)
    responses = [
        await client.get(
            "/api/v1/hosts/search",
            params={"query": "john"},
            headers=_auth_headers(registration_device_raw_key),
        )
        for _ in range(25)
    ]
    assert any(r.status_code == 429 for r in responses)
