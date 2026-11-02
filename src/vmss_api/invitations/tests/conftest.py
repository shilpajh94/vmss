"""Fixtures for every invitation test module. The autouse ones applied to
the whole of the old single `tests.py`, so they live here to keep doing so.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    DepartmentFactory,
    RoleFactory,
    UserFactory,
    VisitDurationFactory,
    VisitorCategoryFactory,
    VisitPurposeFactory,
)
from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.invitations import code_lockout
from vmss_api.invitations.tests import helpers
from vmss_api.invitations.tests.helpers import (
    _DEFAULT_VISITOR_CATEGORY_ID,
    _FakeRedis,
)
from vmss_api.org_structure.models import Branch, Department
from vmss_api.visit_info.models import VisitDuration, VisitPurpose


@pytest_asyncio.fixture(autouse=True)
def _reset_live_consent_field_ids():
    # The state lives in `helpers`, which reads it; assign there.
    helpers._live_consent_field_ids = None
    yield


@pytest_asyncio.fixture(autouse=True)
async def _default_visitor_category(db_session: AsyncSession) -> None:
    """Backs the fixed `visitorCategoryId` baked into `_individual_payload()`
    /`_group_payload()` — an active category with no configured approval
    workflow (no `ApprovalWorkflowRule` rows), so every existing test in
    this module keeps exercising today's single-approve behavior unless it
    explicitly attaches a workflow (see `approvals/tests.py` for the
    workflow-backed cases).
    """
    db_session.add(
        VisitorCategoryFactory.build(
            id=_DEFAULT_VISITOR_CATEGORY_ID, name="Default Test Category", code="DEFAULT-TEST"
        )
    )
    await db_session.commit()


@pytest_asyncio.fixture(autouse=True)
async def _default_host_role(db_session: AsyncSession) -> None:
    """`create_invitation` now always resolves the tenant's default host
    role (role-based-invitation-workflow) — a real tenant gets this from
    `auth/rbac_catalog.py::seed_default_roles` at provisioning time, but
    this module's fixtures don't go through that flow, so a `reception` role
    is seeded here for every test instead — same rationale as
    `_default_visitor_category` above.
    """
    db_session.add(RoleFactory.build(id=uuid.uuid4(), name="reception", permissions=[]))
    await db_session.commit()


@pytest_asyncio.fixture(autouse=True)
def _default_tenant_slug_matches_test_tenant(monkeypatch):
    """`GET /invitations/track` has no token to resolve a tenant from and
    falls back to `settings.default_tenant_slug` (`invitations/deps.py`'s
    documented limitation). The test tenant fixture (`conftest.py::tenant`)
    uses slug `acme-test`, not the app's real default — pointed at it here so
    the public tracking endpoint resolves the same tenant schema every other
    fixture in this module uses.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")


@pytest_asyncio.fixture
async def visit_department(db_session: AsyncSession, branch: Branch) -> Department:
    department = DepartmentFactory.build(
        id=uuid.uuid4(), branch_id=branch.id, floor_id=None, code="ENG-VI"
    )
    db_session.add(department)
    await db_session.commit()
    return department


@pytest_asyncio.fixture
async def visit_purpose(db_session: AsyncSession) -> VisitPurpose:
    purpose = VisitPurposeFactory.build(id=uuid.uuid4(), name="Business Meeting")
    db_session.add(purpose)
    await db_session.commit()
    return purpose


@pytest_asyncio.fixture
async def visit_duration(db_session: AsyncSession) -> VisitDuration:
    duration = VisitDurationFactory.build(id=uuid.uuid4(), name="1 hour", minutes=60)
    db_session.add(duration)
    await db_session.commit()
    return duration


@pytest_asyncio.fixture
async def visit_host(db_session: AsyncSession) -> User:
    host = UserFactory.build(
        id=uuid.uuid4(), full_name="Rahul Nair", email="rahul.nair@acme-test.example"
    )
    db_session.add(host)
    await db_session.commit()
    return host


@pytest.fixture
def fake_lockout_redis(monkeypatch) -> _FakeRedis:
    fake = _FakeRedis()

    async def _get_redis() -> _FakeRedis:
        return fake

    monkeypatch.setattr(code_lockout, "get_redis", _get_redis)
    return fake
