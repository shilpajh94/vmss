import asyncio
import csv
import html as html_lib
import io
import json
import re
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import aiosmtplib
import openpyxl
import pytest
import pytest_asyncio
import starlette.datastructures as starlette_datastructures
import structlog
from fastapi import HTTPException
from httpx import AsyncClient, Response
from openpyxl.utils import get_column_letter
from PIL import Image
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from factories import (
    ApprovalWorkflowRuleFactory,
    BranchFactory,
    BuildingFactory,
    CompanyFactory,
    DepartmentFactory,
    FloorFactory,
    InvitationApprovalStepFactory,
    InvitationFactory,
    InvitationVehicleFactory,
    InvitationVisitorFactory,
    PermissionFactory,
    RoleFactory,
    UserFactory,
    VisitDurationFactory,
    VisitorCategoryFactory,
    VisitPurposeFactory,
)
from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.auth.models import AuditLog, Permission, User, UserBranchRole
from vmss_api.auth.rbac_catalog import seed_default_roles
from vmss_api.auth.repository import RoleRepository
from vmss_api.core import storage
from vmss_api.core.config import settings
from vmss_api.core.database import AsyncSessionLocal
from vmss_api.core.rate_limit import limiter
from vmss_api.core.schemas import SortOrder
from vmss_api.core.security import hash_password
from vmss_api.core.sms import SmsTemplate
from vmss_api.core.whatsapp import WhatsAppTemplate
from vmss_api.form_builder.defaults import _stable_id as _form_builder_stable_id
from vmss_api.invitations import code_lockout, notifications, qr_token, tasks
from vmss_api.invitations import export as invitation_export
from vmss_api.invitations import service as invitations_service
from vmss_api.invitations.models import (
    Invitation,
    InvitationQRCode,
    InvitationVehicle,
    InvitationVisitor,
)
from vmss_api.invitations.qr import generate_qr_png
from vmss_api.invitations.repository import InvitationExportNames, InvitationRepository
from vmss_api.invitations.schemas import (
    ExportFormat,
    InvitationExportDateRange,
    InvitationStatus,
    RegistrationSource,
    RegistrationType,
)
from vmss_api.notifications import service as notifications_service
from vmss_api.org_structure.models import Branch, Company, Department
from vmss_api.platform.models import TenantUserIndex
from vmss_api.tenant.models import Tenant
from vmss_api.visit_info.models import VisitDuration, VisitPurpose

# Fixed id baked into `_individual_payload()`/`_group_payload()` below, and
# created for real by the `_default_visitor_category` autouse fixture — every
# test in this module gets a valid, active `visitorCategoryId` for free
# without having to plumb one through each of the ~40 call sites that build
# an invitation-creation payload.
_DEFAULT_VISITOR_CATEGORY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


_DEFAULT_CONSENT_KEYS = (
    "terms_accepted",
    "data_processing_accepted",
    "safety_guidelines_accepted",
)

# Set by any of the admin-side `_create_and_publish_*`/`_configure_and_
# publish_branch_field`/`_update_and_publish_group_range` helpers below,
# reset to `None` before every test by `_reset_live_consent_field_ids`
# (autouse). Publishing seeds the branch's default steps/fields as *real*
# database rows (random ids) the first time anything is fetched/published
# for it — a branch that's never touched form-builder admin endpoints at
# all still resolves against `DEFAULT_EFFECTIVE_FORM`'s deterministic
# ids (`_default_consent_field_id` below), but the moment a test publishes
# anything, the branch's Consent Agreement fields get real ids that no
# longer match that deterministic fallback (restructure-walkin-payload-
# by-field-id). This lets `_individual_payload()`/`_group_payload()` keep
# working unmodified either way, without every publishing test having to
# separately re-derive and patch its own `consents`.
_live_consent_field_ids: dict[str, str] | None = None


@pytest_asyncio.fixture(autouse=True)
def _reset_live_consent_field_ids():
    global _live_consent_field_ids
    _live_consent_field_ids = None
    yield


def _record_live_consent_field_ids(steps: list[dict]) -> None:
    """Called by every admin-side setup helper right after it publishes, so
    subsequent `_individual_payload()`/`_group_payload()` calls in the same
    test pick up the branch's now-real Consent Agreement field ids."""
    global _live_consent_field_ids
    step = next((s for s in steps if s["key"] == "consent_agreement"), None)
    if step is None:
        return
    _live_consent_field_ids = {f["key"]: f["id"] for f in step["fields"]}


def _default_consent_field_id(key: str) -> str:
    """The current Consent Agreement field id for `key` — the branch's own
    real id if a test has published anything for it
    (`_live_consent_field_ids`), otherwise the deterministic id
    `form_builder/defaults.py::DEFAULT_EFFECTIVE_FORM` assigns it, matching
    what `resolve_effective_form` falls back to for a branch with no
    published `FormConfigVersion` at all (restructure-walkin-payload-by-
    field-id). Lets `_individual_payload()`/`_group_payload()` submit
    `consents` by id without every test needing its own form-builder round
    trip.
    """
    if _live_consent_field_ids is not None and key in _live_consent_field_ids:
        return _live_consent_field_ids[key]
    return str(_form_builder_stable_id("field", "consent_agreement", key))


def _set_consent_accepted(payload: dict, key: str, accepted: bool) -> None:
    """Mutates `payload["consents"]` (built by `_individual_payload()`/
    `_group_payload()`) in place, flipping the default consent field
    identified by its default *key* to `accepted` — a test-authoring
    convenience so call sites can keep referring to a consent by its
    readable default key instead of `_default_consent_field_id(key)`."""
    field_id = _default_consent_field_id(key)
    entry = next(c for c in payload["consents"] if c["fieldId"] == field_id)
    entry["accepted"] = accepted


def _add_consent(payload: dict, field_id: str, accepted: bool) -> None:
    payload["consents"].append({"fieldId": field_id, "accepted": accepted})


def _remove_default_consent(payload: dict, key: str) -> None:
    """Drops the default consent field identified by its default *key*
    from `payload["consents"]` in place."""
    field_id = _default_consent_field_id(key)
    payload["consents"] = [c for c in payload["consents"] if c["fieldId"] != field_id]


def _custom_field_value(entries: list[dict], field_id: str) -> Any:
    """Looks up one `{fieldId, value}` entry's `value` out of a response's
    `customFields` array by `fieldId` — the
    read-side counterpart of building a `customFields` request array by
    hand (restructure-walkin-payload-by-field-id)."""
    return next(e["value"] for e in entries if e["fieldId"] == field_id)


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="JPEG")
    return buffer.getvalue()


def _individual_payload() -> dict:
    return {
        "registrationType": "individual",
        "visitorCategoryId": str(_DEFAULT_VISITOR_CATEGORY_ID),
        "primaryContact": {
            "fullName": "Meera Krishnan",
            "email": "meera.krishnan@example.com",
            "preferredContactMethod": "email",
            "idProofType": "Passport",
        },
        "visitors": [],
        "visitDetails": {
            "purposeOfVisit": "Interview",
            "hostNameOrEmail": "hr@enterprise-ugo.co",
            "preferredVisitDate": "2026-08-12",
            "preferredVisitTime": "10:00:00",
            "expectedDuration": "< 1 hour",
            "departmentToVisit": "Human Resources",
        },
        "carriedItems": {"items": []},
        "vehicles": [],
        # Referenced by fieldId, never key/label
        # (restructure-walkin-payload-by-field-id) — one entry per default
        # Consent Agreement field, for a branch that has never customized it.
        "consents": [
            {"fieldId": _default_consent_field_id("terms_accepted"), "accepted": True},
            {"fieldId": _default_consent_field_id("data_processing_accepted"), "accepted": True},
            {"fieldId": _default_consent_field_id("safety_guidelines_accepted"), "accepted": True},
        ],
    }


def _group_payload() -> dict:
    return {
        "registrationType": "group",
        "visitorCategoryId": str(_DEFAULT_VISITOR_CATEGORY_ID),
        "primaryContact": {
            "fullName": "Priya Sharma",
            "email": "priya.sharma@enterprise-ugo.co",
            "phone": "+91 98765 43210",
            "preferredContactMethod": "email",
            "idProofType": "Aadhaar Card",
        },
        "visitors": [
            {
                "fullName": "Alexander Pierce",
                "email": "alexander.p@enterprise-ugo.co",
                "idProofType": "Aadhaar Card",
            },
            {
                "fullName": "Clara Oswald",
                "phone": "+1 (555) 014-0362",
                "idProofType": "Passport",
            },
        ],
        "visitDetails": {
            "purposeOfVisit": "Business Meeting",
            "hostNameOrEmail": "Rahul Nair",
            "preferredVisitDate": "2026-08-15",
            "preferredVisitTime": "14:30:00",
            "expectedDuration": "1-2 hours",
            "departmentToVisit": "Engineering",
        },
        "carriedItems": {
            "items": ["laptop_tablet", "mobile_phone"],
            "itemDescription": "2 laptops",
        },
        "vehicles": [
            {
                "vehicleType": "4_wheeler",
                "licensePlate": "KA-01-AB-1234",
                "makeModel": "Honda City",
                "color": "White",
            },
            {"vehicleType": "2_wheeler", "licensePlate": "KA-05-CD-5678"},
        ],
        "consents": [
            {"fieldId": _default_consent_field_id("terms_accepted"), "accepted": True},
            {"fieldId": _default_consent_field_id("data_processing_accepted"), "accepted": True},
            {"fieldId": _default_consent_field_id("safety_guidelines_accepted"), "accepted": True},
        ],
    }


async def _login(client: AsyncClient, email: str, password: str = "correct-password") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["data"]["accessToken"]


async def _create_invitation(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    payload: dict,
    visitor_file_count: int = 0,
    idempotency_key: str | None = None,
) -> Response:
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    files = [
        ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
        ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
    ]
    files += [
        ("visitor_id_proof_files", (f"v{i}.jpg", _jpeg_bytes(), "image/jpeg"))
        for i in range(visitor_file_count)
    ]
    return await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(payload)},
        files=files,
        headers=headers,
    )


async def _create_invitation_success(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    payload: dict,
    visitor_file_count: int = 0,
    idempotency_key: str | None = None,
) -> dict:
    response = await _create_invitation(
        client,
        token,
        branch,
        payload=payload,
        visitor_file_count=visitor_file_count,
        idempotency_key=idempotency_key,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


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


# --- API-09: employee creates a fully completed invitation -------------------


async def test_create_individual_invitation_success(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=_individual_payload())
    assert data["registrationType"] == "individual"
    assert data["status"] == "submitted"
    assert data["trackingId"].startswith("INV-")
    assert data["submittedAt"] is not None
    # Regression check (add-walkin-visitor-registration): the existing
    # staff-created flow is unaffected by the new `source` column — it
    # still defaults to "staff_pre_registration" without the caller having
    # to pass anything new.
    assert data["source"] == "staff_pre_registration"


async def test_create_group_invitation_success_with_visitors_and_vehicles(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    token = await _login(client, user.email)
    data = await _create_invitation_success(
        client, token, branch, payload=_group_payload(), visitor_file_count=2
    )
    assert data["status"] == "submitted"

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert len(invitation.visitors) == 2
    assert len(invitation.vehicles) == 2
    assert invitation.carried_items == ["laptop_tablet", "mobile_phone"]
    assert invitation.consents.get(_default_consent_field_id("terms_accepted")) is True


# --- invitation-multi-step-approval: visitorCategoryId on creation ----------


async def test_create_invitation_missing_visitor_category_id_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _individual_payload()
    del payload["visitorCategoryId"]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_unknown_visitor_category_id_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitorCategoryId"] = str(uuid.uuid4())
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_inactive_visitor_category_id_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    token = await _login(client, user.email)
    inactive_category = VisitorCategoryFactory.build(
        id=uuid.uuid4(), name="Inactive Category", code="INACTIVE", is_active=False
    )
    db_session.add(inactive_category)
    await db_session.commit()

    payload = _individual_payload()
    payload["visitorCategoryId"] = str(inactive_category.id)
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_cross_tenant_visitor_category_id_rejected(
    client: AsyncClient,
    user: User,
    branch: Branch,
    make_tenant_schema,
    open_tenant_session,
) -> None:
    """testing-standards.md §2 tenant-isolation case: a category id that is
    valid in another tenant's schema must not be usable from this tenant's
    session — the category lookup is a plain `WHERE id=...` scoped to
    whichever schema the session is bound to, same isolation guarantee as
    every other `TenantScopedRepository` query.
    """
    other_schema = "tenant_other_category_test"
    await make_tenant_schema(other_schema)
    other_category_id = uuid.uuid4()
    async with open_tenant_session(other_schema) as other_session:
        other_session.add(
            VisitorCategoryFactory.build(
                id=other_category_id, name="Other Tenant Category", code="OTHER-TENANT"
            )
        )
        await other_session.commit()

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitorCategoryId"] = str(other_category_id)
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_response_includes_visitor_category_id(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=_individual_payload())
    assert data["visitorCategoryId"] == str(_DEFAULT_VISITOR_CATEGORY_ID)


# --- Auto-approve driven status/notification (add-invitation-approval-flow-and-role-resync) ---


async def test_create_invitation_auto_approve_enabled_is_approved_immediately(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), auto_approve_pre_registered_visitors=True))
    await db_session.commit()

    approval_calls: list[dict] = []
    tracking_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )
    monkeypatch.setattr(
        tasks.send_tracking_notification, "delay", lambda **kw: tracking_calls.append(kw)
    )

    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=_individual_payload())

    assert data["status"] == "approved"
    assert data["approvedAt"] is not None
    assert len(approval_calls) == 1  # the QR-bearing notification, not the tracking-only one
    assert tracking_calls == []


async def test_create_invitation_auto_approve_issues_qr_code_with_matching_token(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """add-qr-checkin-security spec.md "Token is generated once at
    approval" — the token persisted in `InvitationQRCode` is exactly the
    one handed to the approval-notification task, and it decrypts back to
    the invitation it was issued for.
    """
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), auto_approve_pre_registered_visitors=True))
    await db_session.commit()

    approval_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )

    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=_individual_payload())
    invitation_id = uuid.UUID(data["id"])

    qr_row = (
        await db_session.execute(
            select(InvitationQRCode).where(InvitationQRCode.invitation_id == invitation_id)
        )
    ).scalar_one()
    assert qr_token.decrypt_invitation_token(qr_row.qr_token) == invitation_id
    assert approval_calls[0]["qr_token"] == qr_row.qr_token


async def test_create_invitation_auto_approve_disabled_is_awaiting_approval(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    db_session.add(
        CompanyFactory.build(id=uuid.uuid4(), auto_approve_pre_registered_visitors=False)
    )
    await db_session.commit()

    approval_calls: list[dict] = []
    tracking_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )
    monkeypatch.setattr(
        tasks.send_tracking_notification, "delay", lambda **kw: tracking_calls.append(kw)
    )

    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=_individual_payload())

    assert data["status"] == "submitted"
    assert data["approvedAt"] is None
    assert len(tracking_calls) == 1  # tracking-only — no QR code yet
    assert approval_calls == []


async def test_create_invitation_auto_approve_never_resolves_a_host(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    visit_host: User,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    """An auto-approved invitation gets no `InvitationApprovalStep` rows at
    all (create_invitation's `if not auto_approved:` gate) — so, unlike a
    manual-approval invitation, it has no ownership step for anyone to
    delegate. Combined with "A supplied hostId or hostNameOrEmail is
    silently ignored" (role-based-invitation-workflow), that means an
    auto-approved invitation never gets a resolved host at all: `hostId`
    stays null, and no one sees it in their `relevantToMe` worklist by
    virtue of being its host. Accepted current behavior — auto-approve
    skips the whole approval/delegation workflow, host resolution
    included, not just the approval gate.
    """
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), auto_approve_pre_registered_visitors=True))
    await db_session.commit()
    monkeypatch.setattr(tasks.send_approval_notification, "delay", lambda **kw: None)
    monkeypatch.setattr(tasks.send_host_creation_notification, "delay", lambda **kw: None)

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["hostId"] = str(visit_host.id)
    created = await _create_invitation_success(client, token, branch, payload=payload)
    assert created["status"] == "approved"
    assert created["hostId"] is None

    host_token = issue_token(visit_host)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true", "status": "approved"},
        headers={"Authorization": f"Bearer {host_token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert created["trackingId"] not in tracking_ids


async def test_create_invitation_no_company_profile_defaults_to_awaiting_approval(
    client: AsyncClient, user: User, branch: Branch, monkeypatch
) -> None:
    """No `Company` profile at all (not even a disabled one) — the more
    conservative "awaiting approval" path, matching the column's own
    default (spec.md "No configured company profile defaults to awaiting
    approval").
    """
    tracking_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_tracking_notification, "delay", lambda **kw: tracking_calls.append(kw)
    )

    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=_individual_payload())

    assert data["status"] == "submitted"
    assert data["approvedAt"] is None
    assert len(tracking_calls) == 1


@pytest.mark.parametrize(
    ("payload_factory", "visitor_file_count"),
    [(_individual_payload, 0), (_group_payload, 2)],
    ids=["individual", "group"],
)
async def test_create_invitation_requires_permission(
    client: AsyncClient,
    user_without_permissions: User,
    branch: Branch,
    payload_factory,
    visitor_file_count: int,
    issue_token: Callable[[User], str],
) -> None:
    token = issue_token(user_without_permissions)
    response = await _create_invitation(
        client,
        token,
        branch,
        payload=payload_factory(),
        visitor_file_count=visitor_file_count,
    )
    assert response.status_code == 403


async def test_create_invitation_without_branch_header_or_payload_rejected(
    client: AsyncClient, user: User
) -> None:
    """Neither the `X-Branch-ID` header nor `branchId` in the payload is
    supplied — omitting both is a handled 400, not FastAPI's generic
    required-header 422.
    """
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(_individual_payload())},
        files=[
            ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


async def test_create_invitation_branch_id_in_payload_used_when_header_omitted(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """`branchId` in the payload resolves the branch when `X-Branch-ID` is
    omitted entirely — the header is not the only way to identify one.
    """
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["branchId"] = str(branch.id)
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(payload)},
        files=[
            ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201


async def test_create_invitation_requires_reachable_contact_for_method(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["primaryContact"] = {
        "fullName": "Rahul Nair",
        "phone": "+91 90000 11122",
        "preferredContactMethod": "email",
        "idProofType": "Aadhaar Card",
    }
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_missing_consent_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _individual_payload()
    _set_consent_accepted(payload, "safety_guidelines_accepted", False)
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_omitted_consents_defaults_to_empty_list(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """`consents` is optional on the wire (defaults to `[]` when omitted),
    but that doesn't bypass the branch's required-consent check — a branch
    with required Consent Agreement fields still rejects an empty/omitted
    `consents` the same way it rejects an explicit non-accepted one
    (test_create_invitation_missing_consent_rejected)."""
    token = await _login(client, user.email)
    payload = _individual_payload()
    del payload["consents"]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_disguised_file_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(_individual_payload())},
        files=[
            (
                "primary_contact_id_proof_file",
                ("id.jpg", b"this is not actually an image, just plain text bytes", "image/jpeg"),
            ),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 422


async def test_create_invitation_oversized_file_rejected(
    client: AsyncClient, user: User, branch: Branch, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "invitation_max_upload_size_bytes", 10)
    token = await _login(client, user.email)
    response = await _create_invitation(client, token, branch, payload=_individual_payload())
    assert response.status_code == 422


async def test_create_invitation_oversized_file_read_is_bounded(
    client: AsyncClient, user: User, branch: Branch, monkeypatch
) -> None:
    """add-avatar-upload-and-verify-image-storage design.md Decision 3 — the
    router bounds each `UploadFile.read()` call to `max_size_bytes + 1`
    rather than an unbounded read, so an oversized upload is detected
    without a second, unbounded in-memory buffer beyond what's needed to
    tell it's too large.
    """
    monkeypatch.setattr(settings, "invitation_max_upload_size_bytes", 10)
    read_sizes: list[int] = []
    # Starlette's multipart parser instantiates its own
    # `starlette.datastructures.UploadFile` (not `fastapi.UploadFile`, a
    # subclass never actually constructed at request-parsing time) — the
    # spy has to patch the base class the real request objects are.
    original_read = starlette_datastructures.UploadFile.read

    async def _spy_read(self, size: int = -1) -> bytes:
        read_sizes.append(size)
        return await original_read(self, size)

    monkeypatch.setattr(starlette_datastructures.UploadFile, "read", _spy_read)

    token = await _login(client, user.email)
    response = await _create_invitation(client, token, branch, payload=_individual_payload())

    assert response.status_code == 422
    # The primary contact's ID-proof file is read first, bounded to the
    # (monkeypatched, tiny) `invitation_max_upload_size_bytes + 1` — the
    # oversized read is detected there and the request is rejected before
    # any visitor file would be read. The now-mandatory primary contact
    # photo file is still read (unconditionally, per
    # require-primary-contact-photo), bounded to its own, unpatched
    # `invitation_max_photo_size_bytes + 1` limit.
    assert read_sizes == [11, settings.invitation_max_photo_size_bytes + 1]


async def test_create_group_invitation_earlier_visitor_file_not_stored_when_later_invalid(
    client: AsyncClient, user: User, branch: Branch, monkeypatch
) -> None:
    """Regression test for the validate-before-persist fix
    (specs/invitations/spec.md "Earlier visitor's file not persisted when a
    later visitor's file is rejected"): a group submission rejected because
    one visitor's file is invalid must not have written any other visitor's
    (or the primary contact's) file to storage first.
    """
    storage_calls: list[str] = []
    original_save = invitations_service.storage_save

    async def _spy_save(tenant_id, category, content, content_type):
        storage_calls.append(content_type)
        return await original_save(tenant_id, category, content, content_type)

    monkeypatch.setattr(invitations_service, "storage_save", _spy_save)

    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    files = [
        ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
        ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
        ("visitor_id_proof_files", ("v0.jpg", _jpeg_bytes(), "image/jpeg")),
        ("visitor_id_proof_files", ("v1.txt", b"not actually an image", "image/jpeg")),
    ]
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(_group_payload())},
        files=files,
        headers=headers,
    )

    assert response.status_code == 422
    assert storage_calls == []


# --- Optional profile photo (checkin-approval-workflow-improvements) --------


async def test_create_invitation_with_primary_contact_photo_succeeds(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """spec.md "Photo supplied and valid is stored and returned"."""
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    files = [
        ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
        ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
    ]
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(_individual_payload())},
        files=files,
        headers=headers,
    )
    assert response.status_code == 201, response.text


async def test_create_invitation_without_primary_contact_photo_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """require-primary-contact-photo spec.md "Missing primary contact photo
    is rejected" — a request that omits `primaryContactPhotoFile` entirely
    is rejected and creates no invitation record.
    """
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(_individual_payload())},
        files=[("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg"))],
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 422


async def test_create_invitation_disguised_photo_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """spec.md "Disguised executable submitted as a photo is rejected" —
    creates no invitation record.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    files = [
        ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
        (
            "primary_contact_photo_file",
            ("selfie.jpg", b"this is not actually an image, just plain text bytes", "image/jpeg"),
        ),
    ]
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(_individual_payload())},
        files=files,
        headers=headers,
    )
    assert response.status_code == 422


async def test_create_invitation_pdf_photo_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A photo must be image-only — unlike ID-proof uploads, a PDF is not an
    acceptable content type for a profile photo, even though it would pass
    the ID-proof allow-list.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    pdf_bytes = b"%PDF-1.4\n%mock pdf content for content-sniffing tests\n"
    files = [
        ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
        ("primary_contact_photo_file", ("id.pdf", pdf_bytes, "application/pdf")),
    ]
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(_individual_payload())},
        files=files,
        headers=headers,
    )
    assert response.status_code == 422


async def test_create_invitation_oversized_photo_rejected(
    client: AsyncClient, user: User, branch: Branch, monkeypatch
) -> None:
    """spec.md "Oversized photo upload is rejected"."""
    monkeypatch.setattr(settings, "invitation_max_photo_size_bytes", 10)
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    files = [
        ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
        ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
    ]
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(_individual_payload())},
        files=files,
        headers=headers,
    )
    assert response.status_code == 422


async def test_create_group_invitation_with_visitor_photos_returns_photo_urls(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """spec.md "Walk-in registration inherits the same optional photo
    capture" is exercised in `registrations/tests.py`; here we confirm a
    group invitation's co-visitor photos are order-matched and returned.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    files = [
        ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
        ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
        ("visitor_id_proof_files", ("v0.jpg", _jpeg_bytes(), "image/jpeg")),
        ("visitor_id_proof_files", ("v1.jpg", _jpeg_bytes(), "image/jpeg")),
        ("visitor_photo_files", ("v0-photo.jpg", _jpeg_bytes(), "image/jpeg")),
    ]
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(_group_payload())},
        files=files,
        headers=headers,
    )
    assert response.status_code == 201, response.text
    invitation_id = response.json()["data"]["id"]

    detail_response = await client.get(f"/api/v1/invitations/{invitation_id}", headers=headers)
    visitors = detail_response.json()["data"]["visitors"]
    assert visitors[0]["photoUrl"] is not None
    assert visitors[1]["photoUrl"] is None


async def test_create_invitation_idempotency_key_replay(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    calls: list[dict] = []
    # No `Company` profile is configured for this test tenant, so creation
    # resolves to `submitted` (awaiting approval) — see
    # `test_create_invitation_auto_approve_*` below for the `approved` path.
    monkeypatch.setattr(tasks.send_tracking_notification, "delay", lambda **kw: calls.append(kw))

    token = await _login(client, user.email)
    idempotency_key = str(uuid.uuid4())

    first = await _create_invitation_success(
        client,
        token,
        branch,
        payload=_group_payload(),
        visitor_file_count=2,
        idempotency_key=idempotency_key,
    )
    second = await _create_invitation_success(
        client,
        token,
        branch,
        payload=_group_payload(),
        visitor_file_count=2,
        idempotency_key=idempotency_key,
    )
    assert first == second

    invitations = await InvitationRepository(db_session).list()
    assert len(invitations) == 1  # not doubled by the replayed request
    assert len(calls) == 1  # confirmation dispatched exactly once


async def test_create_invitation_without_idempotency_key_creates_separately(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    token = await _login(client, user.email)

    first = await _create_invitation_success(client, token, branch, payload=_individual_payload())
    second = await _create_invitation_success(client, token, branch, payload=_individual_payload())
    assert first["trackingId"] != second["trackingId"]

    invitations = await InvitationRepository(db_session).list()
    assert len(invitations) == 2


# --- Group-specific validation -------------------------------------------------


async def test_create_group_invitation_with_empty_visitor_list_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _group_payload()
    payload["visitors"] = []
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_group_invitation_exceeding_former_max_visitors_accepted(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Visitor Info's seeded group is no longer repeatable (`isRepeatable`
    now seeded `False` — see `defaults.py`'s "visitors" group), which is a
    deliberate product decision to retire the group-visitor-count cap
    entirely: `validate_group_instance_count` skips all enforcement for a
    non-repeatable group (`form_builder/validation.py`), so
    `settings.invitation_max_group_visitors` no longer bounds a group
    registration's visitor count at all. This supersedes the old
    `test_create_group_invitation_exceeding_max_visitors_rejected`.
    """
    token = await _login(client, user.email)
    payload = _group_payload()
    payload["visitors"] = [
        {
            "fullName": f"Extra Visitor {i}",
            "email": f"extra.visitor.{i}@example.com",
            "idProofType": "Passport",
        }
        for i in range(settings.invitation_max_group_visitors + 1)
    ]
    data = await _create_invitation_success(
        client,
        token,
        branch,
        payload=payload,
        visitor_file_count=settings.invitation_max_group_visitors + 1,
    )
    assert data["id"]


async def test_create_group_invitation_visitor_file_count_mismatch_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    response = await _create_invitation(
        client, token, branch, payload=_group_payload(), visitor_file_count=1
    )
    assert response.status_code == 422


async def test_create_group_invitation_visitor_without_contact_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _group_payload()
    payload["visitors"][0].pop("email")
    response = await _create_invitation(
        client, token, branch, payload=payload, visitor_file_count=2
    )
    assert response.status_code == 422


# --- Individual-specific validation --------------------------------------------


async def test_create_individual_invitation_with_visitors_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitors"] = [
        {"fullName": "Extra Person", "email": "extra@example.com", "idProofType": "Passport"}
    ]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


# --- General field validation --------------------------------------------------


@pytest.mark.parametrize("missing_field", ["registrationType", "primaryContact", "visitDetails"])
async def test_create_invitation_missing_required_top_level_field_rejected(
    client: AsyncClient, user: User, branch: Branch, missing_field: str
) -> None:
    token = await _login(client, user.email)
    payload = _individual_payload()
    del payload[missing_field]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_invalid_id_proof_type_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["primaryContact"]["idProofType"] = "Not A Real Document"
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_invalid_vehicle_type_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["vehicles"] = [{"vehicleType": "spaceship", "licensePlate": "KA-01-AB-1234"}]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_admin_added_id_proof_type_option_accepted(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """make-id-proof-and-vehicle-type-configurable: an ID proof type is no
    longer a fixed enum — a value the admin has added to the branch's "ID
    Proof Type" options is accepted, even though it isn't one of the
    original four defaults."""
    token = await _login(client, user.email)
    await _update_and_publish_field_options(
        client,
        token,
        branch,
        step_key="visitor_info",
        field_key="id_proof_type",
        options=["Aadhaar Card", "Passport", "Driving License", "Other", "Voter ID"],
    )

    payload = _individual_payload()
    payload["primaryContact"]["idProofType"] = "Voter ID"
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]


async def test_create_invitation_admin_added_vehicle_type_option_accepted(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    await _update_and_publish_field_options(
        client,
        token,
        branch,
        step_key="vehicle_info",
        field_key="vehicle_type",
        options=["2_wheeler", "4_wheeler", "heavy", "tricycle"],
    )

    payload = _individual_payload()
    payload["vehicles"] = [{"vehicleType": "tricycle", "licensePlate": "KA-01-AB-1234"}]
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]


async def test_create_invitation_default_id_proof_and_vehicle_types_still_accepted(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A branch that has never customized "ID Proof Type"/"Vehicle Type"
    still accepts every one of the original default options — confirms the
    dynamic-validation switch is behavior-preserving for the common case."""
    token = await _login(client, user.email)
    payload = _group_payload()
    payload["primaryContact"]["idProofType"] = "Aadhaar Card"
    payload["visitors"][0]["idProofType"] = "Passport"
    payload["visitors"][1]["idProofType"] = "Driving License"
    payload["vehicles"] = [
        {"vehicleType": "2_wheeler", "licensePlate": "KA-01-AB-1234"},
        {"vehicleType": "4_wheeler", "licensePlate": "KA-05-CD-5678"},
        {"vehicleType": "heavy", "licensePlate": "KA-09-EF-9012"},
    ]
    data = await _create_invitation_success(
        client, token, branch, payload=payload, visitor_file_count=2
    )
    assert data["id"]


# --- add-repeatable-field-groups: group instance-count enforcement ----------


async def _update_and_publish_group_range(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    step_key: str,
    group_key: str,
    min_instances: int | None = None,
    max_instances: int | None = None,
) -> dict:
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == step_key)
    group = next(g for g in step["groups"] if g["key"] == group_key)

    body: dict[str, Any] = {}
    if min_instances is not None:
        body["minInstances"] = min_instances
    if max_instances is not None:
        body["maxInstances"] = max_instances
    update_response = await client.patch(
        f"/api/v1/form-builder/groups/{group['id']}", json=body, headers=headers
    )
    assert update_response.status_code == 200, update_response.text

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])
    return update_response.json()["data"]


async def _create_and_publish_custom_group(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    step_key: str,
    group_key: str,
    field_key: str,
    min_instances: int | None = None,
    max_instances: int | None = None,
    field_type: str = "text",
    is_required: bool = False,
    options: list[str] | None = None,
    visibility_condition: dict[str, Any] | None = None,
) -> dict:
    """Admin-side setup: creates a repeatable field group with one field on
    `step_key` and publishes the branch's scope so `create_invitation`
    reads it. `visibility_condition`, if supplied, is applied to the group
    itself after creation (add-repeatable-field-groups) — its `fieldKey`
    must reference an existing field on the same step other than this
    group's own.
    """
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == step_key)

    group_body: dict[str, Any] = {"key": group_key, "name": group_key.title(), "isRepeatable": True}
    if min_instances is not None:
        group_body["minInstances"] = min_instances
    if max_instances is not None:
        group_body["maxInstances"] = max_instances
    group_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/groups", json=group_body, headers=headers
    )
    assert group_response.status_code == 201, group_response.text
    group = group_response.json()["data"]

    field_body: dict[str, Any] = {
        "key": field_key,
        "label": field_key.replace("_", " ").title(),
        "fieldType": field_type,
        "isRequired": is_required,
        "groupId": group["id"],
    }
    if options is not None:
        field_body["options"] = options
    field_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields", json=field_body, headers=headers
    )
    assert field_response.status_code == 201, field_response.text
    # Test-only, not a real API response field (restructure-walkin-payload-
    # by-field-id) — every group this helper builds has exactly one field,
    # so `_group_entry` below can look its id up here rather than every
    # call site threading it through separately.
    field_id = field_response.json()["data"]["id"]

    if visibility_condition is not None:
        condition_response = await client.patch(
            f"/api/v1/form-builder/groups/{group['id']}",
            json={"visibilityCondition": visibility_condition},
            headers=headers,
        )
        assert condition_response.status_code == 200, condition_response.text
        group = condition_response.json()["data"]

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])
    group["_field_id"] = field_id
    return group


def _group_entry(group: dict, instances: list[dict[str, Any]]) -> dict:
    """Builds one `payload["groups"]` entry from a `_create_and_publish_
    custom_group` group dict and a list of `{fieldKey: value}` instance
    dicts (test-authoring convenience, since every group this test module
    builds has exactly one field) — converts each instance to the
    `{fieldId, value}` array shape (restructure-walkin-payload-by-field-id).
    """
    field_id = group["_field_id"]
    return {
        "groupId": group["id"],
        "instances": [
            [{"fieldId": field_id, "value": v} for v in instance.values()] for instance in instances
        ],
    }


async def test_create_invitation_vehicle_count_below_configured_minimum_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    await _update_and_publish_group_range(
        client, token, branch, step_key="vehicle_info", group_key="vehicles", min_instances=1
    )
    payload = _individual_payload()
    payload["vehicles"] = []
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_vehicle_count_above_configured_maximum_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    await _update_and_publish_group_range(
        client, token, branch, step_key="vehicle_info", group_key="vehicles", max_instances=1
    )
    payload = _individual_payload()
    payload["vehicles"] = [
        {"vehicleType": "2_wheeler", "licensePlate": "KA-01-AB-1234"},
        {"vehicleType": "4_wheeler", "licensePlate": "KA-05-CD-5678"},
    ]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_vehicle_count_within_configured_range_accepted(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    await _update_and_publish_group_range(
        client,
        token,
        branch,
        step_key="vehicle_info",
        group_key="vehicles",
        min_instances=1,
        max_instances=3,
    )
    payload = _individual_payload()
    payload["vehicles"] = [{"vehicleType": "2_wheeler", "licensePlate": "KA-01-AB-1234"}]
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]


async def test_create_invitation_custom_group_instances_within_range_persisted(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    token = await _login(client, user.email)
    group = await _create_and_publish_custom_group(
        client,
        token,
        branch,
        step_key="carried_items",
        group_key="parcels",
        field_key="parcel_weight",
        min_instances=1,
        max_instances=3,
    )
    payload = _individual_payload()
    payload["groups"] = [_group_entry(group, [{"parcel_weight": "2kg"}, {"parcel_weight": "5kg"}])]
    data = await _create_invitation_success(client, token, branch, payload=payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    field_id = group["_field_id"]
    assert invitation.group_field_values == {group["id"]: [{field_id: "2kg"}, {field_id: "5kg"}]}


async def test_create_invitation_custom_group_below_minimum_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    group = await _create_and_publish_custom_group(
        client,
        token,
        branch,
        step_key="carried_items",
        group_key="parcels",
        field_key="parcel_weight",
        min_instances=1,
    )
    payload = _individual_payload()
    payload["groups"] = [_group_entry(group, [])]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_custom_group_above_maximum_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    group = await _create_and_publish_custom_group(
        client,
        token,
        branch,
        step_key="carried_items",
        group_key="parcels",
        field_key="parcel_weight",
        max_instances=1,
    )
    payload = _individual_payload()
    payload["groups"] = [_group_entry(group, [{"parcel_weight": "2kg"}, {"parcel_weight": "5kg"}])]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_unknown_group_key_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["groups"] = [
        {
            "groupId": str(uuid.uuid4()),
            "instances": [[{"fieldId": str(uuid.uuid4()), "value": "bar"}]],
        }
    ]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_one_invalid_group_instance_rejects_whole_request(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    token = await _login(client, user.email)
    group = await _create_and_publish_custom_group(
        client,
        token,
        branch,
        step_key="carried_items",
        group_key="parcels",
        field_key="parcel_weight",
        is_required=True,
    )
    payload = _individual_payload()
    # second instance missing required field
    payload["groups"] = [
        {
            "groupId": group["id"],
            "instances": [[{"fieldId": group["_field_id"], "value": "2kg"}], []],
        }
    ]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422

    invitations = await InvitationRepository(db_session).list_by_primary_contact_email(
        payload["primaryContact"]["email"]
    )
    assert invitations == []


# --- add-repeatable-field-groups (revised): hidden custom group skips ------
# required-field validation ---------------------------------------------------


async def test_create_invitation_hidden_group_required_field_not_required(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """specs/invitations/spec.md (delta) "A Hidden Custom Field Group's
    Fields Are Not Required At Submission" — the group's condition watches
    Carried Items' own seeded `itemDescription` field; leaving it at its
    default (not "trigger") hides the group, so its required field can be
    omitted.
    """
    token = await _login(client, user.email)
    group = await _create_and_publish_custom_group(
        client,
        token,
        branch,
        step_key="carried_items",
        group_key="conditional_parcels",
        field_key="parcel_weight",
        is_required=True,
        visibility_condition={
            "fieldKey": "item_description",
            "operator": "equals",
            "value": "trigger",
        },
    )
    payload = _individual_payload()
    payload["carriedItems"] = {"items": [], "itemDescription": "not the trigger value"}
    payload["groups"] = [_group_entry(group, [{}])]
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]


async def test_create_invitation_visible_group_required_field_still_required(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    group = await _create_and_publish_custom_group(
        client,
        token,
        branch,
        step_key="carried_items",
        group_key="conditional_parcels",
        field_key="parcel_weight",
        is_required=True,
        visibility_condition={
            "fieldKey": "item_description",
            "operator": "equals",
            "value": "trigger",
        },
    )
    payload = _individual_payload()
    payload["carriedItems"] = {"items": [], "itemDescription": "trigger"}
    payload["groups"] = [_group_entry(group, [{}])]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_hidden_group_supplied_value_still_validated(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A hidden group's field isn't required, but a value supplied anyway
    is still validated against its own type/options rules."""
    token = await _login(client, user.email)
    group = await _create_and_publish_custom_group(
        client,
        token,
        branch,
        step_key="carried_items",
        group_key="conditional_parcels",
        field_key="parcel_weight",
        field_type="dropdown_select",
        options=["light", "heavy"],
        visibility_condition={
            "fieldKey": "item_description",
            "operator": "equals",
            "value": "trigger",
        },
    )
    payload = _individual_payload()
    payload["carriedItems"] = {"items": [], "itemDescription": "not the trigger value"}
    payload["groups"] = [_group_entry(group, [{"parcel_weight": "not_a_real_option"}])]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_hidden_group_instance_minimum_not_enforced(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A hidden group's configured minimum instance count can't be met by
    a visitor who was never shown it (specs/invitations/spec.md delta)."""
    token = await _login(client, user.email)
    group = await _create_and_publish_custom_group(
        client,
        token,
        branch,
        step_key="carried_items",
        group_key="conditional_parcels",
        field_key="parcel_weight",
        min_instances=1,
        visibility_condition={
            "fieldKey": "item_description",
            "operator": "equals",
            "value": "trigger",
        },
    )
    payload = _individual_payload()
    payload["carriedItems"] = {"items": [], "itemDescription": "not the trigger value"}
    payload["groups"] = [_group_entry(group, [])]
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]


async def test_create_invitation_hidden_visitor_info_group_required_field_not_required(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Same rule as above (`test_create_invitation_hidden_group_required_field_not_required`)
    but for a custom group defined directly on Visitor Info — unlike a
    field simply assigned to that step, a *grouped* field on Visitor
    Info/Vehicle Info is now excluded from the flat per-visitor
    `customFieldValues` check entirely and validated only through
    `groupValues`, the same as every other admin-defined group
    (`custom_groups_for_invitation_scope`). Regression test: the group's
    condition watches `registration_type`, so an individual registration
    never shows it and mustn't be blocked on its required field, whether or
    not the client even sends a `groupValues` entry for it.
    """
    token = await _login(client, user.email)
    await _create_and_publish_custom_group(
        client,
        token,
        branch,
        step_key="visitor_info",
        group_key="additional_visitors",
        field_key="name",
        is_required=True,
        visibility_condition={
            "fieldKey": "registration_type",
            "operator": "equals",
            "value": "group",
        },
    )
    payload = _individual_payload()
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]


async def test_create_invitation_visible_visitor_info_group_required_field_still_required(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """The same Visitor Info group's required field is still enforced for
    a registration type that does show it, once an instance is actually
    submitted via `groupValues`."""
    token = await _login(client, user.email)
    group = await _create_and_publish_custom_group(
        client,
        token,
        branch,
        step_key="visitor_info",
        group_key="additional_visitors",
        field_key="name",
        is_required=True,
        visibility_condition={
            "fieldKey": "registration_type",
            "operator": "equals",
            "value": "group",
        },
    )
    payload = _group_payload()
    payload["groups"] = [_group_entry(group, [{}])]
    response = await _create_invitation(
        client, token, branch, payload=payload, visitor_file_count=2
    )
    assert response.status_code == 422


async def test_create_invitation_group_registration_via_visitor_info_custom_group_accepted(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Regression test for the "Group registration must list at least one
    visitor" bug: a branch that collects additional visitors through an
    admin-defined repeatable group on Visitor Info (rather than the fixed
    `visitors` list — the built-in "Visitors" system group is no longer
    admin-configurable, `form_builder/defaults.py`) can submit a group
    registration with `visitors: []` and its visitor data in `groupValues`
    instead, and it's accepted end to end: the structural "at least one
    visitor" check accepts a non-empty `groupValues` entry
    (`invitations/schemas.py`), and the group's own required field is
    validated per submitted instance.
    """
    token = await _login(client, user.email)
    group = await _create_and_publish_custom_group(
        client,
        token,
        branch,
        step_key="visitor_info",
        group_key="additional_visitors",
        field_key="name",
        is_required=True,
    )
    payload = _group_payload()
    payload["visitors"] = []
    payload["groups"] = [_group_entry(group, [{"name": "Extra One"}, {"name": "Extra Two"}])]
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]


async def test_get_invitation_detail_surfaces_visitor_info_group_visitors(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Regression test for "GET /invitations/:id doesn't reflect visitors
    collected via a custom field group": `visitors` in the detail response
    must include a synthesized entry per instance of a Visitor Info group's
    submitted `groups` entry, not just the legacy `visitors` relation (which
    stays empty when a branch collects extras this way instead)."""
    token = await _login(client, user.email)
    group = await _create_and_publish_custom_group(
        client,
        token,
        branch,
        step_key="visitor_info",
        group_key="additional_visitors",
        field_key="name",
        is_required=True,
    )
    payload = _group_payload()
    payload["visitors"] = []
    payload["groups"] = [_group_entry(group, [{"name": "Extra One"}, {"name": "Extra Two"}])]
    data = await _create_invitation_success(client, token, branch, payload=payload)

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert detail_response.status_code == 200, detail_response.text
    body = detail_response.json()["data"]
    field_id = group["_field_id"]
    assert body["groups"] == [
        {
            "groupId": group["id"],
            "instances": [
                [{"fieldId": field_id, "value": "Extra One"}],
                [{"fieldId": field_id, "value": "Extra Two"}],
            ],
        }
    ]
    names = sorted(v["fullName"] for v in body["visitors"])
    assert names == ["Extra One", "Extra Two"]
    for visitor_out in body["visitors"]:
        assert visitor_out["idProofType"] is None
        assert visitor_out["email"] is None


async def test_get_invitation_detail_group_visitor_email_and_phone_mapped_by_field_type(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Follow-up regression test: once a Visitor Info group has its own
    `email`/`phone`-typed fields alongside its name field, the synthesized
    visitor entry picks those values up too, not just `fullName` — matched
    by Form Builder's `fieldType`, since there's no other reliable signal
    for which of an admin's arbitrary field keys means what.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == "visitor_info")

    group_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/groups",
        json={"key": "additional_visitors", "name": "Additional Visitors", "isRepeatable": True},
        headers=headers,
    )
    assert group_response.status_code == 201, group_response.text
    group = group_response.json()["data"]

    field_ids: dict[str, str] = {}
    for field_key, field_type in (
        ("name", "text"),
        ("email_address", "email"),
        ("contact_number", "phone"),
    ):
        field_response = await client.post(
            f"/api/v1/form-builder/steps/{step['id']}/fields",
            json={
                "key": field_key,
                "label": field_key.replace("_", " ").title(),
                "fieldType": field_type,
                "isRequired": False,
                "groupId": group["id"],
            },
            headers=headers,
        )
        assert field_response.status_code == 201, field_response.text
        field_ids[field_key] = field_response.json()["data"]["id"]

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])

    payload = _group_payload()
    payload["visitors"] = []
    payload["groups"] = [
        {
            "groupId": group["id"],
            "instances": [
                [
                    {"fieldId": field_ids["name"], "value": "Extra One"},
                    {"fieldId": field_ids["email_address"], "value": "extra.one@example.com"},
                    {"fieldId": field_ids["contact_number"], "value": "+1 555 000 1111"},
                ]
            ],
        }
    ]
    data = await _create_invitation_success(client, token, branch, payload=payload)

    detail_response = await client.get(f"/api/v1/invitations/{data['id']}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    [visitor_out] = detail_response.json()["data"]["visitors"]
    assert visitor_out["fullName"] == "Extra One"
    assert visitor_out["email"] == "extra.one@example.com"
    assert visitor_out["phone"] == "+1 555 000 1111"
    assert visitor_out["idProofType"] is None
    assert visitor_out["idProofUrl"] is None


# --- add-group-field-file-upload: a custom group's own file_upload field ----


async def _create_and_publish_additional_visitors_group(
    client: AsyncClient, headers: dict[str, str], *, id_upload_required: bool
) -> dict:
    """Admin-side setup shared by the `groupFieldFiles` tests below: a
    repeatable "Additional Visitors" group on Visitor Info with a required
    `name` field and its own `file_upload`-typed field (`id_upload`).
    Returns the group dict augmented with `_field_ids` (a `{key: id}` map
    — restructure-walkin-payload-by-field-id) so callers can build
    `payload.groups`/`groupFieldFiles[<groupId>]` without a second lookup.
    """
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == "visitor_info")

    group_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/groups",
        json={"key": "additional_visitors", "name": "Additional Visitors", "isRepeatable": True},
        headers=headers,
    )
    assert group_response.status_code == 201, group_response.text
    group = group_response.json()["data"]

    field_ids: dict[str, str] = {}
    for field_key, field_type, is_required in (
        ("name", "text", True),
        ("id_upload", "file_upload", id_upload_required),
    ):
        field_response = await client.post(
            f"/api/v1/form-builder/steps/{step['id']}/fields",
            json={
                "key": field_key,
                "label": field_key.replace("_", " ").title(),
                "fieldType": field_type,
                "isRequired": is_required,
                "groupId": group["id"],
            },
            headers=headers,
        )
        assert field_response.status_code == 201, field_response.text
        field_ids[field_key] = field_response.json()["data"]["id"]

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])
    group["_field_ids"] = field_ids
    return group


async def test_create_invitation_group_file_upload_stored_and_surfaced_on_read(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A custom Visitor Info group's own `file_upload`-typed field is
    accepted via the `groupFieldFiles[<groupKey>]` multipart convention
    (order-matched to `groupValues[<groupKey>]` instances), stored, and
    resolved back to `idProofUrl` on `GET /invitations/:id` — matching the
    fixed `visitors[].idProofUrl` behavior for the same caller permission
    (`documents:view`, held by the `user` fixture).
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    group = await _create_and_publish_additional_visitors_group(
        client, headers, id_upload_required=False
    )
    name_field_id = group["_field_ids"]["name"]

    payload = _group_payload()
    payload["visitors"] = []
    payload["groups"] = [
        {
            "groupId": group["id"],
            "instances": [
                [{"fieldId": name_field_id, "value": "Extra One"}],
                [{"fieldId": name_field_id, "value": "Extra Two"}],
            ],
        }
    ]
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(payload)},
        files=[
            ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
            (f"groupFieldFiles[{group['id']}]", ("extra1.jpg", _jpeg_bytes(), "image/jpeg")),
            (f"groupFieldFiles[{group['id']}]", ("extra2.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
        headers=headers,
    )
    assert response.status_code == 201, response.text
    invitation_id = response.json()["data"]["id"]

    detail_response = await client.get(f"/api/v1/invitations/{invitation_id}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    visitors = sorted(detail_response.json()["data"]["visitors"], key=lambda v: v["fullName"])
    assert [v["fullName"] for v in visitors] == ["Extra One", "Extra Two"]
    for visitor_out in visitors:
        assert visitor_out["idProofUrl"] is not None


async def test_get_invitation_detail_non_string_group_file_field_value_resolves_to_null(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """Regression: a group's `file_upload`-typed field key (`id_upload`) is
    resolved against the branch's *current* effective form, not the form as
    it stood when this instance's data was written. If a field was ever
    reused/retyped so an older instance holds a non-string value under that
    key (bool/number/list/dict rather than a storage key), both
    `_resolve_custom_field_file_values` (feeding `groupFieldValues`) and
    `_group_collected_visitor_detail_outs` (feeding the synthesized
    visitor's `idProofUrl`) used to call `storage_url_for` -> `quote()`
    unconditionally, which raises `TypeError: quote_from_bytes() expected
    bytes` for anything that isn't `str`/`bytes` and 500s the whole detail
    endpoint. Both must instead treat a non-string value as "no file".
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    group = await _create_and_publish_additional_visitors_group(
        client, headers, id_upload_required=False
    )
    name_field_id = group["_field_ids"]["name"]
    id_upload_field_id = group["_field_ids"]["id_upload"]

    invitation = _build_invitation(
        db_session,
        branch.id,
        group_field_values={group["id"]: [{name_field_id: "Extra One", id_upload_field_id: True}]},
    )
    db_session.add(invitation)
    await db_session.commit()

    detail_response = await client.get(f"/api/v1/invitations/{invitation.id}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    body = detail_response.json()["data"]
    [group_out] = body["groups"]
    [instance] = group_out["instances"]
    assert _custom_field_value(instance, id_upload_field_id) is None
    [visitor_out] = [v for v in body["visitors"] if v["fullName"] == "Extra One"]
    assert visitor_out["idProofUrl"] is None


async def test_create_invitation_group_file_upload_required_missing_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A group's `file_upload` field marked required rejects a submission
    that doesn't upload a matching file for every instance — the group
    counterpart of the fixed `visitors` list's own ID-proof-count check.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    group = await _create_and_publish_additional_visitors_group(
        client, headers, id_upload_required=True
    )
    name_field_id = group["_field_ids"]["name"]

    payload = _group_payload()
    payload["visitors"] = []
    payload["groups"] = [
        {"groupId": group["id"], "instances": [[{"fieldId": name_field_id, "value": "Extra One"}]]}
    ]
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(payload)},
        files=[
            ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
        headers=headers,
    )
    assert response.status_code == 422, response.text


async def test_create_invitation_group_file_upload_extra_files_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """More `groupFieldFiles[<groupId>]` files than submitted instances is
    rejected, same as an over-long `visitorIdProofFiles` list."""
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    group = await _create_and_publish_additional_visitors_group(
        client, headers, id_upload_required=False
    )
    name_field_id = group["_field_ids"]["name"]

    payload = _group_payload()
    payload["visitors"] = []
    payload["groups"] = [
        {"groupId": group["id"], "instances": [[{"fieldId": name_field_id, "value": "Extra One"}]]}
    ]
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(payload)},
        files=[
            ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
            (f"groupFieldFiles[{group['id']}]", ("extra1.jpg", _jpeg_bytes(), "image/jpeg")),
            (f"groupFieldFiles[{group['id']}]", ("extra2.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
        headers=headers,
    )
    assert response.status_code == 422, response.text


async def test_create_invitation_group_file_upload_json_value_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A client-supplied JSON value for a group's `file_upload` field is
    rejected outright rather than silently ignored — the file is the only
    valid source of that field's answer (`service.py::_group_field_file_id`).
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    group = await _create_and_publish_additional_visitors_group(
        client, headers, id_upload_required=False
    )
    name_field_id = group["_field_ids"]["name"]
    id_upload_field_id = group["_field_ids"]["id_upload"]

    payload = _group_payload()
    payload["visitors"] = []
    payload["groups"] = [
        {
            "groupId": group["id"],
            "instances": [
                [
                    {"fieldId": name_field_id, "value": "Extra One"},
                    {"fieldId": id_upload_field_id, "value": "not-a-file"},
                ]
            ],
        }
    ]
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(payload)},
        files=[
            ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
        headers=headers,
    )
    assert response.status_code == 422, response.text


async def test_create_invitation_inline_custom_field_file_upload_stored_on_read(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """An admin-authored `file_upload` field directly on Visitor Info (not
    assigned to a group) is accepted via the `primaryContactCustomFieldFiles
    [<fieldId>]`/`visitorCustomFieldFiles[<fieldId>]` multipart
    convention and stored — the standalone counterpart of
    `groupFieldFiles[<groupId>]` above (add-inline-custom-field-file-upload).
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="visitor_info", key="pic", field_type="file_upload"
    )
    field_id = field["id"]

    payload = _group_payload()
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(payload)},
        files=[
            ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
            ("visitor_id_proof_files", ("v0.jpg", _jpeg_bytes(), "image/jpeg")),
            ("visitor_id_proof_files", ("v1.jpg", _jpeg_bytes(), "image/jpeg")),
            (
                f"primaryContactCustomFieldFiles[{field_id}]",
                ("primary-pic.jpg", _jpeg_bytes(), "image/jpeg"),
            ),
            (f"visitorCustomFieldFiles[{field_id}]", ("v0-pic.jpg", _jpeg_bytes(), "image/jpeg")),
            (f"visitorCustomFieldFiles[{field_id}]", ("v1-pic.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
        headers=headers,
    )
    assert response.status_code == 201, response.text
    invitation_id = response.json()["data"]["id"]

    detail_response = await client.get(f"/api/v1/invitations/{invitation_id}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    body = detail_response.json()["data"]

    def _assert_resolved_file_url(value: str) -> None:
        # Must be a signed, fetchable URL — not the raw `vmss:...` storage
        # key a pre-fix reader would have serialized verbatim.
        assert value
        assert not value.startswith("vmss:")
        assert "/api/v1/files/" in value or value.startswith("http")

    _assert_resolved_file_url(_custom_field_value(body["customFields"], field_id))
    for visitor_out in body["visitors"]:
        _assert_resolved_file_url(_custom_field_value(visitor_out["customFields"], field_id))


async def test_create_invitation_vehicle_custom_field_file_upload_resolved_on_read(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Regression: vehicle-level `file_upload` custom-field answers must
    resolve to a signed URL on `GET /invitations/:id` the same as the
    identical visitor/primary-contact/invitation/group paths — previously
    `_to_invitation_detail_out`'s vehicle construction passed
    `v.custom_field_values` straight through unresolved, leaking the raw
    `vmss:...` storage key.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    field = await _create_and_publish_custom_field(
        client,
        token,
        branch,
        step_key="vehicle_info",
        key="registration_doc",
        field_type="file_upload",
    )
    field_id = field["id"]

    payload = _group_payload()
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(payload)},
        files=[
            ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
            ("visitor_id_proof_files", ("v0.jpg", _jpeg_bytes(), "image/jpeg")),
            ("visitor_id_proof_files", ("v1.jpg", _jpeg_bytes(), "image/jpeg")),
            (
                f"vehicleCustomFieldFiles[{field_id}]",
                ("v0-doc.jpg", _jpeg_bytes(), "image/jpeg"),
            ),
            (
                f"vehicleCustomFieldFiles[{field_id}]",
                ("v1-doc.jpg", _jpeg_bytes(), "image/jpeg"),
            ),
        ],
        headers=headers,
    )
    assert response.status_code == 201, response.text
    invitation_id = response.json()["data"]["id"]

    detail_response = await client.get(f"/api/v1/invitations/{invitation_id}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    vehicles = detail_response.json()["data"]["vehicles"]
    for vehicle_out in vehicles:
        value = _custom_field_value(vehicle_out["customFields"], field_id)
        assert value
        assert not value.startswith("vmss:")
        assert "/api/v1/files/" in value or value.startswith("http")


async def test_create_invitation_inline_custom_field_file_upload_required_missing_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A required, ungrouped `file_upload` field on Visitor Info rejects a
    submission missing a file for any visitor — the standalone counterpart
    of `test_create_invitation_group_file_upload_required_missing_rejected`.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    field = await _create_and_publish_custom_field(
        client,
        token,
        branch,
        step_key="visitor_info",
        key="pic",
        field_type="file_upload",
        is_required=True,
    )
    field_id = field["id"]

    payload = _group_payload()
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(payload)},
        files=[
            ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
            ("visitor_id_proof_files", ("v0.jpg", _jpeg_bytes(), "image/jpeg")),
            ("visitor_id_proof_files", ("v1.jpg", _jpeg_bytes(), "image/jpeg")),
            (
                f"primaryContactCustomFieldFiles[{field_id}]",
                ("primary-pic.jpg", _jpeg_bytes(), "image/jpeg"),
            ),
            # Only one of the two visitors' required files supplied.
            (f"visitorCustomFieldFiles[{field_id}]", ("v0-pic.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
        headers=headers,
    )
    assert response.status_code == 422, response.text


async def test_create_invitation_inline_custom_field_file_upload_json_value_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A client-supplied JSON value for an ungrouped `file_upload` field is
    rejected outright rather than silently ignored — the file is the only
    valid source of that field's answer, same rule as a group's own
    `file_upload` field.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="visitor_info", key="pic", field_type="file_upload"
    )

    payload = _individual_payload()
    payload["customFields"] = [{"fieldId": field["id"], "value": "not-a-file"}]
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(payload)},
        files=[
            ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
        headers=headers,
    )
    assert response.status_code == 422, response.text


async def test_create_invitation_inline_invitation_level_custom_field_file_upload_stored(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """The invitation-level (Visit Details/Carried Items/custom step)
    counterpart — a single file via `customFieldFiles[<fieldKey>]`, no
    per-visitor/vehicle order-matching involved.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="visit_details", key="cost_note", field_type="file_upload"
    )
    field_id = field["id"]

    payload = _individual_payload()
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(payload)},
        files=[
            ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
            (f"customFieldFiles[{field_id}]", ("note.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
        headers=headers,
    )
    assert response.status_code == 201, response.text
    invitation_id = response.json()["data"]["id"]

    detail_response = await client.get(f"/api/v1/invitations/{invitation_id}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    assert _custom_field_value(detail_response.json()["data"]["customFields"], field_id)


async def test_get_invitation_detail_group_visitor_id_proof_url_omitted_without_documents_view(
    client: AsyncClient,
    user: User,
    branch: Branch,
    tenant: Tenant,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """Counterpart of the happy-path test above — a caller holding
    `invitations:view` but not `documents:view` sees `idProofUrl` `null`
    for a group-collected visitor too, matching `_to_visitor_detail_outs`'s
    existing gating for the fixed `visitors` list.
    """
    admin_token = await _login(client, user.email)
    admin_headers = {"Authorization": f"Bearer {admin_token}", "X-Branch-ID": str(branch.id)}
    group = await _create_and_publish_additional_visitors_group(
        client, admin_headers, id_upload_required=False
    )
    name_field_id = group["_field_ids"]["name"]

    payload = _group_payload()
    payload["visitors"] = []
    payload["groups"] = [
        {"groupId": group["id"], "instances": [[{"fieldId": name_field_id, "value": "Extra One"}]]}
    ]
    create_response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(payload)},
        files=[
            ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
            (f"groupFieldFiles[{group['id']}]", ("extra1.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
        headers=admin_headers,
    )
    assert create_response.status_code == 201, create_response.text
    invitation_id = create_response.json()["data"]["id"]

    # Not `_branch_scoped_invitation_viewer(db_session, tenant, branch.id)`:
    # that helper creates its own `Permission(code="invitations:view")` row,
    # which collides with the one the `user` fixture above already created
    # (global `permissions.code` is unique) — reuses that existing row
    # instead of inserting a duplicate.
    existing_permissions = list(
        (
            await db_session.execute(
                select(Permission).where(
                    Permission.code.in_(("invitations:view", "invitations:view-all"))
                )
            )
        ).scalars()
    )
    viewer_role = RoleFactory.build(
        id=uuid.uuid4(), name="invitations-viewer-no-documents", permissions=existing_permissions
    )
    viewer_branch_role = UserBranchRole(id=uuid.uuid4(), role=viewer_role, branch_id=branch.id)
    viewer = UserFactory.build(
        id=uuid.uuid4(),
        email=f"viewer-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Invitation Viewer",
        branch_roles=[viewer_branch_role],
    )
    db_session.add_all([viewer_role, viewer])
    await db_session.flush()
    db_session.add(TenantUserIndex(email=viewer.email, tenant_id=tenant.id, user_id=viewer.id))
    await db_session.commit()

    viewer_token = issue_token(viewer)
    detail_response = await client.get(
        f"/api/v1/invitations/{invitation_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert detail_response.status_code == 200, detail_response.text
    [visitor_out] = detail_response.json()["data"]["visitors"]
    assert visitor_out["fullName"] == "Extra One"
    assert visitor_out["idProofUrl"] is None


async def test_get_invitation_detail_includes_primary_contact_email_and_phone(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Regression test: `primaryContactEmail`/`primaryContactPhone` were
    captured at submission but never returned by `GET /invitations/:id`."""
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["primaryContact"]["phone"] = "+91 90000 00000"
    data = await _create_invitation_success(client, token, branch, payload=payload)

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert detail_response.status_code == 200, detail_response.text
    body = detail_response.json()["data"]
    assert body["primaryContactEmail"] == payload["primaryContact"]["email"]
    assert body["primaryContactPhone"] == payload["primaryContact"]["phone"]


async def test_create_invitation_retyped_system_field_matching_option_accepted(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """make-system-field-types-editable: once an admin retypes "Purpose of
    Visit" to `dropdown_select` with configured options, a submission
    matching one of those options is accepted."""
    token = await _login(client, user.email)
    await _update_and_publish_field_options(
        client,
        token,
        branch,
        step_key="visit_details",
        field_key="purpose_of_visit",
        field_type="dropdown_select",
        options=["Meeting", "Delivery", "Interview"],
    )

    payload = _individual_payload()
    payload["visitDetails"]["purposeOfVisit"] = "Meeting"
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]


async def test_create_invitation_retyped_system_field_non_matching_option_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """make-system-field-types-editable: the same retyped field rejects a
    submission that doesn't match any of its currently configured
    options, mirroring the existing `idProofType`/`vehicleType`
    unknown-option rejection."""
    token = await _login(client, user.email)
    await _update_and_publish_field_options(
        client,
        token,
        branch,
        step_key="visit_details",
        field_key="purpose_of_visit",
        field_type="dropdown_select",
        options=["Meeting", "Delivery", "Interview"],
    )

    payload = _individual_payload()
    payload["visitDetails"]["purposeOfVisit"] = "Sightseeing"
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_retyped_radio_button_field_matching_option_accepted(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """update-form-field-type-catalog: `radio_button` is validated at
    submission the same way `dropdown_select` is — a value matching one
    of the field's configured options is accepted."""
    token = await _login(client, user.email)
    await _update_and_publish_field_options(
        client,
        token,
        branch,
        step_key="visit_details",
        field_key="purpose_of_visit",
        field_type="radio_button",
        options=["Meeting", "Delivery", "Interview"],
    )

    payload = _individual_payload()
    payload["visitDetails"]["purposeOfVisit"] = "Meeting"
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]


async def test_create_invitation_retyped_radio_button_field_non_matching_option_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """update-form-field-type-catalog: the same retyped `radio_button`
    field rejects a submission that doesn't match any of its currently
    configured options, mirroring `dropdown_select`'s unknown-option
    rejection."""
    token = await _login(client, user.email)
    await _update_and_publish_field_options(
        client,
        token,
        branch,
        step_key="visit_details",
        field_key="purpose_of_visit",
        field_type="radio_button",
        options=["Meeting", "Delivery", "Interview"],
    )

    payload = _individual_payload()
    payload["visitDetails"]["purposeOfVisit"] = "Sightseeing"
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_system_field_still_default_type_accepts_free_text(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """make-system-field-types-editable: a system field left at its
    default (non-option-bearing) type is validated as ordinary free text,
    unaffected by this change — any non-empty string within the existing
    length limit is accepted."""
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["purposeOfVisit"] = "Sightseeing and general curiosity"
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]


async def test_create_invitation_invalid_carried_item_category_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["carriedItems"] = {"items": ["nuclear_launch_codes"]}
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_unknown_consent_key_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """specs/invitations/spec.md (delta) "Consent Is Mandatory and
    Recorded" — a `consents` fieldId outside the calling branch's configured
    Consent Agreement set is rejected, mirroring the carried-items allow-list
    check above.
    """
    token = await _login(client, user.email)
    payload = _individual_payload()
    _add_consent(payload, str(uuid.uuid4()), True)
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_vehicle_missing_license_plate_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["vehicles"] = [{"vehicleType": "4_wheeler"}]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_group_invitation_visitor_missing_full_name_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _group_payload()
    del payload["visitors"][0]["fullName"]
    response = await _create_invitation(
        client, token, branch, payload=payload, visitor_file_count=2
    )
    assert response.status_code == 422


# --- dedupe-repeat-visitor-registrations: returning primary contact --------


def _phone_only_primary_contact(payload: dict, *, full_name: str, phone: str) -> dict:
    """Swaps `payload["primaryContact"]` to a phone-only contact (no email)
    — `preferredContactMethod` must be `sms` in that case, per
    `InvitationPrimaryContactCreate._check_contact`.
    """
    payload["primaryContact"] = {
        "fullName": full_name,
        "phone": phone,
        "preferredContactMethod": "sms",
        "idProofType": "Passport",
    }
    return payload


async def test_create_invitation_first_time_email_uses_submitted_name(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["primaryContact"]["email"] = "first.timer@example.com"
    payload["primaryContact"]["fullName"] = "First Timer"
    data = await _create_invitation_success(client, token, branch, payload=payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert invitation.primary_contact_full_name == "First Timer"


async def test_create_invitation_returning_email_locks_full_name(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    token = await _login(client, user.email)
    email = "priya.returning@example.com"

    first_payload = _individual_payload()
    first_payload["primaryContact"]["email"] = email
    first_payload["primaryContact"]["fullName"] = "Priya Sharma"
    await _create_invitation_success(client, token, branch, payload=first_payload)

    second_payload = _individual_payload()
    second_payload["primaryContact"]["email"] = email
    second_payload["primaryContact"]["fullName"] = "Priya S."
    second_data = await _create_invitation_success(client, token, branch, payload=second_payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(
        second_data["trackingId"]
    )
    assert invitation is not None
    assert invitation.primary_contact_full_name == "Priya Sharma"


async def test_create_invitation_returning_email_other_fields_taken_fresh(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    token = await _login(client, user.email)
    email = "returning.other.fields@example.com"

    first_payload = _individual_payload()
    first_payload["primaryContact"]["email"] = email
    first_payload["primaryContact"]["phone"] = "+91 90000 00001"
    await _create_invitation_success(client, token, branch, payload=first_payload)

    second_payload = _individual_payload()
    second_payload["primaryContact"]["email"] = email
    second_payload["primaryContact"]["phone"] = "+91 90000 99999"
    second_payload["visitDetails"]["purposeOfVisit"] = "Follow-up Meeting"
    second_data = await _create_invitation_success(client, token, branch, payload=second_payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(
        second_data["trackingId"]
    )
    assert invitation is not None
    assert invitation.primary_contact_phone == "+91 90000 99999"
    assert invitation.visitor_category_id == _DEFAULT_VISITOR_CATEGORY_ID
    assert invitation.purpose_of_visit == "Follow-up Meeting"


async def test_create_invitation_denied_prior_invitation_still_locks_name(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    email = "once.denied@example.com"
    prior = _build_invitation(
        db_session,
        branch.id,
        status="denied",
        primary_contact_full_name="Original Name",
        primary_contact_email=email,
        primary_contact_phone=None,
    )
    db_session.add(prior)
    await db_session.commit()

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["primaryContact"]["email"] = email
    payload["primaryContact"]["fullName"] = "Different Name"
    data = await _create_invitation_success(client, token, branch, payload=payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert invitation.primary_contact_full_name == "Original Name"


async def test_create_invitation_phone_fallback_locks_name_and_email(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    token = await _login(client, user.email)
    phone = "+91 99999 11111"

    first_payload = _individual_payload()
    first_payload["primaryContact"]["email"] = "phone.fallback@example.com"
    first_payload["primaryContact"]["fullName"] = "Phone Fallback"
    first_payload["primaryContact"]["phone"] = phone
    await _create_invitation_success(client, token, branch, payload=first_payload)

    second_payload = _phone_only_primary_contact(
        _individual_payload(), full_name="Different Name", phone=phone
    )
    second_data = await _create_invitation_success(client, token, branch, payload=second_payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(
        second_data["trackingId"]
    )
    assert invitation is not None
    assert invitation.primary_contact_full_name == "Phone Fallback"
    assert invitation.primary_contact_email == "phone.fallback@example.com"


async def test_create_invitation_phone_fallback_no_match_is_first_time(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    token = await _login(client, user.email)
    payload = _phone_only_primary_contact(
        _individual_payload(), full_name="Nobody Before", phone="+91 88888 22222"
    )
    data = await _create_invitation_success(client, token, branch, payload=payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert invitation.primary_contact_full_name == "Nobody Before"
    assert invitation.primary_contact_email is None


async def test_create_invitation_new_email_not_rescued_by_phone_match(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    token = await _login(client, user.email)
    shared_phone = "+91 77777 33333"

    first_payload = _individual_payload()
    first_payload["primaryContact"]["email"] = "old.identity@example.com"
    first_payload["primaryContact"]["fullName"] = "Old Identity"
    first_payload["primaryContact"]["phone"] = shared_phone
    await _create_invitation_success(client, token, branch, payload=first_payload)

    second_payload = _individual_payload()
    second_payload["primaryContact"]["email"] = "new.identity@example.com"
    second_payload["primaryContact"]["fullName"] = "New Identity"
    second_payload["primaryContact"]["phone"] = shared_phone
    second_data = await _create_invitation_success(client, token, branch, payload=second_payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(
        second_data["trackingId"]
    )
    assert invitation is not None
    assert invitation.primary_contact_full_name == "New Identity"
    assert invitation.primary_contact_email == "new.identity@example.com"


async def test_create_invitation_returning_contact_creates_new_row_prior_unchanged(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    token = await _login(client, user.email)
    email = "two.visits@example.com"

    first_payload = _individual_payload()
    first_payload["primaryContact"]["email"] = email
    first_payload["primaryContact"]["fullName"] = "Two Visits"
    first_data = await _create_invitation_success(client, token, branch, payload=first_payload)

    second_payload = _individual_payload()
    second_payload["primaryContact"]["email"] = email
    second_payload["primaryContact"]["fullName"] = "Renamed Attempt"
    second_data = await _create_invitation_success(client, token, branch, payload=second_payload)

    assert first_data["trackingId"] != second_data["trackingId"]
    repo = InvitationRepository(db_session)
    first_invitation = await repo.get_by_tracking_id(first_data["trackingId"])
    second_invitation = await repo.get_by_tracking_id(second_data["trackingId"])
    assert first_invitation is not None
    assert second_invitation is not None
    assert first_invitation.primary_contact_full_name == "Two Visits"
    assert second_invitation.primary_contact_full_name == "Two Visits"


async def test_create_group_invitation_covisitor_email_match_is_unaffected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """Co-visitors are never matched or locked — only the primary contact
    is deduped by this change.
    """
    token = await _login(client, user.email)
    covisitor_email = "recurring.covisitor@enterprise-ugo.co"

    first_payload = _group_payload()
    first_payload["primaryContact"]["email"] = "group.host.one@example.com"
    first_payload["visitors"][0]["email"] = covisitor_email
    first_payload["visitors"][0]["fullName"] = "Original Covisitor Name"
    await _create_invitation_success(
        client, token, branch, payload=first_payload, visitor_file_count=2
    )

    second_payload = _group_payload()
    second_payload["primaryContact"]["email"] = "group.host.two@example.com"
    second_payload["visitors"][0]["email"] = covisitor_email
    second_payload["visitors"][0]["fullName"] = "New Submitted Covisitor Name"
    second_data = await _create_invitation_success(
        client, token, branch, payload=second_payload, visitor_file_count=2
    )

    invitation = await InvitationRepository(db_session).get_with_children(
        uuid.UUID(second_data["id"])
    )
    assert invitation is not None
    covisitor = next(v for v in invitation.visitors if v.email == covisitor_email)
    assert covisitor.full_name == "New Submitted Covisitor Name"


def test_invitation_payload_description_matches_schema_requirements() -> None:
    """Independently recomputes each schema's own `required` list (not by
    calling `router._required_fields_summary()` — that would just prove the
    function agrees with itself) and asserts the `payload` field's
    description names every one of them, so a future field addition that
    updates the schema without updating the description text fails this
    test (verify-invitation-validation-and-dispatch/design.md Decision 2).
    """
    from vmss_api.invitations import router
    from vmss_api.invitations.schemas import (
        CarriedItemsSubmit,
        InvitationCreate,
        InvitationPrimaryContactCreate,
        VehicleSubmit,
        VisitDetailsSubmit,
        VisitorSubmit,
    )

    description = router._PAYLOAD_DESCRIPTION
    # `consents` is no longer its own nested schema (`dict[str, bool]`
    # directly on `InvitationCreate`) — its top-level requiredness is
    # already covered via `InvitationCreate.model_json_schema()["required"]`
    # below.
    models: list[type[BaseModel]] = [
        InvitationCreate,
        InvitationPrimaryContactCreate,
        VisitorSubmit,
        VisitDetailsSubmit,
        CarriedItemsSubmit,
        VehicleSubmit,
    ]
    for model in models:
        for field_name in model.model_json_schema().get("required", []):
            assert field_name in description, (
                f"{model.__name__}'s required field {field_name!r} is not "
                "mentioned in the payload description"
            )


# --- API-12: public tracking lookup ------------------------------------------


async def test_track_by_tracking_id_individual_success(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=_individual_payload())

    response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": data["trackingId"]}
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "submitted"
    assert body["primaryContactFullName"] == "Meera Krishnan"
    assert body["visitors"] == []
    assert body["vehicles"] == []
    assert body["expectedDuration"] == "< 1 hour"
    assert body["departmentToVisit"] == "Human Resources"


async def test_track_by_tracking_id_masks_custom_file_upload_field_raw_storage_key(
    client: AsyncClient, user: User, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """add-generic-custom-field-file-url-resolution, extended to the public
    tracking-lookup response — same posture as the QR/check-in-by-tracking-
    id counterparts: a `file_upload`-typed custom field's raw storage key
    must never reach this unauthenticated caller.
    """
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="visitor_info", key="pic", field_type="file_upload"
    )
    invitation = _build_invitation(
        db_session,
        branch.id,
        primary_contact_custom_field_values={
            field["id"]: "vmss:tenant:invitations/custom-fields:primary-pic.jpg"
        },
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": invitation.tracking_id}
    )
    assert response.status_code == 200
    assert _custom_field_value(response.json()["data"]["customFields"], field["id"]) is None


async def test_track_by_tracking_id_group_success(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    data = await _create_invitation_success(
        client, token, branch, payload=_group_payload(), visitor_file_count=2
    )

    response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": data["trackingId"]}
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "submitted"
    assert len(body["visitors"]) == 2
    assert len(body["vehicles"]) == 2
    assert body["carriedItems"] == ["laptop_tablet", "mobile_phone"]
    assert body["carriedItemsDescription"] == "2 laptops"


async def test_track_by_tracking_id_omits_current_step_for_auto_approved_invitation(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Non-workflow invitation omits step progress" — an
    auto-approved invitation is never `submitted` and has no snapshotted
    steps at all (role-based-invitation-workflow: every *submitted*
    invitation now gets an unconditional ownership step, but an
    auto-approved one skips snapshotting entirely — see "Auto-Approved
    Invitations Are Never Snapshotted").
    """
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), auto_approve_pre_registered_visitors=True))
    await db_session.commit()

    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=_individual_payload())
    assert data["status"] == "approved"

    response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": data["trackingId"]}
    )
    assert response.status_code == 200
    assert response.json()["data"]["currentApprovalStep"] is None


async def test_track_by_tracking_id_exposes_current_step_for_workflow_backed_invitation(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """invitation-multi-step-approval spec.md "Workflow-backed invitation
    exposes current step progress" — a category with two active rules
    snapshots exactly those two steps at submission (no separate ownership
    step ahead of them — see `docs/features/approvals.md` "The
    host-nomination step"); the tracking lookup surfaces the first
    configured step (`stepOrder` 1) as current, since it's the first to
    become pending and doubles as the host-nomination step.
    """
    category = VisitorCategoryFactory.build(
        id=uuid.uuid4(), name="Workflow Category", code="WORKFLOW-CAT"
    )
    approver_role = RoleFactory.build(id=uuid.uuid4(), name="step-one-approver", permissions=[])
    db_session.add_all([category, approver_role])
    await db_session.flush()
    db_session.add_all(
        [
            ApprovalWorkflowRuleFactory.build(
                id=uuid.uuid4(),
                visitor_category_id=category.id,
                step_order=1,
                approver_role_id=approver_role.id,
            ),
            ApprovalWorkflowRuleFactory.build(
                id=uuid.uuid4(),
                visitor_category_id=category.id,
                step_order=2,
                approver_role_id=approver_role.id,
            ),
        ]
    )
    await db_session.commit()

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitorCategoryId"] = str(category.id)
    data = await _create_invitation_success(client, token, branch, payload=payload)
    steps = await InvitationApprovalStepRepository(db_session).list_for_invitation(
        uuid.UUID(data["id"])
    )
    step_one = next(s for s in steps if s.step_order == 1)
    assert data["currentApprovalStep"] == {
        "id": str(step_one.id),
        "stepOrder": 1,
        "approverRoleId": str(approver_role.id),
        "approverUserId": None,
        "totalSteps": 2,
        "delegatedToUserId": None,
    }

    response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": data["trackingId"]}
    )
    assert response.status_code == 200
    assert response.json()["data"]["currentApprovalStep"] == {
        "id": str(step_one.id),
        "stepOrder": 1,
        "approverRoleId": str(approver_role.id),
        "approverUserId": None,
        "totalSteps": 2,
        "delegatedToUserId": None,
    }


async def test_track_unknown_tracking_id_not_found(client: AsyncClient, tenant: Tenant) -> None:
    response = await client.get("/api/v1/invitations/track", params={"trackingId": "INV-DEADBEEF"})
    assert response.status_code == 404


async def test_track_requires_exactly_one_param(client: AsyncClient, tenant: Tenant) -> None:
    response = await client.get("/api/v1/invitations/track")
    assert response.status_code == 422

    response = await client.get(
        "/api/v1/invitations/track",
        params={"trackingId": "INV-DEADBEEF", "email": "a@example.com"},
    )
    assert response.status_code == 422


async def test_track_by_email_minimal_disclosure(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    data = await _create_invitation_success(
        client, token, branch, payload=_group_payload(), visitor_file_count=2
    )

    response = await client.get(
        "/api/v1/invitations/track", params={"email": "priya.sharma@enterprise-ugo.co"}
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert len(body) == 1
    assert set(body[0].keys()) == {"trackingId", "status"}
    assert body[0]["trackingId"] == data["trackingId"]


async def test_track_rate_limit_trips(client: AsyncClient, tenant: Tenant, monkeypatch) -> None:
    """`slowapi`'s `Limiter` is disabled outright in the test environment
    (`core/rate_limit.py`: `enabled=settings.environment != "test"`) — flipped
    on here for just this one test to exercise the 429 path
    (security-architecture.md §2), then restored.
    """
    monkeypatch.setattr(limiter, "enabled", True)
    responses = [
        await client.get("/api/v1/invitations/track", params={"trackingId": "INV-DEADBEEF"})
        for _ in range(25)
    ]
    assert any(r.status_code == 429 for r in responses)


async def test_track_unresolvable_default_tenant_logged_as_error(
    client: AsyncClient, monkeypatch
) -> None:
    """`track_default_tenant_db` (`invitations/deps.py`) resolves the single
    configured default tenant via `core.tenancy.resolve_default_tenant`. When
    that tenant doesn't exist, this is a server-side misconfiguration, not a
    caller error, so it must be logged at `ERROR` with the same
    not-found/inactive distinction `registrations/deps.py`'s equivalent
    fallback already has — see
    harden-default-tenant-resolution-and-readiness/design.md. The
    client-facing 404 is unchanged from before this consistency fix.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", "no-such-tenant-slug")

    with capture_logs() as captured:
        response = await client.get(
            "/api/v1/invitations/track", params={"trackingId": "INV-DEADBEEF"}
        )

    assert response.status_code == 404
    assert response.json()["message"] == "Tenant not found or inactive"

    [entry] = [e for e in captured if e["event"] == "invitations_track_default_tenant_unconfigured"]
    assert entry["log_level"] == "error"
    assert entry["reason"] == "not_found"


async def test_track_inactive_default_tenant_logged_as_error(
    client: AsyncClient, tenant: Tenant, db_session: AsyncSession
) -> None:
    await db_session.execute(update(Tenant).where(Tenant.id == tenant.id).values(is_active=False))
    await db_session.commit()

    with capture_logs() as captured:
        response = await client.get(
            "/api/v1/invitations/track", params={"trackingId": "INV-DEADBEEF"}
        )

    assert response.status_code == 404
    assert response.json()["message"] == "Tenant not found or inactive"

    [entry] = [e for e in captured if e["event"] == "invitations_track_default_tenant_unconfigured"]
    assert entry["log_level"] == "error"
    assert entry["reason"] == "inactive"


# --- Employee listing (GET /invitations) -------------------------------------


async def _branch_scoped_invitation_viewer(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID
) -> User:
    """A branch-wide invitation viewer (`invitations:view` +
    `invitations:view-all`) at `branch_id` — the branch-scoping counterpart
    of `org_structure/tests.py`'s `_branch_scoped_user`, applied to this
    feature's own permissions. See `_branch_scoped_host` for a caller holding
    `invitations:view` alone (restrict-delegated-invitation-visibility).
    """
    permissions = [
        PermissionFactory.build(id=uuid.uuid4(), code=code, description=code)
        for code in ("invitations:view", "invitations:view-all")
    ]
    role = RoleFactory.build(id=uuid.uuid4(), name="invitations-viewer", permissions=permissions)
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"viewer-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Invitation Viewer",
        branch_roles=[branch_role],
    )
    db_session.add_all([*permissions, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


async def _branch_scoped_invitation_editor(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID
) -> User:
    """A caller whose only role grant is `invitations:edit` at `branch_id` —
    holds enough to reach `PATCH /invitations/{id}/edit` at all, but not
    `invitations:approve`, for point-of-contact authorization tests
    (add-invitation-point-of-contact: setting `pocUserId`/`pocRoleId`
    requires `invitations:approve` in addition to this endpoint's own
    `invitations:edit` gate).
    """
    permission = PermissionFactory.build(
        id=uuid.uuid4(), code="invitations:edit", description="invitations:edit"
    )
    role = RoleFactory.build(id=uuid.uuid4(), name="invitations-editor", permissions=[permission])
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"editor-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Invitation Editor",
        branch_roles=[branch_role],
    )
    db_session.add_all([permission, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


async def _branch_scoped_invitation_and_documents_viewer(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID
) -> User:
    """Same as `_branch_scoped_invitation_viewer` but additionally holds
    `documents:view` at `branch_id` —
    enrich-invitation-checkin-and-detail-views spec.md "Primary Contact and
    Visitor ID-Proof Documents Are Surfaced Only to Callers Holding
    documents:view".
    """
    permissions = [
        PermissionFactory.build(id=uuid.uuid4(), code=code, description=code)
        for code in ("invitations:view", "invitations:view-all", "documents:view")
    ]
    role = RoleFactory.build(id=uuid.uuid4(), name="documents-viewer", permissions=permissions)
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"docs-viewer-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Documents Viewer",
        branch_roles=[branch_role],
    )
    db_session.add_all([*permissions, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


async def _branch_scoped_invitation_creator(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID
) -> User:
    """A caller whose only role grant is `invitations:create` at
    `branch_id` — same shape as `_branch_scoped_invitation_viewer`, for
    `GET /invitations/lookup-by-email`'s branch-scoped
    `require_branch_scope("invitations:create")` gate
    (add-invitation-lookup-by-email/design.md).
    """
    permission = PermissionFactory.build(
        id=uuid.uuid4(), code="invitations:create", description="invitations:create"
    )
    role = RoleFactory.build(id=uuid.uuid4(), name="invitations-creator", permissions=[permission])
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"creator-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Invitation Creator",
        branch_roles=[branch_role],
    )
    db_session.add_all([permission, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


async def _branch_scoped_invitation_creator_with_documents(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID
) -> User:
    """Same as `_branch_scoped_invitation_creator` but additionally holds
    `documents:view` at `branch_id` — for
    `GET /invitations/lookup-by-email`'s `idProofUrl` gating (spec.md
    "ID-proof URL Is Resolved With documents:view").
    """
    permissions = [
        PermissionFactory.build(id=uuid.uuid4(), code=code, description=code)
        for code in ("invitations:create", "documents:view")
    ]
    role = RoleFactory.build(
        id=uuid.uuid4(), name="creator-with-documents", permissions=permissions
    )
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"creator-docs-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Invitation Creator With Documents",
        branch_roles=[branch_role],
    )
    db_session.add_all([*permissions, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


def _build_invitation(
    db_session: AsyncSession,
    branch_id: uuid.UUID,
    **overrides,
):
    """Builds (but does not add/commit) an `Invitation` row via the shared
    `InvitationFactory` (testing-standards.md §1) rather than a hand-built
    dict — callers add and commit once, per query-performance.md §3's
    "commit once, not once per row" habit, applied here to test setup.
    `created_by_user_id` is forced to `None`: it's a real FK to `users`, and
    polyfactory's auto-generated UUID for it never matches an actual row.
    `registration_type`/`source` default to a valid enum value each, since
    the router maps the plain string columns back through
    `RegistrationType`/`RegistrationSource` when serializing a list row.
    """
    overrides.setdefault("created_by_user_id", None)
    overrides.setdefault("registration_type", "individual")
    overrides.setdefault("source", "staff_pre_registration")
    return InvitationFactory.build(id=uuid.uuid4(), branch_id=branch_id, **overrides)


async def test_list_invitations_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get("/api/v1/invitations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] >= 1
    tracking_ids = {row["trackingId"] for row in body["data"]}
    assert invitation.tracking_id in tracking_ids
    row = next(r for r in body["data"] if r["trackingId"] == invitation.tracking_id)
    assert set(row.keys()) == {
        "id",
        "trackingId",
        "registrationType",
        "source",
        "status",
        "visitorCategoryId",
        "primaryContactFullName",
        "primaryContactEmail",
        "primaryContactPhone",
        "primaryContactPhotoUrl",
        "purposeOfVisit",
        "departmentToVisit",
        "departmentId",
        "buildingId",
        "expiresAt",
        "submittedAt",
        "approvedAt",
        "archivedAt",
        "checkedOutAutomatically",
        "statusChangedAt",
    }
    assert row["visitorCategoryId"] is None
    assert row["primaryContactPhotoUrl"] is None
    assert row["primaryContactEmail"] == invitation.primary_contact_email
    assert row["primaryContactPhone"] == invitation.primary_contact_phone


async def test_list_invitations_surfaces_primary_contact_photo_url(
    client: AsyncClient, user: User, branch: Branch, tenant: Tenant, db_session: AsyncSession
) -> None:
    """qr-checkin-scheduling-photo-email spec.md "List row surfaces the
    primary contact's photo URL when one was captured" — matches what the
    tracking/detail endpoints already return for the same invitation.

    add-avatar-upload-and-verify-image-storage spec.md "Every photo URL
    returned by any invitation response ... SHALL be a fetchable HTTP URL"
    — asserts the list row's URL is genuinely fetchable, not just non-null.
    """
    photo_bytes = _jpeg_bytes()
    photo_key = await storage.save(tenant.id, "invitations/photos", photo_bytes, "image/jpeg")
    invitation = _build_invitation(
        db_session,
        branch.id,
        primary_contact_photo_storage_key=photo_key,
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get("/api/v1/invitations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    row = next(r for r in response.json()["data"] if r["trackingId"] == invitation.tracking_id)
    assert row["primaryContactPhotoUrl"] is not None

    photo_response = await client.get(row["primaryContactPhotoUrl"])
    assert photo_response.status_code == 200
    assert photo_response.content == photo_bytes


async def test_list_invitations_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get("/api/v1/invitations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


async def test_list_invitations_branch_header_narrows_to_one_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-INV")
    db_session.add(other_branch)
    await db_session.flush()

    in_scope = _build_invitation(db_session, branch.id)
    other_branch_invitation = _build_invitation(db_session, other_branch.id)
    db_session.add_all([in_scope, other_branch_invitation])
    await db_session.commit()

    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/invitations",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert in_scope.tracking_id in tracking_ids
    assert other_branch_invitation.tracking_id not in tracking_ids


async def test_list_invitations_unauthorized_branch_id_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-INV-2")
    db_session.add(other_branch)
    await db_session.commit()

    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/invitations",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(other_branch.id)},
    )
    assert response.status_code == 403


async def test_list_invitations_without_branch_header_returns_every_authorized_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-INV-3")
    db_session.add(other_branch)
    await db_session.flush()

    invitation = _build_invitation(db_session, branch.id)
    other_branch_invitation = _build_invitation(db_session, other_branch.id)
    db_session.add_all([invitation, other_branch_invitation])
    await db_session.commit()

    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    token = issue_token(viewer)
    response = await client.get("/api/v1/invitations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids
    assert other_branch_invitation.tracking_id not in tracking_ids


# --- add-invitation-lookup-by-email ------------------------------------------


async def test_lookup_by_email_returns_most_recent_invitations_prefill_data(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    identifier = "jane@example.com"
    older = _build_invitation(
        db_session,
        branch.id,
        primary_contact_email=identifier,
        primary_contact_full_name="J Doe",
        tracking_id="INV-LOOKUP-OLD1",
    )
    newer = _build_invitation(
        db_session,
        branch.id,
        primary_contact_email=identifier,
        primary_contact_full_name="Jane Doe",
        primary_contact_phone="1234567890",
        primary_contact_preferred_contact_method="email",
        primary_contact_id_proof_type="passport",
        visitor_category_id=_DEFAULT_VISITOR_CATEGORY_ID,
        tracking_id="INV-LOOKUP-NEW1",
    )
    db_session.add_all([older, newer])
    await db_session.commit()
    now = datetime.now(UTC)
    newer.created_at = now
    older.created_at = now - timedelta(days=1)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": identifier},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["fullName"] == "Jane Doe"
    assert data["phone"] == "1234567890"
    assert data["preferredContactMethod"] == "email"
    assert data["idProofType"] == "passport"
    assert data["visitorCategoryId"] == str(_DEFAULT_VISITOR_CATEGORY_ID)


async def test_lookup_by_email_is_case_insensitive(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    invitation = _build_invitation(db_session, branch.id, primary_contact_email="Jane@Example.com")
    db_session.add(invitation)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "jane@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"] is not None


async def test_lookup_by_email_no_match_returns_null_data(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "no-such-visitor@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"] is None


async def test_lookup_by_email_match_at_unauthorized_branch_returns_null(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-LOOKUP-1")
    db_session.add(other_branch)
    await db_session.flush()

    invitation = _build_invitation(
        db_session, other_branch.id, primary_contact_email="only-at-other-branch@example.com"
    )
    db_session.add(invitation)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "only-at-other-branch@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"] is None


async def test_lookup_by_email_branch_header_excludes_matching_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-LOOKUP-2")
    db_session.add(other_branch)
    await db_session.flush()

    invitation = _build_invitation(
        db_session, other_branch.id, primary_contact_email="multi-branch-caller@example.com"
    )
    db_session.add(invitation)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    branch_role = UserBranchRole(
        id=uuid.uuid4(), role=creator.branch_roles[0].role, branch_id=other_branch.id
    )
    creator.branch_roles.append(branch_role)
    db_session.add(branch_role)
    await db_session.commit()

    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "multi-branch-caller@example.com"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200
    assert response.json()["data"] is None


async def test_lookup_by_email_requires_invitations_create_permission(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """A caller holding only `invitations:view` (not `invitations:create`)
    is rejected — this lookup only exists to prefill the create flow
    (add-invitation-lookup-by-email/design.md "Permission").
    """
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "anyone@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_lookup_by_email_photo_url_resolved_without_documents_view(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "Photo URL Is Always Resolved When Captured" — a face photo
    isn't gated like an identity document in this codebase."""
    invitation = _build_invitation(
        db_session,
        branch.id,
        primary_contact_email="has-documents@example.com",
        primary_contact_id_proof_storage_key="docs/id.jpg",
        primary_contact_photo_storage_key="docs/photo.jpg",
    )
    db_session.add(invitation)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "has-documents@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["photoUrl"] is not None


async def test_lookup_by_email_id_proof_url_null_without_documents_view(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "ID-proof URL Is Null Without documents:view"."""
    invitation = _build_invitation(
        db_session,
        branch.id,
        primary_contact_email="has-id-proof@example.com",
        primary_contact_id_proof_storage_key="docs/id.jpg",
    )
    db_session.add(invitation)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "has-id-proof@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["idProofType"] is not None
    assert data["idProofUrl"] is None


async def test_lookup_by_email_id_proof_url_resolved_with_documents_view(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "ID-proof URL Is Resolved With documents:view"."""
    invitation = _build_invitation(
        db_session,
        branch.id,
        primary_contact_email="has-id-proof-2@example.com",
        primary_contact_id_proof_storage_key="docs/id.jpg",
    )
    db_session.add(invitation)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator_with_documents(db_session, tenant, branch.id)
    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "has-id-proof-2@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["idProofUrl"] is not None


async def test_list_invitations_filters_by_status_registration_type_and_source(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    matching = _build_invitation(
        db_session,
        branch.id,
        status="submitted",
        registration_type="group",
        source="visitor_walk_in",
    )
    non_matching = _build_invitation(
        db_session,
        branch.id,
        status="cancelled",
        registration_type="individual",
        source="staff_pre_registration",
    )
    db_session.add_all([matching, non_matching])
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={
            "status": "submitted",
            "registrationType": "group",
            "source": "visitor_walk_in",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert matching.tracking_id in tracking_ids
    assert non_matching.tracking_id not in tracking_ids


async def test_list_invitations_filters_by_search_matching_contact_name_or_tracking_id(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    jane = _build_invitation(db_session, branch.id, primary_contact_full_name="Jane Visitor")
    john = _build_invitation(db_session, branch.id, primary_contact_full_name="John Guest")
    db_session.add_all([jane, john])
    await db_session.commit()

    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}

    name_response = await client.get(
        "/api/v1/invitations", params={"search": "jane"}, headers=headers
    )
    assert name_response.status_code == 200
    name_tracking_ids = {row["trackingId"] for row in name_response.json()["data"]}
    assert jane.tracking_id in name_tracking_ids
    assert john.tracking_id not in name_tracking_ids

    id_response = await client.get(
        "/api/v1/invitations", params={"search": john.tracking_id}, headers=headers
    )
    assert id_response.status_code == 200
    id_tracking_ids = {row["trackingId"] for row in id_response.json()["data"]}
    assert john.tracking_id in id_tracking_ids
    assert jane.tracking_id not in id_tracking_ids


async def test_list_invitations_filters_by_purpose_of_visit(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """specs/invitations/spec.md "Invitation List Supports a Purpose-of-Visit
    Filter" — exact match, reflected in `pagination.total`.
    """
    purpose = f"Interview {uuid.uuid4().hex[:8]}"
    matching = _build_invitation(db_session, branch.id, purpose_of_visit=purpose)
    non_matching = _build_invitation(db_session, branch.id, purpose_of_visit="Delivery")
    db_session.add_all([matching, non_matching])
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={"purposeOfVisit": purpose},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [row["trackingId"] for row in body["data"]] == [matching.tracking_id]
    assert body["pagination"]["total"] == 1


async def test_list_invitations_purpose_filter_combines_with_status(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    purpose = f"Interview {uuid.uuid4().hex[:8]}"
    submitted = _build_invitation(
        db_session, branch.id, purpose_of_visit=purpose, status="submitted"
    )
    approved = _build_invitation(db_session, branch.id, purpose_of_visit=purpose, status="approved")
    db_session.add_all([submitted, approved])
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={"purposeOfVisit": purpose, "status": "submitted"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert [row["trackingId"] for row in response.json()["data"]] == [submitted.tracking_id]


async def test_list_invitations_purpose_filter_requires_exact_match(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    purpose = f"Interview {uuid.uuid4().hex[:8]}"
    invitation = _build_invitation(db_session, branch.id, purpose_of_visit=purpose)
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={"purposeOfVisit": purpose[:-1]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id not in tracking_ids


async def test_list_invitations_purpose_filter_rejects_over_long_value(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={"purposeOfVisit": "x" * 256},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "status_value", ["submitted", "approved", "denied", "checked_in", "checked_out"]
)
async def test_list_invitations_filters_by_each_status_value(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    status_value: str,
) -> None:
    """api-conventions.md §1 — `InvitationStatus` is a closed enum covering
    every value `Invitation.status`'s state-machine writes ever produce
    (schemas.py's `InvitationStatus` docstring); this proves each one
    actually round-trips through the `status` query param, not just
    "submitted" the way the combined filter test above does.
    """
    other_status = "approved" if status_value != "approved" else "submitted"
    matching = _build_invitation(db_session, branch.id, status=status_value)
    non_matching = _build_invitation(db_session, branch.id, status=other_status)
    db_session.add_all([matching, non_matching])
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={"status": status_value},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert matching.tracking_id in tracking_ids
    assert non_matching.tracking_id not in tracking_ids


async def test_list_invitations_invalid_status_rejected(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={"status": "cancelled"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_list_invitations_sort_order(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    older = _build_invitation(db_session, branch.id, submitted_at=now - timedelta(hours=1))
    newer = _build_invitation(db_session, branch.id, submitted_at=now)
    db_session.add_all([older, newer])
    await db_session.commit()

    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}

    default_order = await client.get("/api/v1/invitations", headers=headers)
    default_ids = [row["trackingId"] for row in default_order.json()["data"]]
    assert default_ids.index(newer.tracking_id) < default_ids.index(older.tracking_id)

    asc_order = await client.get(
        "/api/v1/invitations", params={"sortOrder": "asc"}, headers=headers
    )
    asc_ids = [row["trackingId"] for row in asc_order.json()["data"]]
    assert asc_ids.index(older.tracking_id) < asc_ids.index(newer.tracking_id)


async def test_list_invitations_invalid_sort_by_rejected(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={"sortBy": "not_a_real_field"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


# --- sort-invitation-board-by-status-date -------------------------------------

_STATUS_TIMESTAMP_FIELDS = (
    "submitted_at",
    "approved_at",
    "checked_in_at",
    "checked_out_at",
    "denied_at",
    "archived_at",
    "approval_reverted_at",
    "rescheduled_at",
)


def _build_status_row(
    db_session: AsyncSession,
    branch_id: uuid.UUID,
    marker: str,
    status: str,
    **timestamps: datetime | None,
):
    """An invitation in `status` with every status timestamp pinned (None
    unless given) so the factory's random values can't affect the sort, and
    `marker` in the contact name so `search` isolates a test's own rows."""
    overrides: dict[str, Any] = dict.fromkeys(_STATUS_TIMESTAMP_FIELDS)
    overrides.update(timestamps)
    return _build_invitation(
        db_session,
        branch_id,
        status=status,
        primary_contact_full_name=f"{marker} {uuid.uuid4().hex[:6]}",
        **overrides,
    )


async def _list_rows(
    client: AsyncClient, token: str, marker: str, **params: Any
) -> list[dict[str, Any]]:
    response = await client.get(
        "/api/v1/invitations",
        params={"search": marker, "pageSize": 100, **params},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_list_invitations_status_changed_at_orders_checked_in_by_check_in_time(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Checked-in column orders by most recent check-in"."""
    marker = f"chk{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    recent_check_in = _build_status_row(
        db_session,
        branch.id,
        marker,
        "checked_in",
        submitted_at=now - timedelta(days=3),
        checked_in_at=now - timedelta(minutes=5),
    )
    older_check_in = _build_status_row(
        db_session,
        branch.id,
        marker,
        "checked_in",
        submitted_at=now - timedelta(days=1),
        checked_in_at=now - timedelta(hours=2),
    )
    db_session.add_all([recent_check_in, older_check_in])
    await db_session.commit()

    token = await _login(client, user.email)
    rows = await _list_rows(client, token, marker, status="checked_in", sortBy="status_changed_at")
    assert [row["trackingId"] for row in rows] == [
        recent_check_in.tracking_id,
        older_check_in.tracking_id,
    ]
    assert datetime.fromisoformat(rows[0]["statusChangedAt"]) == recent_check_in.checked_in_at

    default_rows = await _list_rows(client, token, marker, status="checked_in")
    assert [row["trackingId"] for row in default_rows] == [
        older_check_in.tracking_id,
        recent_check_in.tracking_id,
    ]


@pytest.mark.parametrize(
    ("status", "timestamp_field"),
    [
        ("approved", "approved_at"),
        ("checked_out", "checked_out_at"),
        ("denied", "denied_at"),
        ("archived", "archived_at"),
    ],
)
async def test_list_invitations_status_changed_at_uses_each_status_timestamp(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    status: str,
    timestamp_field: str,
) -> None:
    """spec.md "Each status column orders by its own status time" and
    "Ascending order is supported" — the older-submitted row changed status
    most recently, so it leads under `desc` and trails under `asc`."""
    marker = f"st{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    changed_recently = _build_status_row(
        db_session,
        branch.id,
        marker,
        status,
        submitted_at=now - timedelta(days=5),
        **{timestamp_field: now - timedelta(minutes=1)},
    )
    changed_earlier = _build_status_row(
        db_session,
        branch.id,
        marker,
        status,
        submitted_at=now - timedelta(days=1),
        **{timestamp_field: now - timedelta(hours=6)},
    )
    db_session.add_all([changed_recently, changed_earlier])
    await db_session.commit()

    token = await _login(client, user.email)
    desc_rows = await _list_rows(client, token, marker, status=status, sortBy="status_changed_at")
    assert [row["trackingId"] for row in desc_rows] == [
        changed_recently.tracking_id,
        changed_earlier.tracking_id,
    ]
    asc_rows = await _list_rows(
        client, token, marker, status=status, sortBy="status_changed_at", sortOrder="asc"
    )
    assert [row["trackingId"] for row in asc_rows] == [
        changed_earlier.tracking_id,
        changed_recently.tracking_id,
    ]


async def test_list_invitations_status_changed_at_requested_column_revert_and_reschedule(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "An invitation whose approval was reverted returns to the top
    of Requested" / "An archived invitation rescheduled back into approval
    is ordered by the reschedule" — and a plain reschedule of a
    never-archived request does not move it."""
    marker = f"req{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    reverted = _build_status_row(
        db_session,
        branch.id,
        marker,
        "submitted",
        submitted_at=now - timedelta(days=7),
        approval_reverted_at=now - timedelta(minutes=1),
    )
    back_from_archive = _build_status_row(
        db_session,
        branch.id,
        marker,
        "submitted",
        submitted_at=now - timedelta(days=10),
        archived_at=now - timedelta(days=2),
        rescheduled_at=now - timedelta(minutes=10),
    )
    submitted_today = _build_status_row(
        db_session, branch.id, marker, "submitted", submitted_at=now - timedelta(hours=1)
    )
    plainly_rescheduled = _build_status_row(
        db_session,
        branch.id,
        marker,
        "submitted",
        submitted_at=now - timedelta(days=4),
        rescheduled_at=now - timedelta(seconds=30),
    )
    db_session.add_all([reverted, back_from_archive, submitted_today, plainly_rescheduled])
    await db_session.commit()

    token = await _login(client, user.email)
    rows = await _list_rows(client, token, marker, status="submitted", sortBy="status_changed_at")
    assert [row["trackingId"] for row in rows] == [
        reverted.tracking_id,
        back_from_archive.tracking_id,
        submitted_today.tracking_id,
        plainly_rescheduled.tracking_id,
    ]


async def test_list_invitations_status_changed_at_interleaves_mixed_statuses(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Mixed-status list orders by each row's own status time"."""
    marker = f"mix{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    old_submission = now - timedelta(days=2)
    checked_out = _build_status_row(
        db_session,
        branch.id,
        marker,
        "checked_out",
        submitted_at=old_submission,
        checked_in_at=now - timedelta(hours=3),
        checked_out_at=now - timedelta(minutes=2),
    )
    submitted = _build_status_row(
        db_session, branch.id, marker, "submitted", submitted_at=now - timedelta(hours=1)
    )
    approved = _build_status_row(
        db_session,
        branch.id,
        marker,
        "approved",
        submitted_at=old_submission,
        approved_at=now - timedelta(hours=5),
    )
    db_session.add_all([checked_out, submitted, approved])
    await db_session.commit()

    token = await _login(client, user.email)
    rows = await _list_rows(client, token, marker, sortBy="status_changed_at")
    assert [row["trackingId"] for row in rows] == [
        checked_out.tracking_id,
        submitted.tracking_id,
        approved.tracking_id,
    ]


@pytest.mark.parametrize("sort_by", [None, "created_at", "status_changed_at"])
async def test_list_invitations_equal_sort_keys_page_stably(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    sort_by: str | None,
) -> None:
    """spec.md "Equal sort keys page stably" — every row shares one
    timestamp, so only the id tie-breaker decides the order."""
    marker = f"tie{uuid.uuid4().hex[:8]}"
    same_moment = datetime.now(UTC) - timedelta(hours=1)
    invitations = [
        _build_status_row(
            db_session,
            branch.id,
            marker,
            "approved",
            submitted_at=same_moment,
            approved_at=same_moment,
            created_at=same_moment,
        )
        for _ in range(7)
    ]
    db_session.add_all(invitations)
    await db_session.commit()

    token = await _login(client, user.email)
    params: dict[str, Any] = {"search": marker, "pageSize": 2}
    if sort_by is not None:
        params["sortBy"] = sort_by
    seen: list[str] = []
    for page in range(1, 5):
        response = await client.get(
            "/api/v1/invitations",
            params={**params, "page": page},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        seen.extend(row["trackingId"] for row in response.json()["data"])
    assert sorted(seen) == sorted(invitation.tracking_id for invitation in invitations)


async def test_status_changed_at_matches_sql_ordering(
    branch: Branch, db_session: AsyncSession
) -> None:
    """design.md Decision 2 — `service.status_changed_at` (the row field)
    must agree with the SQL expression `sortBy=status_changed_at` orders
    by, for every status and for the revert/reschedule/fallback cases."""
    marker = f"par{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    minutes = iter(range(1, 100))

    def ago() -> datetime:
        return now - timedelta(minutes=next(minutes) * 7)

    invitations = [
        _build_status_row(db_session, branch.id, marker, "submitted", submitted_at=ago()),
        _build_status_row(
            db_session,
            branch.id,
            marker,
            "submitted",
            submitted_at=now - timedelta(days=9),
            approval_reverted_at=ago(),
        ),
        _build_status_row(
            db_session,
            branch.id,
            marker,
            "submitted",
            submitted_at=now - timedelta(days=9),
            archived_at=now - timedelta(days=8),
            rescheduled_at=ago(),
        ),
        _build_status_row(
            db_session,
            branch.id,
            marker,
            "submitted",
            submitted_at=ago(),
            rescheduled_at=now,
        ),
        _build_status_row(
            db_session, branch.id, marker, "approved", submitted_at=ago(), approved_at=ago()
        ),
        _build_status_row(
            db_session, branch.id, marker, "checked_in", submitted_at=ago(), checked_in_at=ago()
        ),
        _build_status_row(
            db_session,
            branch.id,
            marker,
            "checked_out",
            submitted_at=ago(),
            checked_out_at=ago(),
        ),
        _build_status_row(
            db_session, branch.id, marker, "denied", submitted_at=ago(), denied_at=ago()
        ),
        _build_status_row(
            db_session, branch.id, marker, "archived", submitted_at=ago(), archived_at=ago()
        ),
        # Missing status timestamp: falls back to submitted_at.
        _build_status_row(db_session, branch.id, marker, "approved", submitted_at=ago()),
    ]
    db_session.add_all(invitations)
    await db_session.commit()

    rows, total = await InvitationRepository(db_session).list_page(
        branch_scope="all",
        status=None,
        registration_type=None,
        source=None,
        search=marker,
        page=1,
        page_size=100,
        sort_by="status_changed_at",
        sort_order=SortOrder.desc,
    )
    assert total == len(invitations)
    python_order = sorted(
        invitations,
        key=lambda invitation: (
            -invitations_service.status_changed_at(invitation).timestamp(),
            invitation.id,
        ),
    )
    assert [row.id for row in rows] == [invitation.id for invitation in python_order]


async def test_list_invitations_status_changed_at_sort_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get(
        "/api/v1/invitations",
        params={"sortBy": "status_changed_at"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_list_invitations_status_changed_at_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    """testing-standards.md §2 — the status-time sort reads only the
    session's own tenant schema."""
    marker = f"iso{uuid.uuid4().hex[:8]}"
    db_session.add(
        _build_status_row(db_session, branch.id, marker, "approved", submitted_at=datetime.now(UTC))
    )
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_status_sort"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        rows, total = await InvitationRepository(other_session).list_page(
            branch_scope="all",
            status=None,
            registration_type=None,
            source=None,
            search=marker,
            page=1,
            page_size=20,
            sort_by="status_changed_at",
            sort_order=SortOrder.desc,
        )
        assert rows == []
        assert total == 0


# --- relevantToMe filter (invitation-relevant-to-me-and-delegation) ----------


async def _invitation_with_host_step(
    db_session: AsyncSession, branch_id: uuid.UUID, host: User, **overrides
):
    """A `submitted` invitation whose `stepOrder` 0 step snapshots `host` as
    its approver — the shape specs/invitations/spec.md "Caller Lists
    Invitations Relevant to Themselves via relevantToMe" keys off.
    """
    invitation = _build_invitation(db_session, branch_id, host_id=host.id, **overrides)
    db_session.add(invitation)
    await db_session.flush()
    db_session.add(
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            step_order=0,
            approver_role_id=None,
            approver_user_id=host.id,
        )
    )
    await db_session.commit()
    return invitation


async def _delegate_step(db_session: AsyncSession, invitation, delegate: User, delegated_by: User):
    """Directly assigns `delegate` to `invitation`'s `stepOrder` 1 step, for
    tests that only need a delegated step to already exist rather than
    exercising the delegate endpoint itself (that's `approvals/tests.py`'s
    job) — mirrors this module's other "unit-style" direct-repository setup
    (testing-standards.md §3).
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    step = InvitationApprovalStepFactory.build(
        id=uuid.uuid4(),
        invitation_id=invitation.id,
        step_order=1,
        approver_role_id=role.id,
    )
    db_session.add(step)
    await db_session.flush()
    updated = await InvitationApprovalStepRepository(db_session).delegate_if_eligible(
        step.id, delegated_to_user_id=delegate.id, delegated_by_user_id=delegated_by.id
    )
    await db_session.commit()
    return updated


async def test_list_invitations_relevant_to_me_host_without_view_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "Host sees their own invitation without
    invitations:view" — `relevantToMe` bypasses the branch-scoped
    permission check entirely.
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    invitation = await _invitation_with_host_step(db_session, branch.id, host)

    token = issue_token(host)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids


async def test_list_invitations_relevant_to_me_honours_purpose_filter(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "Purpose filter applies in relevantToMe mode"."""
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    delivery = await _invitation_with_host_step(
        db_session, branch.id, host, purpose_of_visit="Delivery"
    )
    interview = await _invitation_with_host_step(
        db_session, branch.id, host, purpose_of_visit="Interview"
    )

    token = issue_token(host)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true", "purposeOfVisit": "Delivery"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert delivery.tracking_id in tracking_ids
    assert interview.tracking_id not in tracking_ids


async def test_list_invitations_relevant_to_me_delegate_sees_delegated_invitation(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "Delegate sees the invitation they were
    delegated" — regardless of `invitations:view` and regardless of that
    step's current status.
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    delegate = UserFactory.build(
        id=uuid.uuid4(),
        email=f"delegate-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Delegate",
    )
    db_session.add_all([host, delegate])
    await db_session.flush()
    invitation = await _invitation_with_host_step(db_session, branch.id, host)
    await _delegate_step(db_session, invitation, delegate, host)

    token = issue_token(delegate)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids


async def test_list_invitations_relevant_to_me_reflects_a_re_delegation(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """checkin-approval-workflow-improvements generalizes delegation to
    support re-delegation (chaining) — `relevantToMe`'s existing delegate
    clause is per-step and reads the step's *current* `delegatedToUserId`,
    so it already generalizes correctly: once a step is re-delegated, the
    new delegate sees the invitation and the superseded one no longer does.
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    first_delegate = UserFactory.build(
        id=uuid.uuid4(),
        email=f"delegate-1-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="First Delegate",
    )
    second_delegate = UserFactory.build(
        id=uuid.uuid4(),
        email=f"delegate-2-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Second Delegate",
    )
    db_session.add_all([host, first_delegate, second_delegate])
    await db_session.flush()
    invitation = await _invitation_with_host_step(db_session, branch.id, host)
    step = await _delegate_step(db_session, invitation, first_delegate, host)

    await InvitationApprovalStepRepository(db_session).delegate_if_eligible(
        step.id,
        delegated_to_user_id=second_delegate.id,
        delegated_by_user_id=first_delegate.id,
        expected_current_delegate_id=first_delegate.id,
    )
    await db_session.commit()

    second_token = issue_token(second_delegate)
    second_response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {second_token}"},
    )
    assert second_response.status_code == 200, second_response.text
    assert invitation.tracking_id in {row["trackingId"] for row in second_response.json()["data"]}

    first_token = issue_token(first_delegate)
    first_response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {first_token}"},
    )
    assert first_response.status_code == 200, first_response.text
    assert invitation.tracking_id not in {
        row["trackingId"] for row in first_response.json()["data"]
    }


async def _invitation_with_role_step(
    db_session: AsyncSession, branch_id: uuid.UUID, role, **overrides
):
    """A `submitted` invitation whose `stepOrder` 1 step is role-identified
    for `role`, with no host step and no delegate — the shape spec.md "A
    role-holder sees an invitation whose current step needs their role"
    keys off.
    """
    overrides.setdefault("status", "submitted")
    overrides.setdefault("approved_at", None)
    invitation = _build_invitation(db_session, branch_id, **overrides)
    db_session.add(invitation)
    await db_session.flush()
    db_session.add(
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            step_order=1,
            approver_role_id=role.id,
            approver_user_id=None,
        )
    )
    await db_session.commit()
    return invitation


def _make_role_holder(db_session: AsyncSession, role, branch_id: uuid.UUID) -> User:
    """A user holding `role` via `UserBranchRole` at `branch_id` — no
    permissions attached, mirroring `relevantToMe`'s "no invitations:view
    required" contract.
    """
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"role-holder-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Role Holder",
        branch_roles=[branch_role],
    )
    db_session.add(test_user)
    return test_user


async def test_list_invitations_relevant_to_me_role_holder_sees_current_step_invitation(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "A role-holder sees an invitation whose
    current step needs their role" — closes the gap where such a user could
    only find the invitation via the unfiltered branch-wide list.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, role)

    role_holder = _make_role_holder(db_session, role, branch.id)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=role_holder.email, tenant_id=tenant.id, user_id=role_holder.id)
    )
    await db_session.commit()

    token = issue_token(role_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids


async def test_list_invitations_relevant_to_me_role_holder_loses_visibility_once_delegated(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "A non-default-role holder loses
    visibility once the step is delegated to someone else"
    (harden-approval-gate-and-narrow-delegate-visibility) — clause (c) now
    requires the current step to be undelegated; a non-default-host-role
    holder who is not the delegate, the resolved host, or a past actor
    loses visibility the moment the step is delegated to someone else. This
    replaces the pre-change assertion that such a role-holder retained
    visibility indefinitely.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, role)

    role_holder = _make_role_holder(db_session, role, branch.id)
    delegate = UserFactory.build(
        id=uuid.uuid4(),
        email=f"delegate-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Delegate",
    )
    db_session.add(delegate)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=role_holder.email, tenant_id=tenant.id, user_id=role_holder.id)
    )
    await db_session.commit()

    step = (
        await db_session.execute(
            select(InvitationApprovalStep).where(
                InvitationApprovalStep.invitation_id == invitation.id
            )
        )
    ).scalar_one()
    await InvitationApprovalStepRepository(db_session).delegate_if_eligible(
        step.id, delegated_to_user_id=delegate.id, delegated_by_user_id=role_holder.id
    )
    await db_session.commit()

    token = issue_token(role_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id not in tracking_ids


async def test_list_invitations_relevant_to_me_default_host_role_keeps_visibility_once_delegated(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "A role-holder keeps seeing the invitation
    once someone else's delegation is assigned" — clause (e) is the one
    exception to clause (c)'s narrowing: every holder of the tenant's
    default host role keeps permanent visibility, even once the ownership
    step is delegated to a specific host who is neither them nor anyone who
    acted on the step.
    """
    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None
    invitation = await _invitation_with_role_step(db_session, branch.id, reception_role)

    role_holder = _make_role_holder(db_session, reception_role, branch.id)
    host = UserFactory.build(
        id=uuid.uuid4(),
        email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Host",
    )
    db_session.add(host)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=role_holder.email, tenant_id=tenant.id, user_id=role_holder.id)
    )
    await db_session.commit()

    step = (
        await db_session.execute(
            select(InvitationApprovalStep).where(
                InvitationApprovalStep.invitation_id == invitation.id
            )
        )
    ).scalar_one()
    await InvitationApprovalStepRepository(db_session).delegate_if_eligible(
        step.id, delegated_to_user_id=host.id, delegated_by_user_id=role_holder.id
    )
    await db_session.commit()

    token = issue_token(role_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids


async def test_list_invitations_relevant_to_me_default_host_role_keeps_visibility_after_approval(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md clause (e) — permanent visibility for every
    default-host-role holder does not depend on the invitation's own
    status either: it still holds once the invitation is fully `approved`.
    """
    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None
    invitation = await _invitation_with_role_step(db_session, branch.id, reception_role)

    role_holder = _make_role_holder(db_session, reception_role, branch.id)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=role_holder.email, tenant_id=tenant.id, user_id=role_holder.id)
    )
    await db_session.commit()

    step = (
        await db_session.execute(
            select(InvitationApprovalStep).where(
                InvitationApprovalStep.invitation_id == invitation.id
            )
        )
    ).scalar_one()
    other_holder = _make_role_holder(db_session, reception_role, branch.id)
    await db_session.commit()
    await InvitationApprovalStepRepository(db_session).approve_if_pending(
        step.id, user_id=other_holder.id
    )
    invitation.status = "approved"
    invitation.approved_at = datetime.now(UTC)
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(role_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids


async def test_list_invitations_relevant_to_me_role_holder_loses_visibility_once_step_acted_on(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "A role-holder loses visibility once the
    step is actually approved or rejected" — clause (c) only matches while
    the role's step is still the current pending one, delegated or not.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, role)

    role_holder = _make_role_holder(db_session, role, branch.id)
    delegate = UserFactory.build(
        id=uuid.uuid4(),
        email=f"delegate-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Delegate",
    )
    db_session.add(delegate)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=role_holder.email, tenant_id=tenant.id, user_id=role_holder.id)
    )
    await db_session.commit()

    step_repo = InvitationApprovalStepRepository(db_session)
    step = (
        await db_session.execute(
            select(InvitationApprovalStep).where(
                InvitationApprovalStep.invitation_id == invitation.id
            )
        )
    ).scalar_one()
    await step_repo.delegate_if_eligible(
        step.id, delegated_to_user_id=delegate.id, delegated_by_user_id=role_holder.id
    )
    await db_session.commit()
    await step_repo.approve_if_pending(step.id, user_id=delegate.id)
    await db_session.commit()

    token = issue_token(role_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id not in tracking_ids


async def test_list_invitations_relevant_to_me_actor_keeps_visibility_after_own_step_approved(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "The caller who personally approved a step
    keeps seeing the invitation forever, via clause (d)"
    (reception-retains-visibility-and-delegation-after-own-step) — unlike
    clause (c), clause (d) does not drop off once the step the caller acted
    on stops being current.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, role)

    role_holder = _make_role_holder(db_session, role, branch.id)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=role_holder.email, tenant_id=tenant.id, user_id=role_holder.id)
    )
    await db_session.commit()

    step = (
        await db_session.execute(
            select(InvitationApprovalStep).where(
                InvitationApprovalStep.invitation_id == invitation.id
            )
        )
    ).scalar_one()
    await InvitationApprovalStepRepository(db_session).approve_if_pending(
        step.id, user_id=role_holder.id
    )
    await db_session.commit()

    token = issue_token(role_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids


async def test_list_invitations_relevant_to_me_non_actor_role_holder_gains_nothing_from_clause_d(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "clause (d) is keyed to the specific person
    who acted, not to a role" — a different holder of the same role, who
    never personally acted on the step, gains no visibility once it's no
    longer current.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, role)

    acting_holder = _make_role_holder(db_session, role, branch.id)
    bystander_holder = _make_role_holder(db_session, role, branch.id)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(
            email=bystander_holder.email, tenant_id=tenant.id, user_id=bystander_holder.id
        )
    )
    await db_session.commit()

    step = (
        await db_session.execute(
            select(InvitationApprovalStep).where(
                InvitationApprovalStep.invitation_id == invitation.id
            )
        )
    ).scalar_one()
    await InvitationApprovalStepRepository(db_session).approve_if_pending(
        step.id, user_id=acting_holder.id
    )
    await db_session.commit()

    token = issue_token(bystander_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id not in tracking_ids


async def test_list_invitations_relevant_to_me_role_holder_wrong_role_sees_nothing(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "A role-holder who is not currently
    authorized on the pending step sees nothing for it".
    """
    step_role = RoleFactory.build(id=uuid.uuid4(), name=f"step-role-{uuid.uuid4().hex[:8]}")
    other_role = RoleFactory.build(id=uuid.uuid4(), name=f"other-role-{uuid.uuid4().hex[:8]}")
    db_session.add_all([step_role, other_role])
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, step_role)

    mismatched_role_holder = _make_role_holder(db_session, other_role, branch.id)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(
            email=mismatched_role_holder.email,
            tenant_id=tenant.id,
            user_id=mismatched_role_holder.id,
        )
    )
    await db_session.commit()

    token = issue_token(mismatched_role_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id not in tracking_ids


async def test_list_invitations_relevant_to_me_excludes_unrelated_caller(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "Caller who is neither host nor delegate
    sees nothing for that invitation" — even one who holds
    `invitations:view` at that branch.
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    invitation = await _invitation_with_host_step(db_session, branch.id, host)

    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id not in tracking_ids


async def test_list_invitations_relevant_to_me_composes_with_status_filter(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "relevantToMe composes with status
    filtering".
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    submitted = await _invitation_with_host_step(
        db_session, branch.id, host, status="submitted", approved_at=None
    )
    denied = await _invitation_with_host_step(
        db_session, branch.id, host, status="denied", approved_at=None
    )

    token = issue_token(host)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true", "status": "submitted"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert submitted.tracking_id in tracking_ids
    assert denied.tracking_id not in tracking_ids


async def test_list_invitations_relevant_to_me_empty_result_is_not_an_error(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    """specs/invitations/spec.md "No relevant invitations returns an empty
    page, not an error" — no `invitations:view` grant needed, and no
    invitation names this caller either.
    """
    token = issue_token(user_without_permissions)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"] == []
    assert body["pagination"]["total"] == 0


async def test_list_invitations_relevant_to_me_ignores_branch_header(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "X-Branch-ID is ignored when relevantToMe
    is set".
    """
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-RELEVANT")
    db_session.add(other_branch)
    await db_session.flush()
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    invitation = await _invitation_with_host_step(db_session, other_branch.id, host)

    token = issue_token(host)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids


async def test_list_invitations_relevant_to_me_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    """testing-standards.md §2 — a caller's relevant-to-me set from one
    tenant's schema must not see another tenant's invitations, even for a
    user id that happens to exist in both.
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    await _invitation_with_host_step(db_session, branch.id, host)

    other_schema = "tenant_other_test_invitation_relevant_to_me"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        rows, total = await InvitationRepository(other_session).list_page(
            branch_scope=None,
            relevant_to_user_id=host.id,
            default_host_role_id=uuid.uuid4(),
            status=None,
            registration_type=None,
            source=None,
            search=None,
            page=1,
            page_size=20,
            sort_by="submitted_at",
            sort_order=SortOrder.desc,
        )
        assert rows == []
        assert total == 0


async def test_list_invitations_relevant_to_me_role_holder_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    """testing-standards.md §2 — the new role-based-current-step-approver
    clause must not leak across tenant schemas either, even when a
    same-named role and the same user id happen to exist in both (roles and
    `UserBranchRole` rows are themselves tenant-scoped tables, per
    `database-architecture.md` §2 — there is nothing shared for a forged or
    coincidental id to reach into).
    """
    role = RoleFactory.build(id=uuid.uuid4(), name="relevant-role-isolation-test")
    db_session.add(role)
    await db_session.flush()
    await _invitation_with_role_step(db_session, branch.id, role)
    role_holder = _make_role_holder(db_session, role, branch.id)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_relevant_to_me_role"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        rows, total = await InvitationRepository(other_session).list_page(
            branch_scope=None,
            relevant_to_user_id=role_holder.id,
            default_host_role_id=uuid.uuid4(),
            status=None,
            registration_type=None,
            source=None,
            search=None,
            page=1,
            page_size=20,
            sort_by="submitted_at",
            sort_order=SortOrder.desc,
        )
        assert rows == []
        assert total == 0


async def test_invitation_list_page_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_listing"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        rows, total = await InvitationRepository(other_session).list_page(
            branch_scope="all",
            status=None,
            registration_type=None,
            source=None,
            search=None,
            page=1,
            page_size=20,
            sort_by="submitted_at",
            sort_order=SortOrder.desc,
        )
        assert rows == []
        assert total == 0


# --- Tenant isolation ---------------------------------------------------------


@pytest.mark.parametrize(
    ("payload_factory", "visitor_file_count"),
    [(_individual_payload, 0), (_group_payload, 2)],
    ids=["individual", "group"],
)
async def test_invitation_repository_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    user: User,
    branch: Branch,
    client: AsyncClient,
    payload_factory,
    visitor_file_count: int,
) -> None:
    token = await _login(client, user.email)
    data = await _create_invitation_success(
        client, token, branch, payload=payload_factory(), visitor_file_count=visitor_file_count
    )

    other_schema = "tenant_other_test_invitations"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await InvitationRepository(other_session).get_by_tracking_id(data["trackingId"])
        assert found is None


# --- Celery task idempotency ---------------------------------------------------
#
# These stub out `tasks.tenant_session_scope` with an in-memory fake rather
# than letting the task open a real connection from `.apply()`'s worker
# thread: a real asyncpg connection opened on that thread's throwaway event
# loop, then returned to the module-level engine's *shared* pool, corrupts it
# for every other test that draws from the same pool afterward ("attached to
# a different loop" on a completely unrelated later query) — a real Celery
# worker process never shares a pool with the process that queued the task,
# so this mirrors that isolation instead of the accidental sharing a test
# thread would introduce.


class _FakeInvitation:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)

    def __getattr__(self, name: str):
        # Falls back to `None` for any attribute a test didn't explicitly
        # set — every real `Invitation` column this module's email-template
        # rendering now reads (`host_id`, `purpose_of_visit`, etc.) is
        # nullable, so `None` is a safe default rather than requiring every
        # existing `_FakeInvitation(...)` call site in this file to list
        # every field it doesn't care about.
        return None


class _FakeScalarResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def first(self):
        # `InvitationRepository.get_location`'s joined select reads a whole
        # (Branch, Department, Building) row.
        return self._value


class _FakeSession:
    def __init__(
        self, invitation, user=None, company=None, location=None, qr_code=None, tenant=None
    ) -> None:
        self._invitation = invitation
        self._user = user
        self._company = company
        self._location = location
        self._qr_code = qr_code
        self._tenant = tenant

    async def get(self, model, id_):
        return self._invitation

    async def execute(self, stmt):
        # Not a real `Select` evaluation — a canned result keyed off which
        # entity the statement targets, so each repository lookup a task
        # makes (`UserRepository.get_active`, `CompanyRepository.
        # get_singleton`, `InvitationRepository.get_location`/`get_qr_code`)
        # gets back the fake row the test actually configured.
        entity = stmt.column_descriptions[0]["entity"]
        if entity is Company:
            return _FakeScalarResult(self._company)
        if entity is Branch:
            return _FakeScalarResult(self._location)
        if entity is InvitationQRCode:
            return _FakeScalarResult(self._qr_code)
        if entity is Tenant:
            return _FakeScalarResult(self._tenant)
        return _FakeScalarResult(self._user)


def _fake_tenant_session_scope(
    invitation, user=None, company=None, location=None, qr_code=None, tenant=None
):
    @asynccontextmanager
    async def _scope(schema_name: str):
        yield _FakeSession(
            invitation,
            user=user,
            company=company,
            location=location,
            qr_code=qr_code,
            tenant=tenant,
        )

    return _scope


async def test_send_approval_notification_skips_when_invitation_missing(monkeypatch) -> None:
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(None))

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "qr_token": "fake-qr-token",
        },
    )
    result.get(propagate=True)
    assert sent == []  # invitation no longer exists — nothing to notify about


async def test_send_approval_notification_exhausted_retries_logs_error(monkeypatch) -> None:
    class _FailingEmailSender:
        async def send(self, **kwargs):
            raise RuntimeError("SMTP is down")

    monkeypatch.setattr(notifications, "email_sender", _FailingEmailSender())
    fake_invitation = _FakeInvitation(
        status="approved",
        tracking_id="INV-TEST0001",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
        primary_contact_phone=None,
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))
    logged = []
    monkeypatch.setattr(tasks.logger, "error", lambda event, **kw: logged.append((event, kw)))
    # `max_retries=0` means the very first failure is already "exhausted", so
    # `.apply()` hits the exhaustion branch immediately instead of actually
    # sleeping through `retry_backoff`'s delay for real retries.
    monkeypatch.setattr(tasks.send_approval_notification, "max_retries", 0)

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "qr_token": "fake-qr-token",
        },
    )
    assert result.failed()
    assert logged and logged[0][0] == "approval_notification_dispatch_exhausted"


async def test_send_host_creation_notification_dispatches_email(monkeypatch) -> None:
    """qr-checkin-scheduling-photo-email spec.md "Creation with a resolved
    host sends the host an email" — exercised directly against the task
    (testing-standards.md §3's "unit-style" tier), same fake session/
    invitation pattern the other task tests above use.
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        tracking_id="INV-TEST0003",
        primary_contact_full_name="Meera Krishnan",
        purpose_of_visit="Interview",
    )
    fake_host = UserFactory.build(id=uuid.uuid4(), email="host@acme-test.example", is_active=True)
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, user=fake_host)
    )

    result = await asyncio.to_thread(
        tasks.send_host_creation_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "host_id": str(fake_host.id),
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert sent[0]["to"] == "host@acme-test.example"
    assert "INV-TEST0003" in sent[0]["body"]


async def test_send_host_creation_notification_skips_when_invitation_missing(monkeypatch) -> None:
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(None))

    result = await asyncio.to_thread(
        tasks.send_host_creation_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "host_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)
    assert sent == []


async def test_send_host_creation_notification_skips_when_host_missing(monkeypatch) -> None:
    """Host deactivated/deleted between enqueue and task execution — no
    email, no error (background-jobs.md §2 idempotency).
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(tracking_id="INV-TEST0004")
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, user=None)
    )

    result = await asyncio.to_thread(
        tasks.send_host_creation_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "host_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)
    assert sent == []


async def test_send_edit_notification_includes_point_of_contact_when_set(monkeypatch) -> None:
    """`edit.html`'s Point-of-Contact row, and the plain-text fallback body,
    both reflect whichever POC is currently resolved on the invitation
    (add-invitation-point-of-contact) — not just whichever visit-detail
    field actually changed in this particular edit.
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        tracking_id="INV-TEST0010",
        purpose_of_visit="Interview",
        preferred_visit_date=date(2026, 9, 15),
        preferred_visit_time=time(17, 46),
        expected_duration="1-hour",
        poc_name="Priya POC",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

    result = await asyncio.to_thread(
        tasks.send_edit_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert "YOUR POINT OF CONTACT" in sent[0]["body"]
    assert "Name: Priya POC" in sent[0]["body"]
    assert sent[0]["html_body"] is not None
    assert "Priya POC" in sent[0]["html_body"]


async def test_send_edit_notification_omits_point_of_contact_when_unset(monkeypatch) -> None:
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        tracking_id="INV-TEST0011",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

    result = await asyncio.to_thread(
        tasks.send_edit_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert "Point of contact" not in sent[0]["body"]
    assert sent[0]["html_body"] is None or "Point of contact" not in sent[0]["html_body"]


async def test_send_poc_creation_notification_includes_visit_details(monkeypatch) -> None:
    """add-invitation-point-of-contact: the newly-named point of contact
    gets the same level of visit detail (duration, department) the
    visitor's own edit-notification email already carries — not just
    tracking id/visitor/purpose — plus the visitor's own contact details
    (phone/email), so the POC can actually reach them about the visit.
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        tracking_id="INV-TEST0012",
        primary_contact_full_name="Meera Krishnan",
        primary_contact_phone="+91 90000 44455",
        primary_contact_email="meera@example.com",
        purpose_of_visit="Interview",
        preferred_visit_date=date(2026, 9, 15),
        preferred_visit_time=time(17, 46),
        expected_duration="1-hour",
        department_to_visit="Engineering",
    )
    fake_poc = UserFactory.build(id=uuid.uuid4(), email="poc@acme-test.example", is_active=True)
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, user=fake_poc)
    )

    result = await asyncio.to_thread(
        tasks.send_poc_creation_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "poc_id": str(fake_poc.id),
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert sent[0]["to"] == "poc@acme-test.example"
    assert "Expected duration: 1-hour" in sent[0]["body"]
    assert "Department: Engineering" in sent[0]["body"]
    assert "Visitor phone: +91 90000 44455" in sent[0]["body"]
    assert "Visitor email: meera@example.com" in sent[0]["body"]
    assert sent[0]["html_body"] is not None
    assert "1-hour" in sent[0]["html_body"]
    assert "Engineering" in sent[0]["html_body"]
    assert "+91 90000 44455" in sent[0]["html_body"]
    assert "meera@example.com" in sent[0]["html_body"]


async def test_send_host_creation_notification_exhausted_retries_logs_error(monkeypatch) -> None:
    class _FailingEmailSender:
        async def send(self, **kwargs):
            raise RuntimeError("SMTP is down")

    monkeypatch.setattr(notifications, "email_sender", _FailingEmailSender())
    fake_invitation = _FakeInvitation(tracking_id="INV-TEST0005")
    fake_host = UserFactory.build(id=uuid.uuid4(), email="host@acme-test.example", is_active=True)
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, user=fake_host)
    )
    logged = []
    monkeypatch.setattr(tasks.logger, "error", lambda event, **kw: logged.append((event, kw)))
    monkeypatch.setattr(tasks.send_host_creation_notification, "max_retries", 0)

    result = await asyncio.to_thread(
        tasks.send_host_creation_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "host_id": str(fake_host.id),
        },
    )
    assert result.failed()
    assert logged and logged[0][0] == "host_creation_notification_dispatch_exhausted"
    assert logged[0][1]["host_id"] == str(fake_host.id)


async def test_smtp_dispatch_failure_logs_host_port_and_exception_type(monkeypatch) -> None:
    """`fix-email-dispatch-diagnosability/design.md` — a dispatch failure now
    logs enough detail (SMTP host/port, the underlying exception's type) to
    root-cause a dev-server-only failure without reproducing it locally,
    mirroring `identity_verification/senders.py`'s existing coverage of the
    same behavior. No recipient address is logged (invitations/tasks.py
    already binds tenant/invitation context for locating the record).
    """

    async def _raise(*args, **kwargs) -> None:
        raise aiosmtplib.SMTPConnectError("Connection refused")

    monkeypatch.setattr(aiosmtplib, "send", _raise)
    monkeypatch.setattr(settings, "smtp_username", "should-never-appear")
    monkeypatch.setattr(settings, "smtp_password", "super-secret-password")  # noqa: S105

    sender = notifications.SmtpEmailSender()
    with capture_logs() as captured, pytest.raises(aiosmtplib.SMTPConnectError):
        await sender.send(to="visitor@example.com", subject="Your visit confirmation", body="body")

    [entry] = [e for e in captured if e["event"] == "smtp_email_dispatch_failed"]
    assert entry["smtp_host"] == settings.smtp_host
    assert entry["smtp_port"] == settings.smtp_port
    assert entry["exception_type"] == "SMTPConnectError"

    log_text = str(captured)
    assert "should-never-appear" not in log_text
    assert "super-secret-password" not in log_text
    assert "visitor@example.com" not in log_text


# --- Real dispatch verification (against DDEV's Mailpit, not a fake sender) ---
#
# Every other task test above monkeypatches `notifications.email_sender` with
# a recording/failing fake — proving the task *calls* the sender correctly,
# not that a real message is actually deliverable. This test leaves
# `email_sender` as the real `SmtpEmailSender` so a genuine `aiosmtplib.send`
# goes out over the loopback SMTP port DDEV intercepts, then asks Mailpit's
# own HTTP API whether the message actually arrived — the same "real
# infrastructure, not mocks" bar this project already holds Postgres to
# (testing-standards.md), applied to the other piece of real infrastructure
# this feature depends on.

_MAILPIT_BASE_URL = "http://localhost:8025/api/v1"
_MAILPIT_API_URL = f"{_MAILPIT_BASE_URL}/messages"


_MAILPIT_ASSET_BASE = "https://vmss-new-api.ddev.site:8443"


def _realistic_email_fakes() -> dict[str, Any]:
    """Org-chart and company rows shaped like real tenant data, so Mailpit
    sends look like production emails rather than bare test stubs
    (serve-email-images-by-url-and-complete-contact design.md Decision 5).
    """
    branch = SimpleNamespace(
        name="Technopark Campus",
        address="Phase 1",
        city="Trivandrum",
        contact_phone="+91 80000 22233",
        contact_email=None,
        contact_person_user_id=None,
    )
    return {
        "company": SimpleNamespace(
            legal_name="Acme Corp", logo_url=None, phone="+91 80 4000 1000", email=None
        ),
        "location": (branch, SimpleNamespace(name="Engineering"), SimpleNamespace(name="Tower A")),
    }


async def _persisted_approved_invitation(
    db_session: AsyncSession, branch: Branch, creator: User, *, qr_token_value: str
) -> Invitation:
    """A real invitation + QR row, so the signed QR URL in the delivered
    email resolves through the public route."""
    invitation = InvitationFactory.build(
        id=uuid.uuid4(),
        branch_id=branch.id,
        created_by_user_id=creator.id,
        status="approved",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(invitation)
    await db_session.flush()
    db_session.add(
        InvitationQRCode(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            qr_token=qr_token_value,
            image_storage_key="k",
        )
    )
    await db_session.commit()
    return invitation


async def _find_mailpit_message(mailpit: AsyncClient, tracking_id: str, recipient: str) -> dict:
    list_response = await mailpit.get(_MAILPIT_API_URL, params={"limit": 50})
    assert list_response.status_code == 200
    matches = [
        m
        for m in list_response.json()["messages"]
        if tracking_id in m["Snippet"] and any(to["Address"] == recipient for to in m["To"])
    ]
    assert len(matches) == 1, (
        f"expected exactly one Mailpit message for {tracking_id}, found {len(matches)}"
    )
    detail_response = await mailpit.get(f"{_MAILPIT_BASE_URL}/message/{matches[0]['ID']}")
    assert detail_response.status_code == 200
    return detail_response.json()


def _image_srcs(html: str) -> list[str]:
    return [html_lib.unescape(src) for src in re.findall(r'<img src="([^"]+)"', html)]


async def _assert_url_images_and_fetch_qr(
    detail: dict, client: AsyncClient, expected_token: str
) -> None:
    # invitations spec "Delivered confirmation has no attachment strip and
    # a working QR URL": no attachments, no inline parts at all.
    assert detail["Attachments"] == []
    assert detail["Inline"] == []
    assert "cid:" not in detail["HTML"]
    srcs = _image_srcs(detail["HTML"])
    assert f"{_MAILPIT_ASSET_BASE}/api/v1/public/email-assets/guestify-logo.png" in srcs
    [qr_src] = [src for src in srcs if "/qr/" in src]
    assert qr_src.startswith(f"{_MAILPIT_ASSET_BASE}/api/v1/public/email-assets/")
    qr_response = await client.get(qr_src.removeprefix(_MAILPIT_ASSET_BASE))
    assert qr_response.status_code == 200
    assert qr_response.headers["content-type"] == "image/png"
    assert qr_response.content == await generate_qr_png(expected_token)


async def test_send_approval_notification_delivers_email_with_qr_via_mailpit(
    monkeypatch,
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    user: User,
) -> None:
    monkeypatch.setattr(settings, "email_asset_base_url", _MAILPIT_ASSET_BASE)
    real = await _persisted_approved_invitation(
        db_session, branch, user, qr_token_value="mailpit-qr-token"
    )
    tracking_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    recipient = f"mailpit-check-{uuid.uuid4().hex[:8]}@example.com"
    fake_invitation = _FakeInvitation(
        id=real.id,
        expires_at=real.expires_at,
        branch_id=branch.id,
        status="approved",
        tracking_id=tracking_id,
        primary_contact_full_name="Meera Krishnan",
        purpose_of_visit="Interview",
        preferred_visit_date=date(2026, 10, 14),
        preferred_visit_time=time(10, 30),
        expected_duration="1 hour",
        poc_name="Priya Nair",
        primary_contact_preferred_contact_method="email",
        primary_contact_email=recipient,
        primary_contact_phone=None,
    )
    # `notifications.email_sender` is deliberately left as the real
    # `SmtpEmailSender` here (unlike every other task test above) so a real
    # SMTP send goes out for Mailpit to actually capture.
    monkeypatch.setattr(
        tasks,
        "tenant_session_scope",
        _fake_tenant_session_scope(fake_invitation, tenant=tenant, **_realistic_email_fakes()),
    )

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": tenant.schema_name,
            "invitation_id": str(real.id),
            "qr_token": "mailpit-qr-token",
        },
    )
    result.get(propagate=True)

    async with AsyncClient() as mailpit:
        detail = await _find_mailpit_message(mailpit, tracking_id, recipient)
    assert detail["Subject"] == "Your visit is confirmed"
    assert detail["From"]["Name"] == "Guestify"
    assert "Your check-in pass" in detail["HTML"]
    for expected in ("Your point of contact", "Priya Nair", "Tower A", "Engineering"):
        assert expected in detail["HTML"], expected
    await _assert_url_images_and_fetch_qr(detail, client, "mailpit-qr-token")
    # Deliberately not deleted from Mailpit afterward — left for a human to
    # inspect via the Mailpit web UI, and harmless to accumulate since each
    # run uses a fresh, unique tracking_id/recipient.


async def test_send_approval_notification_without_asset_base_embeds_only_the_qr(
    monkeypatch,
) -> None:
    """The unconfigured fallback: a text wordmark header (no logo part) and
    the QR as the one inline part, still never an attachment."""
    tracking_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    recipient = f"mailpit-check-{uuid.uuid4().hex[:8]}@example.com"
    fake_invitation = _FakeInvitation(
        id=uuid.uuid4(),
        status="approved",
        tracking_id=tracking_id,
        primary_contact_preferred_contact_method="email",
        primary_contact_email=recipient,
        primary_contact_phone=None,
    )
    monkeypatch.setattr(
        tasks,
        "tenant_session_scope",
        _fake_tenant_session_scope(fake_invitation, **_realistic_email_fakes()),
    )

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(fake_invitation.id),
            "qr_token": "fake-qr-token",
        },
    )
    result.get(propagate=True)

    async with AsyncClient() as mailpit:
        detail = await _find_mailpit_message(mailpit, tracking_id, recipient)
        assert detail["Attachments"] == []
        assert [part["ContentID"] for part in detail["Inline"]] == ["visit-qr@vmss"]
        assert "guestify-logo@vmss" not in detail["HTML"]
        assert 'src="cid:visit-qr@vmss"' in detail["HTML"]
        inline_response = await mailpit.get(
            f"{_MAILPIT_BASE_URL}/message/{detail['ID']}/part/{detail['Inline'][0]['PartID']}"
        )
        qr_image = Image.open(io.BytesIO(inline_response.content))
        qr_image.verify()
        assert inline_response.content == await generate_qr_png("fake-qr-token")


async def test_send_tracking_notification_delivers_email_via_mailpit(monkeypatch) -> None:
    """Same real-SMTP-round-trip bar as
    `test_send_approval_notification_delivers_email_with_qr_via_mailpit`
    above, extended to the submission tracking notification (task 9.1) — the
    "your registration is received" email sent when creation leaves an
    invitation `submitted` rather than immediately `approved`. Unlike the
    approval email, this one carries no QR attachment.
    """
    tracking_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    recipient = f"mailpit-check-{uuid.uuid4().hex[:8]}@example.com"
    fake_invitation = _FakeInvitation(
        status="submitted",
        tracking_id=tracking_id,
        primary_contact_preferred_contact_method="email",
        primary_contact_email=recipient,
        primary_contact_phone=None,
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

    result = await asyncio.to_thread(
        tasks.send_tracking_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)

    async with AsyncClient() as mailpit:
        list_response = await mailpit.get(_MAILPIT_API_URL, params={"limit": 50})
        assert list_response.status_code == 200
        matches = [
            m
            for m in list_response.json()["messages"]
            if tracking_id in m["Snippet"] and any(to["Address"] == recipient for to in m["To"])
        ]
        assert len(matches) == 1, (
            f"expected exactly one Mailpit message for {tracking_id}, found {len(matches)}"
        )
        message_id = matches[0]["ID"]

        detail_response = await mailpit.get(f"{_MAILPIT_BASE_URL}/message/{message_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["Subject"] == "We've received your visit request"
        assert detail["Attachments"] == []
        assert tracking_id in detail["Text"]


async def test_send_denial_notification_delivers_email_via_mailpit(monkeypatch) -> None:
    """Same real-SMTP-round-trip bar as
    `test_send_approval_notification_delivers_email_with_qr_via_mailpit`
    above, extended to the denial notification per design.md Decision 1 —
    "the stub was called correctly" and "an email genuinely arrived" have
    only ever been proven together for the approval path until now.
    """
    tracking_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    recipient = f"mailpit-check-{uuid.uuid4().hex[:8]}@example.com"
    fake_invitation = _FakeInvitation(
        status="denied",
        tracking_id=tracking_id,
        denial_reason="Visitor not on the expected list",
        primary_contact_preferred_contact_method="email",
        primary_contact_email=recipient,
        primary_contact_phone=None,
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

    result = await asyncio.to_thread(
        tasks.send_denial_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)

    async with AsyncClient() as mailpit:
        list_response = await mailpit.get(_MAILPIT_API_URL, params={"limit": 50})
        assert list_response.status_code == 200
        matches = [
            m
            for m in list_response.json()["messages"]
            if tracking_id in m["Snippet"] and any(to["Address"] == recipient for to in m["To"])
        ]
        assert len(matches) == 1, (
            f"expected exactly one Mailpit message for {tracking_id}, found {len(matches)}"
        )
        detail_response = await mailpit.get(f"{_MAILPIT_BASE_URL}/message/{matches[0]['ID']}")
        assert detail_response.status_code == 200
        assert detail_response.json()["Subject"] == "Your visit request wasn't approved"


async def test_send_reschedule_notification_delivers_email_via_mailpit(
    monkeypatch,
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    user: User,
) -> None:
    """Same real-SMTP-round-trip bar, extended to the reschedule
    notification: an approved visit's existing QR (the persisted token) is
    shown again, by signed URL, with nothing attached or inline.
    """
    monkeypatch.setattr(settings, "email_asset_base_url", _MAILPIT_ASSET_BASE)
    real = await _persisted_approved_invitation(
        db_session, branch, user, qr_token_value="persisted-qr-token"
    )
    tracking_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    recipient = f"mailpit-check-{uuid.uuid4().hex[:8]}@example.com"
    fake_invitation = _FakeInvitation(
        id=real.id,
        expires_at=real.expires_at,
        branch_id=branch.id,
        status="approved",
        tracking_id=tracking_id,
        primary_contact_full_name="Meera Krishnan",
        preferred_visit_date=date(2026, 12, 1),
        preferred_visit_time=time(15, 30),
        previous_preferred_visit_date=date(2026, 11, 28),
        previous_preferred_visit_time=time(10, 0),
        poc_name="Priya Nair",
        primary_contact_preferred_contact_method="email",
        primary_contact_email=recipient,
        primary_contact_phone=None,
    )
    fake_qr = InvitationQRCode(
        id=uuid.uuid4(),
        invitation_id=real.id,
        qr_token="persisted-qr-token",
        image_storage_key="k",
    )
    monkeypatch.setattr(
        tasks,
        "tenant_session_scope",
        _fake_tenant_session_scope(
            fake_invitation, qr_code=fake_qr, tenant=tenant, **_realistic_email_fakes()
        ),
    )

    result = await asyncio.to_thread(
        tasks.send_reschedule_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": tenant.schema_name,
            "invitation_id": str(real.id),
        },
    )
    result.get(propagate=True)

    async with AsyncClient() as mailpit:
        detail = await _find_mailpit_message(mailpit, tracking_id, recipient)
    assert detail["Subject"] == "Your visit has been rescheduled"
    assert "Tue, 1 Dec 2026 · 3:30 PM" in detail["Text"]
    assert "Sat, 28 Nov 2026 · 10:00 AM" in detail["Text"]
    assert "Priya Nair" in detail["HTML"]
    await _assert_url_images_and_fetch_qr(detail, client, "persisted-qr-token")


async def test_send_host_creation_notification_delivers_email_via_mailpit(monkeypatch) -> None:
    """Same real-SMTP-round-trip bar, extended to the new host-creation
    email (qr-checkin-scheduling-photo-email/design.md Decision 5) —
    `notifications.email_sender` is deliberately left as the real
    `SmtpEmailSender` so a genuine `aiosmtplib.send` goes out for Mailpit to
    actually capture.
    """
    tracking_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    recipient = f"mailpit-check-{uuid.uuid4().hex[:8]}@example.com"
    fake_invitation = _FakeInvitation(
        tracking_id=tracking_id,
        primary_contact_full_name="Meera Krishnan",
        purpose_of_visit="Interview",
    )
    fake_host = UserFactory.build(id=uuid.uuid4(), email=recipient, is_active=True)
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, user=fake_host)
    )

    result = await asyncio.to_thread(
        tasks.send_host_creation_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "host_id": str(fake_host.id),
        },
    )
    result.get(propagate=True)

    async with AsyncClient() as mailpit:
        list_response = await mailpit.get(_MAILPIT_API_URL, params={"limit": 50})
        assert list_response.status_code == 200
        matches = [
            m
            for m in list_response.json()["messages"]
            if tracking_id in m["Snippet"] and any(to["Address"] == recipient for to in m["To"])
        ]
        assert len(matches) == 1, (
            f"expected exactly one Mailpit message for {tracking_id}, found {len(matches)}"
        )
        detail_response = await mailpit.get(f"{_MAILPIT_BASE_URL}/message/{matches[0]['ID']}")
        assert detail_response.status_code == 200
        assert detail_response.json()["Subject"] == "You've been named host for a visit"


# --- visit-info-lookup-api: optional purposeId/hostId/durationId/departmentId -


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


async def test_create_invitation_with_no_ids_behaves_exactly_as_before(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """spec.md "Submission with no ids behaves exactly as before"."""
    data = await _create_invitation_success(
        client, await _login(client, user.email), branch, payload=_individual_payload()
    )
    assert data["registrationType"] == "individual"


async def test_create_invitation_with_ids_overwrites_free_text_with_canonical_value(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    visit_purpose: VisitPurpose,
    visit_duration: VisitDuration,
    visit_department: Department,
) -> None:
    """spec.md "Submission with an id overwrites free text with the catalog
    value" — a mismatched free-text string is discarded in favor of the
    referenced row's canonical name. `hostId`/`durationId`/`departmentId`
    used to include a host id too, but the host is never client-resolved
    anymore (role-based-invitation-workflow) — see the dedicated
    `test_create_invitation_ignores_supplied_host_fields` below for that.
    """
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["purposeOfVisit"] = "does not match the catalog row"
    payload["visitDetails"]["expectedDuration"] = "nor this"
    payload["visitDetails"]["departmentToVisit"] = "nor this either"
    payload["visitDetails"]["purposeId"] = str(visit_purpose.id)
    payload["visitDetails"]["durationId"] = str(visit_duration.id)
    payload["visitDetails"]["departmentId"] = str(visit_department.id)

    data = await _create_invitation_success(client, token, branch, payload=payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert invitation.purpose_of_visit == visit_purpose.name
    assert invitation.expected_duration == visit_duration.name
    assert invitation.department_to_visit == visit_department.name
    assert invitation.purpose_id == visit_purpose.id
    assert invitation.duration_id == visit_duration.id
    assert invitation.department_id == visit_department.id


async def test_create_invitation_ignores_supplied_host_fields(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    visit_host: User,
) -> None:
    """spec.md "A supplied hostId or hostNameOrEmail is silently ignored" —
    an un-updated client supplying either field no longer resolves a host or
    fails the request; the invitation is created with no host at all.
    """
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["hostId"] = str(visit_host.id)
    payload["visitDetails"]["hostNameOrEmail"] = visit_host.full_name

    data = await _create_invitation_success(client, token, branch, payload=payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert invitation.host_id is None
    assert invitation.host_name_or_email is None


async def test_create_invitation_with_no_department_succeeds_and_leaves_it_unset(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """allow-optional-department-at-creation spec.md "Submission with no
    department succeeds and leaves it unset" — a visitor or staff member
    creating an invitation often doesn't know the receiving organisation's
    internal department, so omitting both `departmentToVisit` and
    `departmentId` no longer fails the request.
    """
    token = await _login(client, user.email)
    payload = _individual_payload()
    del payload["visitDetails"]["departmentToVisit"]

    data = await _create_invitation_success(client, token, branch, payload=payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert invitation.department_to_visit is None
    assert invitation.department_id is None


async def test_create_invitation_never_enqueues_host_email(
    client: AsyncClient,
    user: User,
    branch: Branch,
    visit_host: User,
    monkeypatch,
) -> None:
    """REMOVED spec.md requirement "Invitation Creation Notifies the
    Resolved Host via Email" (role-based-invitation-workflow) — a host is
    never resolved at creation anymore, whether or not a client still
    supplies `hostId`, so this dispatch never fires at creation. See the
    `approvals` capability's "Delegating the Ownership Step Also Resolves
    the Invitation's Host" for the email the actual host now receives
    instead, once delegated.
    """
    calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_host_creation_notification, "delay", lambda **kw: calls.append(kw)
    )

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["hostId"] = str(visit_host.id)
    await _create_invitation_success(client, token, branch, payload=payload)

    assert calls == []


async def test_created_invitation_current_step_id_is_directly_actionable(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    visit_host: User,
    issue_token: Callable[[User], str],
) -> None:
    """add-approval-step-id-and-host-routing — `currentApprovalStep.id` on
    the creation response is the same id `POST /invitations/{id}/approval-
    steps/{stepId}/approve` expects, with no separate lookup needed. Every
    newly created invitation's ownership step is role-identified for the
    tenant's default host role (role-based-invitation-workflow), so a
    holder of that role — e.g. Reception — is the current approver and may
    approve it directly like any other step (`specs/approvals/spec.md`
    "The Ownership Step Is a Plain Role-Identified Step, Approvable
    Directly"). This invitation's category has no configured workflow rules,
    so this one synthetic step is also its *only* step — a single-step,
    reception-only workflow — so approving it directly resolves `hostId` to
    the approving Reception user (see "Approving the Only Step of a
    Single-Step Workflow Also Resolves the Invitation's Host"), the same as
    delegating would.
    """
    # `_default_host_role` (this module's autouse fixture) seeds "reception"
    # with no permissions attached — enough for snapshot logic, not enough
    # to actually approve — so this test grants `invitations:approve` on it
    # explicitly, reusing the global permission row the `user` fixture's
    # own admin permission set already created.
    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None
    permission = (
        await db_session.execute(select(Permission).where(Permission.code == "invitations:approve"))
    ).scalar_one()
    reception_role.permissions.append(permission)
    # Append in-memory too, not just `session.add()` — see
    # `approvals/tests.py::_grant_approve_permission`'s docstring for why
    # the test session's `expire_on_commit=False` makes this necessary.
    branch_role = UserBranchRole(
        id=uuid.uuid4(), user_id=visit_host.id, role_id=reception_role.id, branch_id=branch.id
    )
    visit_host.branch_roles.append(branch_role)
    db_session.add(branch_role)
    await db_session.commit()

    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=_individual_payload())

    assert data["hostId"] is None
    assert data["currentApprovalStep"] is not None
    step_id = data["currentApprovalStep"]["id"]
    assert data["currentApprovalStep"]["approverRoleId"] == str(reception_role.id)
    assert data["currentApprovalStep"]["approverUserId"] is None

    host_token = issue_token(visit_host)
    response = await client.post(
        f"/api/v1/invitations/{data['id']}/approval-steps/{step_id}/approve",
        headers={"Authorization": f"Bearer {host_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "approved"
    assert response.json()["data"]["hostId"] == str(visit_host.id)


async def test_create_invitation_unknown_purpose_id_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Unknown or cross-tenant id is rejected"."""
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["purposeId"] = str(uuid.uuid4())

    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422

    invitations = await InvitationRepository(db_session).list()
    assert invitations == []


async def test_create_invitation_inactive_department_id_rejected(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    visit_department: Department,
) -> None:
    visit_department.is_active = False
    db_session.add(visit_department)
    await db_session.commit()

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["departmentId"] = str(visit_department.id)

    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_cross_tenant_purpose_id_rejected(
    client: AsyncClient,
    user: User,
    branch: Branch,
    make_tenant_schema,
    open_tenant_session,
) -> None:
    """testing-standards.md §2's tenant-isolation case: a `purposeId` valid
    in a different tenant's schema must not resolve here.
    """
    other_schema = "tenant_other_test_visit_info"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        other_purpose = VisitPurposeFactory.build(id=uuid.uuid4(), name="Other Tenant Purpose")
        other_session.add(other_purpose)
        await other_session.commit()

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["purposeId"] = str(other_purpose.id)

    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_walk_in_registration_visit_details_submit_exposes_id_fields() -> None:
    """spec.md "Walk-in registration inherits the same optional fields" —
    guards against a future refactor breaking `registrations.schemas`'s
    re-export of the shared `VisitDetailsSubmit` class (task 6.3).
    """
    from vmss_api.registrations.schemas import VisitDetailsSubmit as WalkInVisitDetailsSubmit

    assert set(WalkInVisitDetailsSubmit.model_fields) >= {
        "purpose_id",
        "host_id",
        "duration_id",
        "department_id",
    }


# --- Manual approval (POST /invitations/{id}/approve) ------------------------


async def _branch_scoped_invitation_approver(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID
) -> User:
    """A caller whose only role grant is `invitations:approve` at
    `branch_id` — the approve-permission counterpart of
    `_branch_scoped_invitation_viewer` above.
    """
    permission = PermissionFactory.build(
        id=uuid.uuid4(), code="invitations:approve", description="invitations:approve"
    )
    role = RoleFactory.build(id=uuid.uuid4(), name="invitations-approver", permissions=[permission])
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"approver-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Invitation Approver",
        branch_roles=[branch_role],
    )
    db_session.add_all([permission, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


async def test_approve_invitation_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted", approved_at=None)
    db_session.add(invitation)
    await db_session.commit()

    approval_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "approved"
    assert data["approvedAt"] is not None
    assert len(approval_calls) == 1

    await db_session.refresh(invitation)
    assert invitation.status == "approved"
    assert invitation.approved_at is not None


async def test_approve_invitation_soft_deleted_branch_succeeds(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """Regression test: approving a `submitted` invitation no longer 404s
    just because its recorded branch was soft-deleted after submission —
    see harden-referential-integrity-and-rbac-gates. The invitation's own
    `branchId` is already-persisted historical data, not something that
    needs to still exist for the approval to go through.
    """
    invitation = _build_invitation(db_session, branch.id, status="submitted", approved_at=None)
    db_session.add(invitation)
    await db_session.execute(
        update(Branch).where(Branch.id == branch.id).values(deleted_at=datetime.now(UTC))
    )
    await db_session.commit()

    approval_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "approved"
    assert data["approvedAt"] is not None
    assert len(approval_calls) == 1

    await db_session.refresh(invitation)
    assert invitation.status == "approved"
    assert invitation.approved_at is not None


async def test_approve_invitation_already_approved_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()
    original_approved_at = invitation.approved_at

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "approved"
    assert invitation.approved_at == original_approved_at


async def test_approve_invitation_rejected_for_workflow_backed_invitation(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """invitation-multi-step-approval spec.md "Blanket approve rejected for
    a workflow-backed invitation" (design.md Decision 3) — an invitation
    with any snapshotted `InvitationApprovalStep` must be approved through
    the step endpoint, never the blanket one.
    """
    invitation = _build_invitation(db_session, branch.id, status="submitted", approved_at=None)
    db_session.add(invitation)
    await db_session.flush()
    role = RoleFactory.build(id=uuid.uuid4(), name="step-approver", permissions=[])
    db_session.add(role)
    await db_session.flush()
    db_session.add(
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(), invitation_id=invitation.id, step_order=1, approver_role_id=role.id
        )
    )
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"


async def test_approve_invitation_rejected_for_host_only_invitation(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """specs/invitations/spec.md "Blanket approve rejected when only a
    host-approval step is snapshotted" (add-approval-step-id-and-host-
    routing) — zero configured workflow rules, but a resolved host still
    snapshots one host-identified step, which must route through the step
    endpoint, not the blanket one.
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    invitation = _build_invitation(
        db_session, branch.id, status="submitted", approved_at=None, host_id=host.id
    )
    db_session.add(invitation)
    await db_session.flush()
    db_session.add(
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            step_order=0,
            approver_role_id=None,
            approver_user_id=host.id,
        )
    )
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"


async def test_approve_invitation_concurrent_requests_transition_exactly_once(
    branch: Branch, tenant: Tenant, db_session: AsyncSession, monkeypatch
) -> None:
    """Regression test for a check-then-act race:
    `invitations/service.py::approve_invitation` used to read
    `invitation.status`, check it, then mutate and commit — two request
    handlers that each independently fetched the same `submitted`
    invitation before either approved it (the shape a real concurrent pair
    of requests produces) could both pass the check and both dispatch a
    notification. Simulated here by calling the service function twice
    against the same stale, pre-approval `invitation` object — neither call
    has seen the other's transition — and asserting the atomic
    conditional-`UPDATE` fix still only transitions and notifies once. See
    codebase-review-and-e2e-scenario-test/design.md.
    """
    invitation = _build_invitation(db_session, branch.id, status="submitted", approved_at=None)
    db_session.add(invitation)
    await db_session.commit()

    approval_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )

    first = await invitations_service.approve_invitation(db_session, invitation, tenant=tenant)
    assert first.status == "approved"

    with pytest.raises(HTTPException) as exc_info:
        await invitations_service.approve_invitation(db_session, invitation, tenant=tenant)
    assert exc_info.value.status_code == 409

    assert len(approval_calls) == 1


async def test_approve_invitation_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    monkeypatch,
    issue_token: Callable[[User], str],
) -> None:
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    invitation = _build_invitation(db_session, branch.id, status="submitted", approved_at=None)
    db_session.add(invitation)
    await db_session.commit()

    approval_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )

    token = issue_token(viewer)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"
    assert approval_calls == []


async def test_approve_invitation_unknown_id_not_found(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{uuid.uuid4()}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_approve_invitation_denied_for_approver_scoped_elsewhere(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """An `invitations:approve` grant at a different branch gets 403, not
    404 — `authorize_branch_id` (the same dependency `POST /invitations`
    uses to resolve a branch id) 403s on no-branch-access, and only 404s
    when the branch itself doesn't exist.
    """
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-APPROVE")
    db_session.add(other_branch)
    await db_session.flush()
    approver = await _branch_scoped_invitation_approver(db_session, tenant, other_branch.id)
    invitation = _build_invitation(db_session, branch.id, status="submitted", approved_at=None)
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(approver)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"


# --- add-invitation-lifecycle-actions ------------------------------------------


async def _branch_scoped_user_with_permission(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID, *, permission_code: str
) -> User:
    """Generic counterpart of `_branch_scoped_invitation_viewer`/`_approver`
    above — a caller whose only role grant is `permission_code` at
    `branch_id`. One helper covers every new permission this capability
    adds instead of a hand-written near-duplicate per code.
    """
    label = permission_code.split(":")[-1]
    permission = PermissionFactory.build(
        id=uuid.uuid4(), code=permission_code, description=permission_code
    )
    role = RoleFactory.build(id=uuid.uuid4(), name=f"invitations-{label}", permissions=[permission])
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"{label}-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name=f"Invitation {label.title()}",
        branch_roles=[branch_role],
    )
    db_session.add_all([permission, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


# --- GET /invitations/{id} ------------------------------------------------------


async def test_get_invitation_detail_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="approved")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/invitations/{invitation.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == str(invitation.id)
    assert data["branchId"] == str(branch.id)
    assert data["status"] == "approved"
    assert data["watchlistFlagged"] is False
    assert data["badgeNumber"] is None
    assert data["visitors"] == []
    assert data["vehicles"] == []


async def test_get_invitation_detail_surfaces_fetchable_primary_contact_photo_url(
    client: AsyncClient, user: User, branch: Branch, tenant: Tenant, db_session: AsyncSession
) -> None:
    """add-avatar-upload-and-verify-image-storage spec.md "Every photo URL
    returned by any invitation response ... SHALL be a fetchable HTTP URL"
    — `GET /invitations/{id}`'s own `primaryContactPhotoUrl` specifically
    (as opposed to a nested visitor's `photoUrl`), fetched end to end.
    """
    photo_bytes = _jpeg_bytes()
    photo_key = await storage.save(tenant.id, "invitations/photos", photo_bytes, "image/jpeg")
    invitation = _build_invitation(
        db_session, branch.id, status="approved", primary_contact_photo_storage_key=photo_key
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/invitations/{invitation.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    photo_url = response.json()["data"]["primaryContactPhotoUrl"]
    assert photo_url is not None

    photo_response = await client.get(photo_url)
    assert photo_response.status_code == 200
    assert photo_response.content == photo_bytes


async def test_get_invitation_detail_surfaces_resolved_host_as_host_id(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """specs/invitations/spec.md "Invitation Output Surfaces the Resolved
    Host as hostId" — detail lookup exposes `hostId` when the host resolved
    at submission, and null when it did not.
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    resolved = _build_invitation(db_session, branch.id, status="approved", host_id=host.id)
    unresolved = _build_invitation(db_session, branch.id, status="approved", host_id=None)
    db_session.add_all([resolved, unresolved])
    await db_session.commit()

    token = await _login(client, user.email)

    response = await client.get(
        f"/api/v1/invitations/{resolved.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["hostId"] == str(host.id)

    response = await client.get(
        f"/api/v1/invitations/{unresolved.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["hostId"] is None


async def test_get_invitation_detail_includes_resolved_branch_detail(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """enrich-invitation-checkin-and-detail-views spec.md "QR Check-In,
    Check-Out, and Detail Responses Surface Resolved Branch, Building, and
    Department" — branch detail is always present, in addition to the
    existing raw `branchId`.
    """
    invitation = _build_invitation(db_session, branch.id, status="approved")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/invitations/{invitation.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["branchId"] == str(branch.id)
    assert data["branch"] == {
        "id": str(branch.id),
        "name": branch.name,
        "code": branch.code,
        "address": branch.address,
        "city": branch.city,
    }


async def test_get_invitation_detail_includes_building_and_department_when_resolvable(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    building = BuildingFactory.build(id=uuid.uuid4(), branch_id=branch.id)
    db_session.add(building)
    await db_session.flush()
    floor = FloorFactory.build(id=uuid.uuid4(), building_id=building.id, floor_number=1)
    db_session.add(floor)
    await db_session.flush()
    department = DepartmentFactory.build(id=uuid.uuid4(), branch_id=branch.id, floor_id=floor.id)
    db_session.add(department)
    await db_session.flush()
    invitation = _build_invitation(
        db_session, branch.id, status="approved", department_id=department.id
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/invitations/{invitation.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["building"] == {
        "id": str(building.id),
        "name": building.name,
        "code": building.code,
    }
    assert data["department"] == {
        "id": str(department.id),
        "name": department.name,
        "code": department.code,
    }


async def test_get_invitation_detail_building_and_department_null_when_no_department_id(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", department_to_visit="Finance", department_id=None
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/invitations/{invitation.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["building"] is None
    assert data["department"] is None
    assert data["departmentToVisit"] == "Finance"


async def test_get_invitation_detail_building_null_when_department_has_no_floor(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    department = DepartmentFactory.build(id=uuid.uuid4(), branch_id=branch.id, floor_id=None)
    db_session.add(department)
    await db_session.flush()
    invitation = _build_invitation(
        db_session, branch.id, status="approved", department_id=department.id
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/invitations/{invitation.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["building"] is None
    assert data["department"] == {
        "id": str(department.id),
        "name": department.name,
        "code": department.code,
    }


async def test_get_invitation_detail_includes_id_proof_url_with_documents_view(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """enrich-invitation-checkin-and-detail-views spec.md "Primary Contact
    and Visitor ID-Proof Documents Are Surfaced Only to Callers Holding
    documents:view" — a caller holding both `invitations:view` and
    `documents:view` sees `idProofUrl` for the primary contact and every
    visitor.
    """
    viewer = await _branch_scoped_invitation_and_documents_viewer(db_session, tenant, branch.id)
    co_visitor = InvitationVisitorFactory.build(id=uuid.uuid4())
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        registration_type="group",
        visitors=[co_visitor],
        primary_contact_id_proof_type="Passport",
        primary_contact_id_proof_storage_key="vmss:tenant:invitations/id_proofs:primary.jpg",
    )
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(viewer)
    response = await client.get(
        f"/api/v1/invitations/{invitation.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["primaryContactIdProofType"] == invitation.primary_contact_id_proof_type
    assert data["primaryContactIdProofUrl"] is not None
    [visitor_out] = data["visitors"]
    assert visitor_out["idProofType"] == co_visitor.id_proof_type
    assert visitor_out["idProofUrl"] is not None


async def test_get_invitation_detail_omits_id_proof_url_without_documents_view(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """Counterpart of the test above — a caller holding `invitations:view`
    but not `documents:view` succeeds with `idProofUrl` `null` for the
    primary contact and every visitor, while `idProofType` (not gated) is
    still present.
    """
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    co_visitor = InvitationVisitorFactory.build(id=uuid.uuid4())
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        registration_type="group",
        visitors=[co_visitor],
        primary_contact_id_proof_type="Passport",
        primary_contact_id_proof_storage_key="vmss:tenant:invitations/id_proofs:primary.jpg",
    )
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(viewer)
    response = await client.get(
        f"/api/v1/invitations/{invitation.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["primaryContactIdProofType"] == invitation.primary_contact_id_proof_type
    assert data["primaryContactIdProofUrl"] is None
    [visitor_out] = data["visitors"]
    assert visitor_out["idProofType"] == co_visitor.id_proof_type
    assert visitor_out["idProofUrl"] is None


async def test_get_invitation_detail_unknown_id_not_found(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/invitations/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_get_invitation_detail_denied_for_viewer_scoped_elsewhere(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-DETAIL")
    db_session.add(other_branch)
    await db_session.flush()
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, other_branch.id)
    invitation = _build_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(viewer)
    response = await client.get(
        f"/api/v1/invitations/{invitation.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# --- PATCH /invitations/{id}/deny -----------------------------------------------


async def test_deny_invitation_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    denial_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_denial_notification, "delay", lambda **kw: denial_calls.append(kw)
    )

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/deny",
        json={"reason": "Host unavailable"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "denied"
    assert len(denial_calls) == 1

    await db_session.refresh(invitation)
    assert invitation.status == "denied"
    assert invitation.denial_reason == "Host unavailable"
    assert invitation.denied_at is not None


async def test_deny_invitation_missing_reason_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/deny",
        json={"reason": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"


async def test_deny_invitation_non_submitted_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/deny",
        json={"reason": "Too late"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "approved"


async def test_deny_invitation_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(viewer)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/deny",
        json={"reason": "No"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"


# --- add-public-checkin-endpoint: PATCH /api/v2/invitations/{trackingId}/check-in --
# checkin-approval-workflow-improvements removed the legacy, staff-
# authenticated `PATCH /api/v1/invitations/{id}/check-in` outright — this v2,
# tracking-ID-keyed, public endpoint is now the single canonical staff/desk
# check-in endpoint (spec.md "Staff Check-In Has One Canonical Endpoint"), so
# it carries every full-detail-response assertion the old v1 tests used to.


async def test_public_check_in_by_tracking_id_success(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "checked_in"

    await db_session.refresh(invitation)
    assert invitation.status == "checked_in"
    assert invitation.checked_in_at is not None
    assert invitation.checked_in_by_user_id is None


async def test_public_check_in_by_tracking_id_masks_custom_file_upload_field_raw_storage_key(
    client: AsyncClient, user: User, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """add-generic-custom-field-file-url-resolution, extended to the public
    tracking-ID check-in response — same posture as the QR counterpart
    (`test_qr_check_in_response_masks_custom_file_upload_field_raw_storage_
    key`): a `file_upload`-typed custom field's raw storage key must never
    reach this unauthenticated caller.
    """
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="visitor_info", key="pic", field_type="file_upload"
    )
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        primary_contact_custom_field_values={
            field["id"]: "vmss:tenant:invitations/custom-fields:primary-pic.jpg"
        },
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 200
    assert _custom_field_value(response.json()["data"]["customFields"], field["id"]) is None


async def test_public_check_in_non_approved_rejected(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"


async def test_public_check_in_watchlist_flagged_blocked(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        watchlist_flagged=True,
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "approved"


async def test_public_check_in_re_entry_after_staff_checkout_succeeds(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """allow-multiple-checkins: `checked_out` is no longer terminal for the
    tracking-ID/staff check-in path — mirrors the QR path's already-proven
    cycling (`test_qr_check_in_and_check_out_full_lifecycle`).
    """
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        check_in_status="unused",
    )
    db_session.add(invitation)
    await db_session.commit()

    first_check_in = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert first_check_in.status_code == 200

    token = await _login(client, user.email)
    check_out = await client.patch(
        f"/api/v1/invitations/{invitation.id}/check-out",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert check_out.status_code == 200

    await db_session.refresh(invitation)
    assert invitation.status == "checked_out"
    assert invitation.check_in_status == "checked_out"

    re_entry = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert re_entry.status_code == 200
    assert re_entry.json()["data"]["status"] == "checked_in"

    await db_session.refresh(invitation)
    assert invitation.status == "checked_in"
    assert invitation.check_in_status == "checked_in"
    assert invitation.checked_in_at is not None


async def test_public_check_in_two_full_round_trips_succeed(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """allow-multiple-checkins: the cycle isn't a one-time exception — it
    repeats indefinitely, same as the QR path.
    """
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        check_in_status="unused",
    )
    db_session.add(invitation)
    await db_session.commit()
    token = await _login(client, user.email)

    for _ in range(2):
        check_in = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
        assert check_in.status_code == 200
        check_out = await client.patch(
            f"/api/v1/invitations/{invitation.id}/check-out",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert check_out.status_code == 200

    final_check_in = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert final_check_in.status_code == 200

    await db_session.refresh(invitation)
    assert invitation.status == "checked_in"
    assert invitation.check_in_status == "checked_in"


async def test_public_check_in_while_already_checked_in_is_idempotent_success(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """A repeat check-in call while already `checked_in` is a no-op
    success, not an error — no re-stamped `checkedInAt`, matching
    `test_qr_check_in_while_already_checked_in_is_idempotent_success`'s
    rule for the other endpoint.
    """
    original_checked_in_at = datetime.now(UTC)
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        approved_at=datetime.now(UTC),
        checked_in_at=original_checked_in_at,
        check_in_status="checked_in",
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "checked_in"

    await db_session.refresh(invitation)
    assert invitation.status == "checked_in"
    assert invitation.checked_in_at == original_checked_in_at


async def test_public_check_in_watchlist_flagged_still_blocked_after_checkout(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """allow-multiple-checkins: the watchlist gate survives the widened
    re-entry eligibility check — a flagged visitor who somehow completed one
    cycle can't just re-enter through the same relaxed `checked_out` gate.
    """
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="checked_out",
        approved_at=datetime.now(UTC),
        checked_in_at=datetime.now(UTC),
        checked_out_at=datetime.now(UTC),
        check_in_status="checked_out",
        watchlist_flagged=True,
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "checked_out"


async def test_check_in_via_tracking_id_then_qr_is_idempotent_no_double_write(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """Cross-path check: a visitor checked in via the tracking-ID/staff
    endpoint who is then "checked in" again via QR gets a 200 idempotent
    no-op from the QR endpoint too (both endpoints share the same
    already-checked-in rule) — not a second write, not a re-stamped
    `checkedInAt`. Before `check_in_if_eligible` wrote `check_in_status`,
    this cross-endpoint call used to slip through as a genuine second
    check-in; this asserts it's recognized as the same already-checked-in
    visitor and produces no state change.
    """
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        check_in_status="unused",
        preferred_visit_date=None,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(invitation)
    await db_session.commit()

    check_in = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert check_in.status_code == 200

    await db_session.refresh(invitation)
    assert invitation.check_in_status == "checked_in"  # the cross-path fix
    first_checked_in_at = invitation.checked_in_at

    qr = qr_token.encrypt_invitation_token(invitation.id)
    second_check_in = await client.patch(f"/api/v2/invitations/qr/{qr}/check-in")
    assert second_check_in.status_code == 200
    assert second_check_in.json()["message"] == "Verification passed"

    await db_session.refresh(invitation)
    assert invitation.check_in_status == "checked_in"
    assert invitation.checked_in_at == first_checked_in_at  # no re-stamp, no second write


async def test_check_in_via_qr_then_tracking_id_is_idempotent_no_double_write(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """The reverse direction of the same cross-path check: checking in via
    QR, then calling the tracking-ID endpoint, is also a 200 idempotent
    no-op rather than a second write.
    """
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    qr = qr_token.encrypt_invitation_token(invitation.id)

    check_in = await client.patch(f"/api/v2/invitations/qr/{qr}/check-in")
    assert check_in.status_code == 200

    await db_session.refresh(invitation)
    first_checked_in_at = invitation.checked_in_at

    second_check_in = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert second_check_in.status_code == 200
    assert second_check_in.json()["data"]["status"] == "checked_in"

    await db_session.refresh(invitation)
    assert invitation.check_in_status == "checked_in"
    assert invitation.checked_in_at == first_checked_in_at  # no re-stamp, no second write


async def test_public_check_in_unknown_tracking_id_not_found(
    client: AsyncClient, tenant: Tenant
) -> None:
    response = await client.patch("/api/v2/invitations/INV-DEADBEEF/check-in")
    assert response.status_code == 404


async def test_public_check_in_idempotency_key_replay(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    headers = {"Idempotency-Key": "public-checkin-key-1"}
    first = await client.patch(
        f"/api/v2/invitations/{invitation.tracking_id}/check-in", headers=headers
    )
    second = await client.patch(
        f"/api/v2/invitations/{invitation.tracking_id}/check-in", headers=headers
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


async def test_public_check_in_rate_limit_trips(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    """Mirrors `test_track_rate_limit_trips` — `slowapi`'s `Limiter` is
    disabled in the test environment (`core/rate_limit.py`), flipped on here
    for just this one test.
    """
    monkeypatch.setattr(limiter, "enabled", True)
    responses = [await client.patch("/api/v2/invitations/INV-DEADBEEF/check-in") for _ in range(25)]
    assert any(r.status_code == 429 for r in responses)


async def test_public_check_in_writes_audit_entry_with_no_actor(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 200

    audit_stmt = select(AuditLog).where(
        AuditLog.action == "invitation_checked_in_public",
        AuditLog.entity_id == invitation.id,
    )
    [entry] = (await db_session.execute(audit_stmt)).scalars().all()
    assert entry.actor_user_id is None
    assert entry.entity_type == "Invitation"


async def test_public_check_in_succeeds_after_watchlist_override(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """The watchlist-override action itself stays staff-authenticated
    (`POST /api/v1/invitations/{id}/watchlist-override`, unaffected by this
    change); check-in now happens through the canonical v2 endpoint.
    """
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        watchlist_flagged=True,
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    override_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/watchlist-override",
        json={"reason": "Confirmed false positive"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert override_response.status_code == 200

    check_in_response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert check_in_response.status_code == 200
    assert check_in_response.json()["data"]["status"] == "checked_in"

    await db_session.refresh(invitation)
    assert invitation.watchlist_flagged is False
    assert invitation.status == "checked_in"


async def test_public_check_in_response_includes_full_invitation_detail(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Successful check-in response includes visitor and host
    detail" — the canonical v2 endpoint's response matches the public
    tracking lookup's field set, not just the thin `InvitationOut` shape.
    """
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["primaryContactFullName"] == invitation.primary_contact_full_name
    assert data["hostNameOrEmail"] == invitation.host_name_or_email
    assert data["purposeOfVisit"] == invitation.purpose_of_visit
    assert data["departmentToVisit"] == invitation.department_to_visit
    assert data["expectedDuration"] == invitation.expected_duration
    assert data["additionalNotes"] == invitation.additional_notes
    assert data["carriedItems"] == invitation.carried_items
    assert data["id"] == str(invitation.id)
    assert data["trackingId"] == invitation.tracking_id
    assert data["status"] == "checked_in"


async def test_public_check_in_response_includes_point_of_contact(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """add-invitation-point-of-contact: the public check-in response
    carries `pocUserId`/`pocRoleId`/`pocName` the same way it already
    carries `hostId`/`hostNameOrEmail` — whoever scans the visitor in can
    see who to actually reach about the visit's logistics.
    """
    poc_user = UserFactory.build(id=uuid.uuid4(), email="poc-checkin@acme-test.example")
    db_session.add(poc_user)
    await db_session.flush()
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        poc_user_id=poc_user.id,
        poc_name="Priya POC",
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pocUserId"] == str(poc_user.id)
    assert data["pocRoleId"] is None
    assert data["pocName"] == "Priya POC"


async def test_public_check_in_response_omits_out_of_scope_new_fields(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """enrich-invitation-checkin-and-detail-views proposal.md "Out of
    scope, unchanged": `PATCH /api/v2/invitations/{trackingId}/check-in`
    is public/unauthenticated with no permission to gate anything by, so
    it must never gain `branch`/`building`/`department` or an ID-proof
    document field — those are exclusive to `GET /invitations/{id}` (and,
    for branch/building/department only, the QR check-in/check-out
    responses).
    """
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 200
    data = response.json()["data"]
    for key in ("branch", "building", "department", "primaryContactIdProofType"):
        assert key not in data
    for visitor_out in data["visitors"]:
        assert "idProofUrl" not in visitor_out


async def test_track_by_tracking_id_omits_out_of_scope_new_fields(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """Same scope guard as the check-in test above, for the public
    tracking lookup (`GET /invitations/track`).
    """
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": invitation.tracking_id}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    for key in ("branch", "building", "department", "primaryContactIdProofType"):
        assert key not in data
    for visitor_out in data["visitors"]:
        assert "idProofUrl" not in visitor_out


async def test_track_by_tracking_id_includes_point_of_contact(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """add-invitation-point-of-contact: the public tracking-by-ID lookup
    carries `pocUserId`/`pocRoleId`/`pocName`, matching `hostNameOrEmail`'s
    existing presence on this schema.
    """
    poc_user = UserFactory.build(id=uuid.uuid4(), email="poc-track@acme-test.example")
    db_session.add(poc_user)
    await db_session.flush()
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        poc_user_id=poc_user.id,
        poc_name="Priya POC",
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": invitation.tracking_id}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pocUserId"] == str(poc_user.id)
    assert data["pocRoleId"] is None
    assert data["pocName"] == "Priya POC"


async def test_public_check_in_response_includes_group_co_visitors(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        registration_type="group",
    )
    db_session.add(invitation)
    await db_session.flush()
    co_visitor = InvitationVisitorFactory.build(
        id=uuid.uuid4(), invitation_id=invitation.id, full_name="Alexander Pierce"
    )
    db_session.add(co_visitor)
    await db_session.commit()
    db_session.expire(invitation, attribute_names=["visitors"])

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 200
    visitors = response.json()["data"]["visitors"]
    assert len(visitors) == 1
    assert visitors[0]["fullName"] == "Alexander Pierce"


async def test_public_check_in_response_includes_declared_vehicles(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.flush()
    vehicle = InvitationVehicleFactory.build(
        id=uuid.uuid4(), invitation_id=invitation.id, license_plate="KA-01-AB-1234"
    )
    db_session.add(vehicle)
    await db_session.commit()
    db_session.expire(invitation, attribute_names=["vehicles"])

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 200
    vehicles = response.json()["data"]["vehicles"]
    assert len(vehicles) == 1
    assert vehicles[0]["licensePlate"] == "KA-01-AB-1234"


async def test_public_check_in_individual_registration_has_empty_visitor_list(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        registration_type="individual",
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["visitors"] == []
    assert data["vehicles"] == []


async def test_public_check_in_response_omits_staff_only_internals(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Response omits staff-only internals" — branch/creator/
    badge/watchlist fields stay exclusive to `GET /invitations/{id}`.
    """
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 200
    data = response.json()["data"]
    for staff_only_field in (
        "branchId",
        "createdByUserId",
        "badgeNumber",
        "badgeIssuedAt",
        "badgeReprintCount",
        "watchlistFlagged",
        "watchlistOverrideAt",
        "watchlistOverrideReason",
        "watchlistOverrideByUserId",
    ):
        assert staff_only_field not in data


async def test_public_check_in_rejected_response_discloses_no_invitation_detail(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Rejected check-in discloses no invitation detail" — a 409
    (not currently `approved`) carries only the existing generic failure
    message.
    """
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 409
    body = response.json()
    assert "data" not in body
    assert body["success"] is False


async def test_v1_check_in_route_removed(client: AsyncClient, user: User, branch: Branch) -> None:
    """spec.md "Legacy v1 check-in route no longer exists" —
    checkin-approval-workflow-improvements removes the route outright."""
    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{uuid.uuid4()}/check-in",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# --- add-qr-checkin-security: token encryption -------------------------------
# Unit-style, no database — mirrors core/tests.py's coverage of
# core/encryption.py's own Fernet round-trip/tamper/not-configured cases
# (testing-standards.md §3).


def test_qr_token_round_trips() -> None:
    invitation_id = uuid.uuid4()
    token = qr_token.encrypt_invitation_token(invitation_id)
    assert token != str(invitation_id)
    assert qr_token.decrypt_invitation_token(token) == invitation_id


def test_qr_token_tampered_token_returns_none() -> None:
    token = qr_token.encrypt_invitation_token(uuid.uuid4())
    tampered = token[:-4] + ("A" if token[-4] != "A" else "B") + token[-3:]
    assert qr_token.decrypt_invitation_token(tampered) is None


def test_qr_token_malformed_input_returns_none() -> None:
    assert qr_token.decrypt_invitation_token("not-a-real-token") is None


def test_qr_token_without_key_configured_raises_loudly(monkeypatch) -> None:
    monkeypatch.setattr(settings, "qr_token_encryption_key", None)
    qr_token._fernet.cache_clear()
    with pytest.raises(qr_token.QrTokenEncryptionKeyNotConfigured):
        qr_token.encrypt_invitation_token(uuid.uuid4())


# --- add-qr-checkin-security: QR check-in ------------------------------------
# The encrypted token doesn't need a persisted `InvitationQRCode` row to be
# scanned — `service.check_in_by_qr_token` decrypts straight to an
# `invitation_id` and looks it up directly — so these tests build the
# invitation via the usual factory and derive the token with
# `qr_token.encrypt_invitation_token` directly, the same way the
# tracking-ID tests above use `invitation.tracking_id` directly.


def _approved_invitation(db_session: AsyncSession, branch_id: uuid.UUID, **overrides):
    overrides.setdefault("status", "approved")
    overrides.setdefault("approved_at", datetime.now(UTC))
    overrides.setdefault("check_in_status", "unused")
    overrides.setdefault("expires_at", datetime.now(UTC) + timedelta(hours=1))
    # `InvitationFactory` (no default of its own for this nullable column)
    # generates a random `preferred_visit_date`, which could land in the
    # future and spuriously trip the new scheduled-date QR check-in gate
    # (qr-checkin-scheduling-photo-email) for every test in this module that
    # doesn't care about that dimension. Pinned to `None` here so those tests
    # keep exercising expiry-only gating; tests of the new behavior below
    # override it explicitly.
    overrides.setdefault("preferred_visit_date", None)
    return _build_invitation(db_session, branch_id, **overrides)


async def test_qr_check_in_and_check_out_full_lifecycle(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """checkin-approval-workflow-improvements split the old toggling
    endpoint into two explicit ones (spec.md "QR Check-In Endpoint
    Transitions an Eligible Visitor to Checked-In" / "QR Check-Out
    Endpoint Transitions a Checked-In Visitor to Checked-Out") — the
    underlying cycling `checkInStatus` model is unchanged, only the
    client now states its intent via which URL it calls.
    """
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    check_in = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert check_in.status_code == 200
    body = check_in.json()
    assert body["message"] == "Verification passed"
    assert body["data"]["checkInStatus"] == "checked_in"
    assert body["data"]["primaryContactFullName"] == invitation.primary_contact_full_name

    await db_session.refresh(invitation)
    assert invitation.check_in_status == "checked_in"
    assert invitation.status == "checked_in"  # mirrored, per design.md "kept parallel"
    assert invitation.checked_in_at is not None

    check_out = await client.patch(f"/api/v2/invitations/qr/{token}/check-out")
    assert check_out.status_code == 200
    assert check_out.json()["message"] == "Checked out successfully"

    await db_session.refresh(invitation)
    assert invitation.check_in_status == "checked_out"
    assert invitation.status == "checked_out"
    assert invitation.checked_out_at is not None

    # `checked_out` is not a dead end — a visitor may have multiple entry
    # points during one visit (design.md "checkInStatus cycles
    # indefinitely"), so a further scan re-admits rather than rejecting.
    re_entry = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert re_entry.status_code == 200
    assert re_entry.json()["message"] == "Verification passed"
    assert re_entry.json()["data"]["checkInStatus"] == "checked_in"

    await db_session.refresh(invitation)
    assert invitation.check_in_status == "checked_in"
    assert invitation.status == "checked_in"

    second_exit = await client.patch(f"/api/v2/invitations/qr/{token}/check-out")
    assert second_exit.status_code == 200
    assert second_exit.json()["message"] == "Checked out successfully"

    await db_session.refresh(invitation)
    assert invitation.check_in_status == "checked_out"
    assert invitation.status == "checked_out"


async def test_qr_check_in_while_already_checked_in_is_idempotent_success(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """Revises spec.md "Calling check-in while already checked in is
    rejected": the check-in endpoint still doesn't toggle to checked-out on
    a repeat scan, but a repeat scan is now a 200 idempotent no-op (same
    "Verification passed" message, no re-stamped `checkedInAt`) rather than
    a 409 — the caller still uses the check-out endpoint to actually exit.
    """
    checked_in_at = datetime.now(UTC)
    invitation = _approved_invitation(
        db_session, branch.id, check_in_status="checked_in", checked_in_at=checked_in_at
    )
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 200
    assert response.json()["message"] == "Verification passed"

    await db_session.refresh(invitation)
    assert invitation.check_in_status == "checked_in"
    assert invitation.checked_in_at == checked_in_at


async def test_qr_check_out_while_not_checked_in_rejected(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Calling check-out on a visitor who isn't checked in is
    rejected".
    """
    invitation = _approved_invitation(db_session, branch.id, check_in_status="unused")
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-out")
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.check_in_status == "unused"


async def test_qr_check_in_response_includes_group_co_visitors(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """qr-checkin-full-registration-detail spec.md "A group registration's
    co-visitors are all present" — the success response's visitor list
    isn't just the primary contact.
    """
    invitation = _approved_invitation(db_session, branch.id, registration_type="group")
    db_session.add(invitation)
    await db_session.flush()
    co_visitor = InvitationVisitorFactory.build(
        id=uuid.uuid4(), invitation_id=invitation.id, full_name="Alexander Pierce"
    )
    db_session.add(co_visitor)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 200
    visitors = response.json()["data"]["visitors"]
    assert len(visitors) == 1
    assert visitors[0]["fullName"] == "Alexander Pierce"


async def test_qr_check_in_response_includes_declared_vehicles(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """qr-checkin-full-registration-detail spec.md "Declared vehicles are
    present".
    """
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.flush()
    vehicle = InvitationVehicleFactory.build(
        id=uuid.uuid4(), invitation_id=invitation.id, license_plate="KA-01-AB-1234"
    )
    db_session.add(vehicle)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 200
    vehicles = response.json()["data"]["vehicles"]
    assert len(vehicles) == 1
    assert vehicles[0]["licensePlate"] == "KA-01-AB-1234"


async def test_qr_check_in_individual_registration_has_empty_visitor_list(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """qr-checkin-full-registration-detail: an individual registration
    (the common case, no co-visitors) gets an empty list, not an error
    and not an omitted field.
    """
    invitation = _approved_invitation(db_session, branch.id, registration_type="individual")
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["visitors"] == []
    assert data["vehicles"] == []


async def test_qr_check_in_response_includes_captured_photos(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Captured photos are included when present" — the primary
    contact's and a visitor's photo, when captured at registration, are
    surfaced on the QR check-in response.
    """
    invitation = _approved_invitation(
        db_session,
        branch.id,
        registration_type="group",
        primary_contact_photo_storage_key="vmss:tenant:invitations/photos:primary.jpg",
    )
    db_session.add(invitation)
    await db_session.flush()
    co_visitor = InvitationVisitorFactory.build(
        id=uuid.uuid4(),
        invitation_id=invitation.id,
        full_name="Alexander Pierce",
        photo_storage_key="vmss:tenant:invitations/photos:visitor.jpg",
    )
    db_session.add(co_visitor)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["primaryContactPhotoUrl"] is not None
    assert data["visitors"][0]["photoUrl"] is not None


async def test_qr_check_in_response_omits_photo_url_when_absent(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Missing photos are represented as null, not omitted or
    errored".
    """
    invitation = _approved_invitation(db_session, branch.id, registration_type="individual")
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 200
    assert response.json()["data"]["primaryContactPhotoUrl"] is None


async def test_qr_check_out_response_includes_captured_photos(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Successful check-out response carries the same detail
    shape as check-in" — including captured photos.
    """
    invitation = _approved_invitation(
        db_session,
        branch.id,
        check_in_status="checked_in",
        primary_contact_photo_storage_key="vmss:tenant:invitations/photos:primary.jpg",
    )
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-out")
    assert response.status_code == 200
    assert response.json()["data"]["primaryContactPhotoUrl"] is not None


async def test_qr_check_in_response_includes_id_proof_type_but_never_a_document_url(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """enrich-invitation-checkin-and-detail-views spec.md "QR Check-In
    Response Surfaces Full Invitation Detail" — `idProofType` is present
    for the primary contact and every visitor, but no ID-proof document
    image/URL field is present anywhere in the response, since this
    endpoint has no authenticated caller to check `documents:view` against.
    Asserts the *key* is absent, not just `null`, to catch a schema
    regression (design.md Decision 3/Risk).
    """
    invitation = _approved_invitation(db_session, branch.id, registration_type="group")
    db_session.add(invitation)
    await db_session.flush()
    co_visitor = InvitationVisitorFactory.build(id=uuid.uuid4(), invitation_id=invitation.id)
    db_session.add(co_visitor)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["primaryContactIdProofType"] == invitation.primary_contact_id_proof_type
    assert "primaryContactIdProofUrl" not in data
    [visitor_out] = data["visitors"]
    assert visitor_out["idProofType"] == co_visitor.id_proof_type
    assert "idProofUrl" not in visitor_out


async def test_qr_check_in_response_masks_custom_file_upload_field_raw_storage_key(
    client: AsyncClient, user: User, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """add-generic-custom-field-file-url-resolution, extended to the public
    QR check-in response: a `file_upload`-typed custom field is present as
    an entry (unlike the removed `idProofUrl` above, there's no dedicated
    schema field to omit — it lives inside the generic
    `customFields` array) but its *value* must never be the raw storage
    key `create_invitation` persisted, since this endpoint has no
    authenticated caller to check `documents:view` against — same posture
    as `test_qr_check_in_response_includes_id_proof_type_but_never_a_
    document_url`.
    """
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="visitor_info", key="pic", field_type="file_upload"
    )
    invitation = _approved_invitation(
        db_session,
        branch.id,
        primary_contact_custom_field_values={
            field["id"]: "vmss:tenant:invitations/custom-fields:primary-pic.jpg"
        },
    )
    db_session.add(invitation)
    await db_session.commit()
    qr_check_in_token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{qr_check_in_token}/check-in")
    assert response.status_code == 200
    assert _custom_field_value(response.json()["data"]["customFields"], field["id"]) is None


async def test_qr_check_in_and_check_out_response_include_resolved_branch_building_department(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """enrich-invitation-checkin-and-detail-views spec.md "QR Check-In,
    Check-Out, and Detail Responses Surface Resolved Branch, Building, and
    Department".
    """
    building = BuildingFactory.build(id=uuid.uuid4(), branch_id=branch.id)
    db_session.add(building)
    await db_session.flush()
    floor = FloorFactory.build(id=uuid.uuid4(), building_id=building.id, floor_number=2)
    db_session.add(floor)
    await db_session.flush()
    department = DepartmentFactory.build(id=uuid.uuid4(), branch_id=branch.id, floor_id=floor.id)
    db_session.add(department)
    await db_session.flush()
    invitation = _approved_invitation(db_session, branch.id, department_id=department.id)
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["branch"] == {
        "id": str(branch.id),
        "name": branch.name,
        "code": branch.code,
        "address": branch.address,
        "city": branch.city,
    }
    assert data["building"] == {
        "id": str(building.id),
        "name": building.name,
        "code": building.code,
    }
    assert data["department"] == {
        "id": str(department.id),
        "name": department.name,
        "code": department.code,
    }

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-out")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["branch"]["id"] == str(branch.id)
    assert data["building"]["id"] == str(building.id)
    assert data["department"]["id"] == str(department.id)


async def test_qr_check_in_response_includes_point_of_contact(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """add-invitation-point-of-contact: the QR check-in/out response
    carries `pocUserId`/`pocRoleId`/`pocName`, matching `hostId`/
    `hostNameOrEmail`'s existing presence on this schema.
    """
    poc_role = RoleFactory.build(id=uuid.uuid4(), name="qr-poc-role", permissions=[])
    db_session.add(poc_role)
    await db_session.flush()
    invitation = _approved_invitation(
        db_session, branch.id, poc_role_id=poc_role.id, poc_name="Front Desk"
    )
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pocRoleId"] == str(poc_role.id)
    assert data["pocUserId"] is None
    assert data["pocName"] == "Front Desk"


async def test_qr_check_in_entry_after_expiry_rejected(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _approved_invitation(
        db_session, branch.id, expires_at=datetime.now(UTC) - timedelta(hours=1)
    )
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 410

    await db_session.refresh(invitation)
    assert invitation.check_in_status == "unused"


async def test_qr_check_in_re_entry_after_expiry_rejected(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "QR Check-In Enforces Invitation Expiry on Every Entry" —
    the expiry check applies to a re-entry from `checked_out` exactly the
    same way it applies to the very first entry from `unused`.
    """
    invitation = _approved_invitation(
        db_session,
        branch.id,
        status="checked_out",
        check_in_status="checked_out",
        checked_in_at=datetime.now(UTC) - timedelta(hours=2),
        checked_out_at=datetime.now(UTC) - timedelta(hours=1, minutes=30),
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 410

    await db_session.refresh(invitation)
    assert invitation.check_in_status == "checked_out"


async def test_qr_check_in_before_scheduled_date_rejected(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """qr-checkin-scheduling-photo-email spec.md "Entry scan before the
    scheduled visit date is rejected" — distinct 425 status, distinguishable
    from the 410 the expiry check above returns.
    """
    invitation = _approved_invitation(
        db_session, branch.id, preferred_visit_date=date.today() + timedelta(days=1)
    )
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 425

    await db_session.refresh(invitation)
    assert invitation.check_in_status == "unused"


async def test_qr_check_in_on_scheduled_date_succeeds(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Entry scan on the scheduled visit date succeeds regardless
    of time of day" — the gate is date-only, so today's date is eligible
    the moment it arrives, not just after a specific time.
    """
    invitation = _approved_invitation(db_session, branch.id, preferred_visit_date=date.today())
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 200
    assert response.json()["data"]["checkInStatus"] == "checked_in"


async def test_qr_check_in_after_scheduled_date_succeeds(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """A scheduled date in the past doesn't block check-in — only a future
    one does (unchanged behavior once the scheduled date has arrived).
    """
    invitation = _approved_invitation(
        db_session, branch.id, preferred_visit_date=date.today() - timedelta(days=1)
    )
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 200


async def test_qr_check_in_no_scheduled_date_falls_back_to_expiry_only(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Entry scan with no scheduled visit date set falls back to
    expiry-only gating" — an invitation with `preferredVisitDate` unset
    (nullable) is never rejected as too early.
    """
    invitation = _approved_invitation(db_session, branch.id, preferred_visit_date=None)
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 200


async def test_qr_check_out_after_expiry_still_succeeds(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _approved_invitation(
        db_session,
        branch.id,
        status="checked_in",
        check_in_status="checked_in",
        checked_in_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-out")
    assert response.status_code == 200
    assert response.json()["message"] == "Checked out successfully"


async def test_qr_check_in_tampered_token_rejected(client: AsyncClient, tenant: Tenant) -> None:
    token = qr_token.encrypt_invitation_token(uuid.uuid4())
    tampered = token[:-4] + ("A" if token[-4] != "A" else "B") + token[-3:]

    response = await client.patch(f"/api/v2/invitations/qr/{tampered}/check-in")
    assert response.status_code == 400


async def test_qr_check_in_valid_token_unknown_invitation_rejected(
    client: AsyncClient, tenant: Tenant
) -> None:
    """Decryption succeeds (this token was genuinely issued by this key) but
    no such invitation exists — folded into the same 400 as a tampered
    token (spec.md "with no invitation detail disclosed"), not a 404 that
    would confirm the id was well-formed but absent.
    """
    token = qr_token.encrypt_invitation_token(uuid.uuid4())
    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 400


async def test_qr_check_in_watchlist_flagged_blocked(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _approved_invitation(db_session, branch.id, watchlist_flagged=True)
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.check_in_status == "unused"


async def test_qr_check_in_not_yet_approved_rejected(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="submitted",
        check_in_status="unused",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 400

    await db_session.refresh(invitation)
    assert invitation.check_in_status == "unused"


async def test_qr_check_in_idempotency_key_replay(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    headers = {"Idempotency-Key": "qr-checkin-key-1"}
    first = await client.patch(f"/api/v2/invitations/qr/{token}/check-in", headers=headers)
    second = await client.patch(f"/api/v2/invitations/qr/{token}/check-in", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()

    await db_session.refresh(invitation)
    # The replay must not have advanced past the cached entry response.
    assert invitation.check_in_status == "checked_in"


async def test_qr_check_in_rate_limit_trips(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    monkeypatch.setattr(limiter, "enabled", True)
    bogus_token = qr_token.encrypt_invitation_token(uuid.uuid4())
    responses = [
        await client.patch(f"/api/v2/invitations/qr/{bogus_token}/check-in") for _ in range(25)
    ]
    assert any(r.status_code == 429 for r in responses)


async def test_qr_check_in_writes_audit_entry_with_no_actor(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert response.status_code == 200

    audit_stmt = select(AuditLog).where(
        AuditLog.action == "invitation_qr_checked_in",
        AuditLog.entity_id == invitation.id,
    )
    [entry] = (await db_session.execute(audit_stmt)).scalars().all()
    assert entry.actor_user_id is None
    assert entry.entity_type == "Invitation"


async def test_qr_check_out_writes_audit_entry_with_no_actor(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _approved_invitation(db_session, branch.id, check_in_status="checked_in")
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    response = await client.patch(f"/api/v2/invitations/qr/{token}/check-out")
    assert response.status_code == 200

    audit_stmt = select(AuditLog).where(
        AuditLog.action == "invitation_qr_checked_out",
        AuditLog.entity_id == invitation.id,
    )
    [entry] = (await db_session.execute(audit_stmt)).scalars().all()
    assert entry.actor_user_id is None
    assert entry.entity_type == "Invitation"


async def test_qr_check_in_repository_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    """testing-standards.md §2 — the QR endpoint itself doesn't carry a
    tenant claim yet (design.md's confirmed Non-Goal), so this exercises
    the repository method directly: a session bound to a different
    tenant's schema must not see this invitation, the same guarantee the
    tracking-ID path's own isolation test already covers.
    """
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_qr_checkin"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).check_in_by_qr_if_eligible(
            invitation.id, today_local=date.today()
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.check_in_status == "unused"


async def test_get_location_repository_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    """testing-standards.md §2 — `InvitationRepository.get_location` must
    resolve `Branch` (and, transitively, `Department`/`Building`) against
    the session's own bound tenant schema, never a different one, even
    when the same id exists as a row in both (`enrich-invitation-checkin-
    and-detail-views/design.md` Decision 5). Also guards the `documents:view`
    permission gate's underlying data: a resolved `idProofUrl` is only ever
    built from data the caller's own tenant session can see in the first
    place.
    """
    other_schema = "tenant_other_test_invitation_get_location"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        other_branch = Branch(id=branch.id, name="Other Tenant Branch", code="OTHER-LOC")
        other_session.add(other_branch)
        await other_session.commit()

        resolved_branch, resolved_department, resolved_building = await InvitationRepository(
            other_session
        ).get_location(branch_id=branch.id, department_id=None)
        assert resolved_branch.name == "Other Tenant Branch"
        assert resolved_department is None
        assert resolved_building is None


# --- PATCH /invitations/{id}/check-out ------------------------------------------


async def test_check_out_invitation_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        approved_at=datetime.now(UTC),
        checked_in_at=datetime.now(UTC),
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/check-out",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "checked_out"

    await db_session.refresh(invitation)
    assert invitation.status == "checked_out"
    assert invitation.checked_out_at is not None
    assert invitation.checked_out_by_user_id == user.id


async def test_check_out_invitation_non_checked_in_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/check-out",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "approved"


async def test_check_out_invitation_idempotency_key_replay(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        approved_at=datetime.now(UTC),
        checked_in_at=datetime.now(UTC),
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "checkout-key-1"}

    first = await client.patch(f"/api/v1/invitations/{invitation.id}/check-out", headers=headers)
    second = await client.patch(f"/api/v1/invitations/{invitation.id}/check-out", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


async def test_check_out_invitation_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        approved_at=datetime.now(UTC),
        checked_in_at=datetime.now(UTC),
    )
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(viewer)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/check-out",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    await db_session.refresh(invitation)
    assert invitation.status == "checked_in"


# --- PATCH /invitations/{id}/reschedule -----------------------------------------


async def test_reschedule_invitation_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """specs/invitations/spec.md "Reschedule Dispatches a Notification to
    the Primary Contact" — a successful reschedule enqueues the
    notification task with the invitation's own id.
    """
    reschedule_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_reschedule_notification, "delay", lambda **kw: reschedule_calls.append(kw)
    )

    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/reschedule",
        json={"preferredVisitDate": "2026-12-01", "preferredVisitTime": "15:30:00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "submitted"

    await db_session.refresh(invitation)
    assert invitation.preferred_visit_date.isoformat() == "2026-12-01"
    assert invitation.preferred_visit_time.isoformat() == "15:30:00"

    assert len(reschedule_calls) == 1
    assert reschedule_calls[0]["invitation_id"] == str(invitation.id)


async def test_reschedule_invitation_captures_previous_schedule_and_audit_diff(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """`add-reschedule-history/design.md`: a reschedule snapshots the
    invitation's prior date/time onto `previous_preferred_visit_date`/`_time`,
    bumps `rescheduled_at`/`reschedule_count`, and records the before/after
    values on the `invitation_rescheduled` audit-log entry — none of which
    existed before this change (the old date/time was simply overwritten).
    """
    monkeypatch.setattr(tasks.send_reschedule_notification, "delay", lambda **kw: None)

    invitation = _build_invitation(
        db_session,
        branch.id,
        status="submitted",
        preferred_visit_date=date(2026, 10, 1),
        preferred_visit_time=time(9, 0, 0),
        reschedule_count=0,
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/reschedule",
        json={"preferredVisitDate": "2026-12-01", "preferredVisitTime": "15:30:00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    await db_session.refresh(invitation)
    assert invitation.previous_preferred_visit_date.isoformat() == "2026-10-01"
    assert invitation.previous_preferred_visit_time.isoformat() == "09:00:00"
    assert invitation.reschedule_count == 1
    assert invitation.rescheduled_at is not None

    detail_response = await client.get(
        f"/api/v1/invitations/{invitation.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["previousPreferredVisitDate"] == "2026-10-01"
    assert detail["previousPreferredVisitTime"] == "09:00:00"
    assert detail["rescheduleCount"] == 1
    assert detail["rescheduledAt"] is not None

    audit_stmt = select(AuditLog).where(
        AuditLog.action == "invitation_rescheduled",
        AuditLog.entity_id == invitation.id,
    )
    [entry] = (await db_session.execute(audit_stmt)).scalars().all()
    assert entry.diff == {
        "before": {"preferredVisitDate": "2026-10-01", "preferredVisitTime": "09:00:00"},
        "after": {"preferredVisitDate": "2026-12-01", "preferredVisitTime": "15:30:00"},
    }


async def test_reschedule_invitation_after_check_in_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    reschedule_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_reschedule_notification, "delay", lambda **kw: reschedule_calls.append(kw)
    )

    invitation = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        approved_at=datetime.now(UTC),
        checked_in_at=datetime.now(UTC),
    )
    db_session.add(invitation)
    await db_session.commit()
    original_date = invitation.preferred_visit_date

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/reschedule",
        json={"preferredVisitDate": "2026-12-01", "preferredVisitTime": "15:30:00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.preferred_visit_date == original_date
    assert reschedule_calls == []


async def test_reschedule_invitation_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    reschedule_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_reschedule_notification, "delay", lambda **kw: reschedule_calls.append(kw)
    )

    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(viewer)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/reschedule",
        json={"preferredVisitDate": "2026-12-01", "preferredVisitTime": "15:30:00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert reschedule_calls == []


async def test_send_reschedule_notification_routes_to_sms_when_preferred(monkeypatch) -> None:
    """specs/invitations/spec.md "Successful reschedule notifies the
    primary contact by SMS when preferred" — exercised directly against
    the task (`testing-standards.md` §3's "unit-style" tier), mirroring
    `test_send_approval_notification_exhausted_retries_logs_error`'s fake
    session/invitation pattern rather than a real Celery/DB round trip.
    """
    sms_sent: list[dict] = []

    class _RecordingSmsSender:
        async def send(self, **kwargs):
            sms_sent.append(kwargs)

    email_sent: list[dict] = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            email_sent.append(kwargs)

    monkeypatch.setattr(notifications, "sms_sender", _RecordingSmsSender())
    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        tracking_id="INV-TEST0002",
        primary_contact_full_name="Asha Rao",
        preferred_visit_date=date(2026, 12, 1),
        preferred_visit_time=time(15, 30),
        primary_contact_preferred_contact_method="sms",
        primary_contact_email=None,
        primary_contact_phone="+919876543210",
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

    result = await asyncio.to_thread(
        tasks.send_reschedule_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)

    assert email_sent == []
    assert len(sms_sent) == 1
    assert sms_sent[0]["to"] == "+919876543210"
    assert sms_sent[0]["template"] == SmsTemplate.visit_rescheduled
    assert sms_sent[0]["variables"] == [
        "Asha Rao",
        "INV-TEST0002",
        "01 Dec 2026 15:30",
        "Reception",
    ]


async def test_send_reschedule_notification_routes_to_whatsapp_when_preferred(
    monkeypatch,
) -> None:
    """specs/whatsapp-notifications "Reschedule by WhatsApp": one WhatsApp
    template message, no email and no SMS.
    """
    sent: dict[str, list[dict]] = {"whatsapp": [], "sms": [], "email": []}

    def _recorder(channel: str):
        class _Recorder:
            async def send(self, **kwargs):
                sent[channel].append(kwargs)

        return _Recorder()

    monkeypatch.setattr(notifications, "whatsapp_sender", _recorder("whatsapp"))
    monkeypatch.setattr(notifications, "sms_sender", _recorder("sms"))
    monkeypatch.setattr(notifications, "email_sender", _recorder("email"))
    fake_invitation = _FakeInvitation(
        tracking_id="INV-TEST0003",
        preferred_visit_date="2026-12-01",
        preferred_visit_time="15:30:00",
        primary_contact_preferred_contact_method="whatsapp",
        primary_contact_email=None,
        primary_contact_phone="9876543210",
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

    result = await asyncio.to_thread(
        tasks.send_reschedule_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)

    assert sent["email"] == [] and sent["sms"] == []
    [call] = sent["whatsapp"]
    assert call["to"] == "9876543210"
    assert call["template"] == WhatsAppTemplate.visit_rescheduled
    # `visitor_updates` template: name, tracking ID, when, point of contact.
    assert len(call["variables"]) == 4
    assert call["variables"][1] == "INV-TEST0003"


def test_whatsapp_preference_requires_a_phone() -> None:
    from vmss_api.invitations.schemas import ContactMethod, _require_contact_for_method

    with pytest.raises(ValueError, match="phone is required"):
        _require_contact_for_method("a@b.com", None, ContactMethod.whatsapp)
    _require_contact_for_method(None, "9876543210", ContactMethod.whatsapp)


# --- PATCH /invitations/{id}/extend ---------------------------------------------


async def test_extend_invitation_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=now,
        expires_at=now + timedelta(days=1),
    )
    db_session.add(invitation)
    await db_session.commit()
    new_expiry = now + timedelta(days=7)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/extend",
        json={"expiresAt": new_expiry.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    await db_session.refresh(invitation)
    assert invitation.expires_at == new_expiry


async def test_extend_invitation_earlier_expiry_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    original_expiry = now + timedelta(days=7)
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=now, expires_at=original_expiry
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/extend",
        json={"expiresAt": (now + timedelta(days=1)).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    await db_session.refresh(invitation)
    assert invitation.expires_at == original_expiry


async def test_extend_invitation_ineligible_status_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/extend",
        json={"expiresAt": (datetime.now(UTC) + timedelta(days=30)).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


async def test_extend_invitation_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(viewer)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/extend",
        json={"expiresAt": (datetime.now(UTC) + timedelta(days=30)).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# --- PATCH /invitations/{id}/edit (role-based-invitation-workflow) --------------


async def test_edit_invitation_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """spec.md "Authorized edit changes multiple visit-detail fields at
    once".
    """
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    email_calls: list[dict] = []
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: email_calls.append(kw))

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={
            "preferredVisitDate": "2026-10-01",
            "expectedDuration": "2-3 hours",
            "additionalNotes": "Bring a laptop",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    await db_session.refresh(invitation)
    assert str(invitation.preferred_visit_date) == "2026-10-01"
    assert invitation.expected_duration == "2-3 hours"
    assert invitation.additional_notes == "Bring a laptop"
    assert len(email_calls) == 1
    assert email_calls[0]["invitation_id"] == str(invitation.id)


async def test_edit_invitation_updates_custom_fields(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """`customFields` on edit overwrites the stored answers so `GET` returns
    them, and an invalid answer is rejected.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    field = await _create_and_publish_custom_field(
        client,
        token,
        branch,
        step_key="visit_details",
        key="floor_pref",
        field_type="dropdown_select",
        options=["Ground", "First"],
    )
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: None)

    url = f"/api/v1/invitations/{invitation.id}/edit"
    bad = await client.patch(
        url, json={"customFields": [{"fieldId": field["id"], "value": "Roof"}]}, headers=headers
    )
    assert bad.status_code == 422, bad.text

    ok = await client.patch(
        url, json={"customFields": [{"fieldId": field["id"], "value": "First"}]}, headers=headers
    )
    assert ok.status_code == 200, ok.text
    await db_session.refresh(invitation)
    assert invitation.custom_field_values[field["id"]] == "First"


async def test_edit_invitation_updates_checked_out_at(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    checked_in_at = datetime.now(UTC) - timedelta(hours=3)
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="checked_out",
        checked_in_at=checked_in_at,
        checked_out_at=datetime.now(UTC) - timedelta(hours=1),
        checked_out_automatically=True,
    )
    db_session.add(invitation)
    await db_session.commit()
    email_calls: list[dict] = []
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: email_calls.append(kw))

    new_time = datetime.now(UTC) - timedelta(hours=2)
    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"checkedOutAt": new_time.isoformat(), "additionalNotes": "ignored"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    await db_session.refresh(invitation)
    assert invitation.checked_out_at == new_time
    assert invitation.checked_out_automatically is False
    assert invitation.checked_out_by_user_id == user.id
    assert invitation.additional_notes != "ignored"
    assert email_calls == []


async def test_edit_invitation_rejects_invalid_checked_out_at(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="checked_out",
        checked_in_at=datetime.now(UTC) - timedelta(hours=3),
        checked_out_at=datetime.now(UTC) - timedelta(hours=1),
    )
    approved = _build_invitation(db_session, branch.id, status="approved")
    db_session.add_all([invitation, approved])
    await db_session.commit()
    invitation_id, approved_id = invitation.id, approved.id
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}

    for when in (datetime.now(UTC) + timedelta(hours=1), datetime.now(UTC) - timedelta(hours=5)):
        response = await client.patch(
            f"/api/v1/invitations/{invitation_id}/edit",
            json={"checkedOutAt": when.isoformat()},
            headers=headers,
        )
        assert response.status_code == 422, response.text

    response = await client.patch(
        f"/api/v1/invitations/{approved_id}/edit",
        json={"checkedOutAt": datetime.now(UTC).isoformat()},
        headers=headers,
    )
    assert response.status_code == 409, response.text


async def test_edit_invitation_resolves_catalog_ids(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    visit_purpose: VisitPurpose,
    visit_duration: VisitDuration,
    visit_department: Department,
    monkeypatch,
) -> None:
    """Same catalog-id-overwrites-free-text behavior creation already has,
    scoped to just the fields supplied.
    """
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: None)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={
            "purposeId": str(visit_purpose.id),
            "durationId": str(visit_duration.id),
            "departmentId": str(visit_department.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    await db_session.refresh(invitation)
    assert invitation.purpose_id == visit_purpose.id
    assert invitation.purpose_of_visit == visit_purpose.name
    assert invitation.duration_id == visit_duration.id
    assert invitation.expected_duration == visit_duration.name
    assert invitation.department_id == visit_department.id
    assert invitation.department_to_visit == visit_department.name


async def test_edit_invitation_sets_a_previously_unset_department(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
) -> None:
    """allow-optional-department-at-creation spec.md "An unset department is
    later filled in via edit" — an invitation created with no department
    (per this change) can have it set afterward through the existing edit
    endpoint, exactly like any other eligible invitation.
    """
    invitation = _build_invitation(
        db_session, branch.id, status="submitted", department_to_visit=None, department_id=None
    )
    db_session.add(invitation)
    await db_session.commit()
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: None)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"departmentToVisit": "Human Resources"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    await db_session.refresh(invitation)
    assert invitation.department_to_visit == "Human Resources"


async def test_edit_invitation_rejects_visitor_personal_fields(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Visitor personal fields and visitor category are rejected"."""
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"primaryContactFullName": "Someone Else"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    await db_session.refresh(invitation)
    assert invitation.primary_contact_full_name != "Someone Else"


async def test_edit_invitation_rejects_visitor_category_id(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"visitorCategoryId": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_edit_invitation_rejects_host_fields(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Host fields are rejected" — host reassignment must go
    through the delegation endpoint instead.
    """
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"hostId": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    await db_session.refresh(invitation)
    assert invitation.host_id is None


async def test_edit_invitation_ineligible_status_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="denied")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"additionalNotes": "Too late"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


async def test_edit_invitation_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(viewer)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"additionalNotes": "Not allowed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_edit_invitation_unknown_id_not_found(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{uuid.uuid4()}/edit",
        json={"additionalNotes": "Anything"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_edit_invitation_notifies_resolved_host(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """spec.md "Edit while a host is resolved also notifies the host"."""
    host = _make_host(db_session)
    db_session.add(host)
    await db_session.flush()
    invitation = _build_invitation(db_session, branch.id, status="submitted", host_id=host.id)
    db_session.add(invitation)
    await db_session.commit()

    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: None)
    push_calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        push_calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"additionalNotes": "Updated"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert len(push_calls) == 1
    assert push_calls[0]["user_id"] == host.id


# --- PATCH /invitations/{id}/edit: point of contact (add-invitation-point-of-contact)


async def test_edit_invitation_sets_point_of_contact_to_user(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """`pocUserId` resolves to a specific person, distinct from `hostId` —
    settable directly, any time, by a caller holding `invitations:approve`
    (the `user` fixture is a company-wide admin holding every permission).
    Notifies the newly-named POC by push and email, on top of the always-
    fired visitor edit-notification email.
    """
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    poc_user = UserFactory.build(
        id=uuid.uuid4(), email="poc-person@acme-test.example", full_name="Priya POC"
    )
    db_session.add(poc_user)
    await db_session.commit()

    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: None)
    push_calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        push_calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)
    email_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_poc_creation_notification, "delay", lambda **kw: email_calls.append(kw)
    )

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"pocUserId": str(poc_user.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["pocUserId"] == str(poc_user.id)
    assert response.json()["data"]["pocRoleId"] is None
    assert response.json()["data"]["pocName"] == "Priya POC"

    await db_session.refresh(invitation)
    assert invitation.poc_user_id == poc_user.id
    assert invitation.poc_role_id is None
    assert invitation.poc_name == "Priya POC"
    assert len(push_calls) == 1
    assert push_calls[0]["user_id"] == poc_user.id
    assert len(email_calls) == 1
    assert email_calls[0]["poc_id"] == str(poc_user.id)


async def test_edit_invitation_sets_point_of_contact_to_role(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """`pocRoleId` broadcasts to every holder of that role at the
    invitation's branch (push only — no specific person to email, same as a
    role-identified approval step has no email counterpart).
    """
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    poc_role = RoleFactory.build(id=uuid.uuid4(), name="front-desk-poc", permissions=[])
    db_session.add(poc_role)
    await db_session.commit()

    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: None)
    role_push_calls: list[dict] = []

    async def _fake_notify_role_at_branch(*args, **kwargs):
        role_push_calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_role_at_branch", _fake_notify_role_at_branch)
    email_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_poc_creation_notification, "delay", lambda **kw: email_calls.append(kw)
    )

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"pocRoleId": str(poc_role.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["pocRoleId"] == str(poc_role.id)
    assert response.json()["data"]["pocUserId"] is None
    assert response.json()["data"]["pocName"] == "front-desk-poc"

    await db_session.refresh(invitation)
    assert invitation.poc_role_id == poc_role.id
    assert invitation.poc_user_id is None
    assert len(role_push_calls) == 1
    assert role_push_calls[0]["role_id"] == poc_role.id
    assert len(email_calls) == 0


async def test_edit_invitation_poc_both_fields_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"pocUserId": str(uuid.uuid4()), "pocRoleId": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_edit_invitation_poc_unknown_user_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"pocUserId": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    await db_session.refresh(invitation)
    assert invitation.poc_user_id is None


async def test_edit_invitation_poc_unknown_role_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"pocRoleId": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    await db_session.refresh(invitation)
    assert invitation.poc_role_id is None


async def test_edit_invitation_poc_requires_approve_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """Holding `invitations:edit` alone (this endpoint's own gate) is not
    enough to set the point of contact — `invitations:approve` is required
    in addition, checked in the service layer.
    """
    editor = await _branch_scoped_invitation_editor(db_session, tenant, branch.id)
    poc_user = UserFactory.build(id=uuid.uuid4(), email="poc-candidate@acme-test.example")
    db_session.add(poc_user)
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(editor)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"pocUserId": str(poc_user.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    await db_session.refresh(invitation)
    assert invitation.poc_user_id is None


async def test_edit_invitation_poc_rejected_mid_workflow(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """`invitations/service.py::_poc_eligible` — a workflow-backed
    invitation not yet at its final approval level rejects a
    point-of-contact edit with 409, even from a caller holding
    `invitations:approve` (this endpoint's own permission gate for POC).
    The frontend already disables the field in this state, but the API
    must not trust that.
    """
    category = VisitorCategoryFactory.build(
        id=uuid.uuid4(), name="Two Step POC Category", code="TWO-STEP-POC-CAT"
    )
    approver_role = RoleFactory.build(id=uuid.uuid4(), name="two-step-poc-approver", permissions=[])
    db_session.add_all([category, approver_role])
    await db_session.flush()
    db_session.add_all(
        [
            ApprovalWorkflowRuleFactory.build(
                id=uuid.uuid4(),
                visitor_category_id=category.id,
                step_order=1,
                approver_role_id=approver_role.id,
            ),
            ApprovalWorkflowRuleFactory.build(
                id=uuid.uuid4(),
                visitor_category_id=category.id,
                step_order=2,
                approver_role_id=approver_role.id,
            ),
        ]
    )
    await db_session.commit()

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitorCategoryId"] = str(category.id)
    data = await _create_invitation_success(client, token, branch, payload=payload)
    poc_user = UserFactory.build(id=uuid.uuid4(), email="poc-mid-workflow@acme-test.example")
    db_session.add(poc_user)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/invitations/{data['id']}/edit",
        json={"pocUserId": str(poc_user.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    invitation = await InvitationRepository(db_session).get(uuid.UUID(data["id"]))
    assert invitation is not None
    assert invitation.poc_user_id is None


async def test_edit_invitation_poc_allowed_at_final_approval_level(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """Once the invitation's only remaining pending step is its last
    snapshotted one, `_poc_eligible` allows the point-of-contact edit —
    "final approval level" doesn't require the invitation to be fully
    `approved` yet, just no earlier step still pending ahead of it.
    """
    category = VisitorCategoryFactory.build(
        id=uuid.uuid4(), name="Two Step POC Final Category", code="TWO-STEP-POC-FINAL-CAT"
    )
    approver_role = RoleFactory.build(
        id=uuid.uuid4(), name="two-step-poc-final-approver", permissions=[]
    )
    db_session.add_all([category, approver_role])
    await db_session.flush()
    db_session.add_all(
        [
            ApprovalWorkflowRuleFactory.build(
                id=uuid.uuid4(),
                visitor_category_id=category.id,
                step_order=1,
                approver_role_id=approver_role.id,
            ),
            ApprovalWorkflowRuleFactory.build(
                id=uuid.uuid4(),
                visitor_category_id=category.id,
                step_order=2,
                approver_role_id=approver_role.id,
            ),
        ]
    )
    await db_session.commit()

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitorCategoryId"] = str(category.id)
    data = await _create_invitation_success(client, token, branch, payload=payload)
    invitation_id = uuid.UUID(data["id"])
    steps = await InvitationApprovalStepRepository(db_session).list_for_invitation(invitation_id)
    first_step = next(s for s in steps if s.step_order == 1)
    await db_session.execute(
        update(InvitationApprovalStep)
        .where(InvitationApprovalStep.id == first_step.id)
        .values(status="approved")
    )
    await db_session.commit()

    poc_user = UserFactory.build(id=uuid.uuid4(), email="poc-final-level@acme-test.example")
    db_session.add(poc_user)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/invitations/{data['id']}/edit",
        json={"pocUserId": str(poc_user.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["pocUserId"] == str(poc_user.id)


async def test_edit_invitation_poc_change_included_in_edit_notification_context(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """The visitor's own edit-notification email (unconditional on every
    successful edit — `_send_edit_notification`) reflects whichever point of
    contact is currently resolved, the same way it already reflects the
    other visit-detail fields regardless of which one changed.
    """
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    poc_user = UserFactory.build(id=uuid.uuid4(), email="poc-person-2@acme-test.example")
    db_session.add(poc_user)
    await db_session.commit()

    edit_calls: list[dict] = []
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: edit_calls.append(kw))
    monkeypatch.setattr(notifications_service, "notify_user", lambda **kw: asyncio.sleep(0))
    monkeypatch.setattr(tasks.send_poc_creation_notification, "delay", lambda **kw: None)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"pocUserId": str(poc_user.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert len(edit_calls) == 1
    assert edit_calls[0]["invitation_id"] == str(invitation.id)


# --- POST /invitations/{id}/badge and /badge/reprint ----------------------------


async def test_issue_badge_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/badge",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["badgeNumber"].startswith("BDG-")
    assert data["reprintCount"] == 0

    await db_session.refresh(invitation)
    assert invitation.badge_number == data["badgeNumber"]
    assert invitation.badge_storage_key is not None
    badge_response = await client.get(data["badgeUrl"])
    assert badge_response.status_code == 200
    assert Image.open(io.BytesIO(badge_response.content)).format == "PNG"


async def test_issue_badge_already_issued_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        badge_number="BDG-EXISTING",
        badge_storage_key="vmss:test:invitations/badges:existing.png",
        badge_issued_at=datetime.now(UTC),
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/badge",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


async def test_issue_badge_ineligible_status_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/badge",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


async def test_issue_badge_idempotency_key_replay(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "badge-key-1"}

    first = await client.post(f"/api/v1/invitations/{invitation.id}/badge", headers=headers)
    second = await client.post(f"/api/v1/invitations/{invitation.id}/badge", headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()


async def test_issue_badge_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(viewer)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/badge",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_reprint_badge_success_and_reflects_updated_expiry(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=now,
        expires_at=now + timedelta(days=1),
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}

    issue_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/badge", headers=headers
    )
    assert issue_response.status_code == 201
    badge_number = issue_response.json()["data"]["badgeNumber"]
    await db_session.refresh(invitation)
    first_storage_key = invitation.badge_storage_key

    new_expiry = now + timedelta(days=30)
    extend_response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/extend",
        json={"expiresAt": new_expiry.isoformat()},
        headers=headers,
    )
    assert extend_response.status_code == 200

    reprint_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/badge/reprint", headers=headers
    )
    assert reprint_response.status_code == 200
    reprint_data = reprint_response.json()["data"]
    assert reprint_data["badgeNumber"] == badge_number
    assert reprint_data["reprintCount"] == 1

    await db_session.refresh(invitation)
    assert invitation.badge_reprint_count == 1
    assert invitation.badge_number == badge_number
    assert invitation.badge_storage_key != first_storage_key
    assert invitation.expires_at == new_expiry


async def test_reprint_badge_none_issued_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/badge/reprint",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


async def test_reprint_badge_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        badge_number="BDG-EXISTING2",
        badge_storage_key="vmss:test:invitations/badges:existing2.png",
        badge_issued_at=datetime.now(UTC),
    )
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(viewer)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/badge/reprint",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# --- POST /invitations/{id}/watchlist-override ----------------------------------


async def test_override_watchlist_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        watchlist_flagged=True,
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/watchlist-override",
        json={"reason": "Confirmed not a match"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    await db_session.refresh(invitation)
    assert invitation.watchlist_flagged is False
    assert invitation.watchlist_override_reason == "Confirmed not a match"
    assert invitation.watchlist_override_by_user_id == user.id
    assert invitation.watchlist_override_at is not None
    assert invitation.status == "approved"


async def test_override_watchlist_not_flagged_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/watchlist-override",
        json={"reason": "Not needed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


async def test_override_watchlist_missing_reason_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        watchlist_flagged=True,
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/watchlist-override",
        json={"reason": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    await db_session.refresh(invitation)
    assert invitation.watchlist_flagged is True


async def test_override_watchlist_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    approver = await _branch_scoped_invitation_approver(db_session, tenant, branch.id)
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        watchlist_flagged=True,
    )
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(approver)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/watchlist-override",
        json={"reason": "Not allowed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    await db_session.refresh(invitation)
    assert invitation.watchlist_flagged is True


# --- Push notifications (add-invitation-push-notifications) -----------------


def _make_host(db_session: AsyncSession) -> User:
    return UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )


async def test_create_invitation_submission_notifies_owning_role(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    visit_host: User,
    monkeypatch,
) -> None:
    """specs/invitations/spec.md "Submission Notifies the Owning Role via
    Push" (role-based-invitation-workflow) — every submitted invitation's
    `stepOrder` 0 ownership step is role-identified for the tenant's default
    host role (`reception`), pushed at submission regardless of any
    `hostId` a client still supplies (now ignored — see
    `test_create_invitation_ignores_supplied_host_fields`).
    """
    calls: list[dict] = []
    email_calls: list[dict] = []

    async def _fake_notify_step_approver(tenant_db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_step_approver", _fake_notify_step_approver)
    monkeypatch.setattr(
        tasks.send_tracking_notification, "delay", lambda **kw: email_calls.append(kw)
    )

    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["hostId"] = str(visit_host.id)
    created = await _create_invitation_success(client, token, branch, payload=payload)

    # Push to the ownership step's role, not the (ignored) supplied host ...
    assert len(calls) == 1
    assert calls[0]["approver_role_id"] == reception_role.id
    assert calls[0]["approver_user_id"] is None
    assert calls[0]["branch_id"] == branch.id
    # ... and, for the same submission, the visitor's own tracking email/SMS
    # (proposal.md finding #1 — both channels must fire for the same request,
    # not just whichever one this test happened to check).
    assert len(email_calls) == 1
    assert email_calls[0]["invitation_id"] == created["id"]


async def test_create_invitation_configured_chain_determines_submission_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """A category's own configured `ApprovalWorkflowRule` chain now
    determines which step (and therefore which role) gets pushed at
    submission — its first configured step is the invitation's current
    step, so the submission push goes to that step's role, not
    unconditionally to the tenant's default host role
    (`docs/features/approvals.md` "The host-nomination step").
    """
    category = VisitorCategoryFactory.build(
        id=uuid.uuid4(), name="Role Workflow Category", code="ROLE-WORKFLOW-CAT"
    )
    approver_role = RoleFactory.build(
        id=uuid.uuid4(), name="submission-approver-role", permissions=[]
    )
    db_session.add_all([category, approver_role])
    await db_session.flush()
    db_session.add(
        ApprovalWorkflowRuleFactory.build(
            id=uuid.uuid4(),
            visitor_category_id=category.id,
            step_order=1,
            approver_role_id=approver_role.id,
        )
    )
    await db_session.commit()

    role_calls: list[dict] = []

    async def _fake_notify_role_at_branch(tenant_db, **kwargs):
        role_calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_role_at_branch", _fake_notify_role_at_branch)

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitorCategoryId"] = str(category.id)
    await _create_invitation_success(client, token, branch, payload=payload)

    assert len(role_calls) == 1
    assert role_calls[0]["role_id"] == approver_role.id
    assert role_calls[0]["branch_id"] == branch.id


async def test_create_invitation_admin_owning_role_sends_no_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """specs/invitations/spec.md "Submission with an Admin-role owning role
    sends no push" — a tenant that has reconfigured its default host role to
    the standard `admin` role gets no push on submission, via the same
    admin-exclusion rule `notify_step_approver` already applies generically.
    """
    admin_role = await RoleRepository(db_session).get_by_name("admin")
    assert admin_role is not None  # seeded by the `user` fixture
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), default_host_role_id=admin_role.id))
    await db_session.commit()

    role_calls: list[dict] = []

    async def _fake_notify_role_at_branch(tenant_db, **kwargs):
        role_calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_role_at_branch", _fake_notify_role_at_branch)

    token = await _login(client, user.email)
    await _create_invitation_success(client, token, branch, payload=_individual_payload())

    assert role_calls == []


async def test_create_invitation_auto_approve_skips_submission_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """specs/invitations/spec.md "Auto-Approved Invitations Do Not Trigger a
    Submission Push".
    """
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), auto_approve_pre_registered_visitors=True))
    await db_session.commit()

    calls: list[dict] = []

    async def _fake_notify_step_approver(tenant_db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_step_approver", _fake_notify_step_approver)

    token = await _login(client, user.email)
    await _create_invitation_success(client, token, branch, payload=_individual_payload())

    assert calls == []


async def test_create_invitation_notifies_owning_role_even_with_no_configured_rules(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """Replaces the old "hostless, no rules -> nothing to push" behavior —
    the default test category (`_default_visitor_category`) has no
    configured workflow rules, but every submitted invitation now gets an
    unconditional `stepOrder` 0 ownership step for the tenant's default host
    role (role-based-invitation-workflow), so there is always someone to
    push to.
    """
    calls: list[dict] = []

    async def _fake_notify_step_approver(tenant_db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_step_approver", _fake_notify_step_approver)

    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None

    token = await _login(client, user.email)
    await _create_invitation_success(client, token, branch, payload=_individual_payload())

    assert len(calls) == 1
    assert calls[0]["approver_role_id"] == reception_role.id
    assert calls[0]["approver_user_id"] is None


async def test_approve_invitation_notifies_host(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host = _make_host(db_session)
    db_session.add(host)
    await db_session.flush()
    invitation = _build_invitation(db_session, branch.id, status="submitted", host_id=host.id)
    db_session.add(invitation)
    await db_session.commit()

    email_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: email_calls.append(kw)
    )
    calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert len(calls) == 1
    assert calls[0]["user_id"] == host.id
    assert calls[0]["data"]["action"] == "approved"
    # Visitor's own approval email/SMS must fire for the same request
    # (proposal.md finding #1).
    assert len(email_calls) == 1
    assert email_calls[0]["invitation_id"] == str(invitation.id)


async def test_approve_invitation_hostless_skips_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """specs/invitations/spec.md "No resolved host means no push, and the
    request still succeeds".
    """
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    monkeypatch.setattr(tasks.send_approval_notification, "delay", lambda **kw: None)
    calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert calls == []


async def test_deny_invitation_notifies_host(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host = _make_host(db_session)
    db_session.add(host)
    await db_session.flush()
    invitation = _build_invitation(db_session, branch.id, status="submitted", host_id=host.id)
    db_session.add(invitation)
    await db_session.commit()

    email_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_denial_notification, "delay", lambda **kw: email_calls.append(kw)
    )
    calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/deny",
        json={"reason": "Not expected"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert len(calls) == 1
    assert calls[0]["user_id"] == host.id
    assert calls[0]["data"]["action"] == "denied"
    # Visitor's own denial email/SMS must fire for the same request
    # (proposal.md finding #1).
    assert len(email_calls) == 1
    assert email_calls[0]["invitation_id"] == str(invitation.id)


async def test_reschedule_invitation_notifies_host(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host = _make_host(db_session)
    db_session.add(host)
    await db_session.flush()
    invitation = _build_invitation(db_session, branch.id, status="submitted", host_id=host.id)
    db_session.add(invitation)
    await db_session.commit()

    email_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_reschedule_notification, "delay", lambda **kw: email_calls.append(kw)
    )
    calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/reschedule",
        json={"preferredVisitDate": "2026-12-01", "preferredVisitTime": "15:30:00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert len(calls) == 1
    assert calls[0]["user_id"] == host.id
    assert calls[0]["data"]["action"] == "rescheduled"
    # Visitor's own reschedule email/SMS must fire for the same request
    # (proposal.md finding #1).
    assert len(email_calls) == 1
    assert email_calls[0]["invitation_id"] == str(invitation.id)


async def test_check_in_invitation_notifies_host(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """No dual-channel assertion here (unlike submit/approve/deny/reschedule,
    proposal.md finding #1): the check-in transition dispatches only the
    host push, no visitor-facing email/SMS task — there is nothing on the
    other channel to assert. Check-in now happens through the canonical,
    public v2 endpoint (checkin-approval-workflow-improvements).
    """
    host = _make_host(db_session)
    db_session.add(host)
    await db_session.flush()
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC), host_id=host.id
    )
    db_session.add(invitation)
    await db_session.commit()

    calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
    assert response.status_code == 200, response.text

    assert len(calls) == 1
    assert calls[0]["user_id"] == host.id
    assert calls[0]["data"]["action"] == "checked_in"


async def test_check_out_invitation_notifies_host(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """No dual-channel assertion here either, same reason as
    `test_check_in_invitation_notifies_host` above: `check_out_invitation`
    dispatches only the host push, no visitor-facing email/SMS task.
    """
    host = _make_host(db_session)
    db_session.add(host)
    await db_session.flush()
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        approved_at=datetime.now(UTC),
        checked_in_at=datetime.now(UTC),
        host_id=host.id,
    )
    db_session.add(invitation)
    await db_session.commit()

    calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/check-out",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert len(calls) == 1
    assert calls[0]["user_id"] == host.id
    assert calls[0]["data"]["action"] == "checked_out"


# --- Tenant isolation ------------------------------------------------------------


async def test_check_in_repository_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_checkin"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).check_in_if_eligible(
            invitation.id, user_id=uuid.uuid4()
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.status == "approved"


# --- verify-full-api-test-and-validation-coverage: remaining repository isolation gaps ---


async def test_approve_if_submitted_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted", approved_at=None)
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_approve"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).approve_if_submitted(invitation.id)
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"
    assert invitation.approved_at is None


async def test_deny_if_submitted_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_deny"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).deny_if_submitted(
            invitation.id, reason="Not on the expected list"
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"


async def test_check_out_if_checked_in_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        approved_at=datetime.now(UTC),
        checked_in_at=datetime.now(UTC),
    )
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_checkout"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).check_out_if_checked_in(
            invitation.id, user_id=uuid.uuid4()
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.status == "checked_in"


async def test_reschedule_if_eligible_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()
    original_date = invitation.preferred_visit_date

    other_schema = "tenant_other_test_invitation_reschedule"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).reschedule_if_eligible(
            invitation.id,
            preferred_visit_date=date(2026, 12, 1),
            preferred_visit_time=time(15, 30),
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.preferred_visit_date == original_date


async def test_extend_if_eligible_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    original_expiry = now + timedelta(days=1)
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=now, expires_at=original_expiry
    )
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_extend"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).extend_if_eligible(
            invitation.id, new_expires_at=now + timedelta(days=7)
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.expires_at == original_expiry


async def test_issue_badge_if_eligible_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_badge_issue"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).issue_badge_if_eligible(
            invitation.id, badge_number="BDG-DEADBEEF", badge_storage_key="badges/other.png"
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.badge_number is None


async def test_reprint_badge_if_issued_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        badge_number="BDG-11112222",
        badge_storage_key="badges/original.png",
    )
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_badge_reprint"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).reprint_badge_if_issued(
            invitation.id, badge_storage_key="badges/other-reprint.png"
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.badge_storage_key == "badges/original.png"
    assert invitation.badge_reprint_count == 0


async def test_override_watchlist_if_flagged_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        watchlist_flagged=True,
    )
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_watchlist_override"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).override_watchlist_if_flagged(
            invitation.id, user_id=uuid.uuid4(), reason="Confirmed false positive"
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.watchlist_flagged is True


async def test_list_by_primary_contact_email_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    """Covers the email-lookup path of `GET /invitations/track` — the
    trackingId path is already covered by
    `test_invitation_repository_tenant_schema_isolation` above.
    """
    email = f"tracked-{uuid.uuid4().hex[:8]}@example.com"
    invitation = _build_invitation(db_session, branch.id, primary_contact_email=email)
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_track_by_email"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await InvitationRepository(other_session).list_by_primary_contact_email(email)
        assert found == []


async def test_get_with_children_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    """Covers `GET /invitations/{id}`'s own repository method."""
    invitation = _build_invitation(db_session, branch.id, status="approved")
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_get_with_children"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await InvitationRepository(other_session).get_with_children(invitation.id)
        assert found is None


async def test_get_invitation_detail_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """testing-standards.md §2 permission-denied case, distinct from
    `test_get_invitation_detail_denied_for_viewer_scoped_elsewhere` above:
    that test's caller has zero access to the invitation's own branch at
    all, which trips `authorize_branch_id_tolerant`'s *first* guard ("No
    access to this branch"). This caller is correctly scoped to the
    invitation's own branch (a real `invitations:approve` grant there) but
    holds no `invitations:view` permission at all — the *second* guard
    ("Insufficient permission"), the "no permission whatsoever" 403 branch
    task 3.4 asks for.
    """
    caller = await _branch_scoped_invitation_approver(db_session, tenant, branch.id)
    invitation = _build_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(caller)
    response = await client.get(
        f"/api/v1/invitations/{invitation.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# --- Email templates (email-notifications capability) -----------------------

_EMAIL_TEMPLATE_NAMES = (
    "tracking_only",
    "visit_confirmation",
    "denial",
    "reschedule",
    "edit",
    "submission_role",
    "host_assigned",
    "poc_assigned",
)


async def test_every_notification_template_renders_without_error() -> None:
    """spec.md "Every Notification Email Is Rendered From a Branded HTML
    Template" — each template renders given a representative context,
    without raising, into both an HTML and a plain-text part.
    """
    from vmss_api.core.email_rendering import render_email

    representative_context = {
        "company_name": "Acme Test Co",
        "logo_url": None,
        "recipient_name": "Meera Krishnan",
        "recipient_email": "meera@example.com",
        "tracking_id": "INV-TEST0001",
        "visitor_name": "Meera Krishnan",
        "purpose": "Interview",
        "visit_date": date(2026, 10, 1),
        "visit_time": time(10, 0),
        "duration": "1 hour",
        "department": "Engineering",
        "denial_reason": "Not expected",
        "host_name": "Rahul Nair",
        "host_contact": "rahul@example.com",
        "front_desk_contact": None,
        "qr_cid": "visit-qr@vmss",
        "is_approved": True,
    }
    for template_name in _EMAIL_TEMPLATE_NAMES:
        rendered = render_email(template_name, representative_context)
        assert rendered.subject
        assert "<html" in rendered.html
        assert "INV-TEST0001" in rendered.html
        assert "INV-TEST0001" in rendered.text


async def test_template_rendering_failure_falls_back_to_plain_text(monkeypatch) -> None:
    """spec.md "Template Rendering Failure Falls Back to a Minimal
    Plain-Text Email" — a forced rendering failure still results in a
    deliverable (plain-text-only) email, logged at `ERROR`.
    """
    from vmss_api.core.email_rendering import TemplateRenderError

    def _raise(*args, **kwargs):
        raise TemplateRenderError("forced failure")

    monkeypatch.setattr(tasks, "render_email", _raise)
    logged: list[tuple[str, dict]] = []
    monkeypatch.setattr(tasks.logger, "error", lambda event, **kw: logged.append((event, kw)))

    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        tracking_id="INV-TEST0006",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
        primary_contact_phone=None,
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

    result = await asyncio.to_thread(
        tasks.send_tracking_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert sent[0]["html_body"] is None
    assert "INV-TEST0006" in sent[0]["body"]
    assert logged and logged[0][0] == "email_template_render_failed"


async def test_approval_email_includes_resolved_host_contact(monkeypatch) -> None:
    """spec.md "Approval email with a resolved host includes their contact
    details".
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        status="approved",
        tracking_id="INV-TEST0007",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
        primary_contact_phone=None,
        host_id=uuid.uuid4(),
    )
    fake_host = UserFactory.build(
        id=fake_invitation.host_id,
        full_name="Rahul Nair",
        phone_number="+91 90000 11122",
        is_active=True,
    )
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, user=fake_host)
    )

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "qr_token": "fake-qr-token",
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert sent[0]["html_body"] is not None
    assert "Rahul Nair" in sent[0]["html_body"]
    assert "+91 90000 11122" in sent[0]["html_body"]


async def test_approval_email_falls_back_to_front_desk_contact_when_no_host(monkeypatch) -> None:
    """spec.md "Approval email with no resolved host falls back to the
    front-desk contact".
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        status="approved",
        tracking_id="INV-TEST0008",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
        primary_contact_phone=None,
    )
    fake_company = CompanyFactory.build(
        id=uuid.uuid4(), phone="+91 80000 22233", email="frontdesk@acme-test.example"
    )
    monkeypatch.setattr(
        tasks,
        "tenant_session_scope",
        _fake_tenant_session_scope(fake_invitation, company=fake_company),
    )

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "qr_token": "fake-qr-token",
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert sent[0]["html_body"] is not None
    assert "+91 80000 22233" in sent[0]["html_body"]


async def test_approval_email_prefers_point_of_contact_over_host(monkeypatch) -> None:
    """add-invitation-point-of-contact: when both a host and a point of
    contact are resolved, the "Your point of contact" box shows the POC —
    a deliberate override of who to reach about the visit's logistics —
    not the workflow-resolved host.

    `_FakeSession.execute` returns the single configured `user=` for *any*
    `UserRepository.get_active(...)` call regardless of which id it was
    given (host_id or poc_user_id alike), so this test can't give the host
    and POC two independently-resolved live identities. It instead relies
    on `poc_name` being read straight off `invitation.poc_name` rather than
    re-resolved from the session — distinct from `host_name`, which *is*
    session-resolved — so asserting the invitation's own `poc_name`
    ("Priya POC") appears while the session-resolved name ("Rahul Nair",
    standing in for whichever party a real host lookup would return) does
    not is still a valid, if narrow, check that the POC branch fired
    instead of the host branch.
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        status="approved",
        tracking_id="INV-TEST0013",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
        primary_contact_phone=None,
        host_id=uuid.uuid4(),
        poc_user_id=uuid.uuid4(),
        poc_name="Priya POC",
    )
    fake_resolved_user = UserFactory.build(
        id=uuid.uuid4(), full_name="Rahul Nair", phone_number="+91 90000 33344", is_active=True
    )
    monkeypatch.setattr(
        tasks,
        "tenant_session_scope",
        _fake_tenant_session_scope(fake_invitation, user=fake_resolved_user),
    )

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "qr_token": "fake-qr-token",
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert sent[0]["html_body"] is not None
    assert "Priya POC" in sent[0]["html_body"]
    assert "Rahul Nair" not in sent[0]["html_body"]


async def test_approval_email_shows_role_based_point_of_contact_without_live_contact(
    monkeypatch,
) -> None:
    """A role-identified point of contact has no single person's phone/email
    to resolve — the box shows just the role's snapshotted name, still in
    preference to the host.
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        status="approved",
        tracking_id="INV-TEST0014",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
        primary_contact_phone=None,
        host_id=uuid.uuid4(),
        poc_role_id=uuid.uuid4(),
        poc_name="Front Desk",
    )
    fake_host = UserFactory.build(
        id=fake_invitation.host_id, full_name="Rahul Nair", is_active=True
    )
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, user=fake_host)
    )

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "qr_token": "fake-qr-token",
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert sent[0]["html_body"] is not None
    assert "Front Desk" in sent[0]["html_body"]
    assert "Rahul Nair" not in sent[0]["html_body"]


# --- Owning-role email fan-out (role-based-invitation-workflow) -------------


async def test_create_invitation_enqueues_owning_role_email_notification(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """spec.md "Submission emails every holder of the owning role" — the
    submission enqueues the role-fan-out email task with the ownership
    step's role and the invitation's branch. `.delay()` only enqueues to a
    real Celery/Redis broker — it does not run the task body inline — so
    this test asserts what the request itself is responsible for (the
    enqueue), the same way every other task-dispatch test in this module
    does; `test_send_submission_role_email_notification_emails_every_role_
    holder_with_usable_email` below exercises the task body itself.
    """
    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None

    calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_submission_role_email_notification, "delay", lambda **kw: calls.append(kw)
    )

    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=_individual_payload())

    assert len(calls) == 1
    assert calls[0]["invitation_id"] == data["id"]
    assert calls[0]["role_id"] == str(reception_role.id)
    assert calls[0]["branch_id"] == str(branch.id)


async def test_send_submission_role_email_notification_emails_every_role_holder_with_usable_email(
    monkeypatch,
) -> None:
    """spec.md "Submission emails every holder of the owning role" —
    exercised directly against the task body (testing-standards.md §3's
    "unit-style" tier), since `.delay()` itself only enqueues.
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        tracking_id="INV-TEST0009",
        primary_contact_full_name="Meera Krishnan",
        purpose_of_visit="Interview",
    )
    role_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    first_user = UserFactory.build(id=uuid.uuid4(), email="reception1@acme-test.example")
    second_user = UserFactory.build(id=uuid.uuid4(), email="reception2@acme-test.example")

    class _FakeUserRepository:
        def __init__(self, session):
            pass

        async def list_users_holding_role_at_branch(self, role_id_arg, branch_id_arg):
            assert role_id_arg == role_id
            assert branch_id_arg == branch_id
            return [first_user, second_user]

    monkeypatch.setattr(tasks, "UserRepository", _FakeUserRepository)
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

    result = await asyncio.to_thread(
        tasks.send_submission_role_email_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "role_id": str(role_id),
            "branch_id": str(branch_id),
        },
    )
    result.get(propagate=True)

    recipients = {call["to"] for call in sent}
    assert recipients == {"reception1@acme-test.example", "reception2@acme-test.example"}
    assert all("INV-TEST0009" in call["body"] for call in sent)


# --- form-builder integration: branch-configured requiredness ---------------
#
# specs/invitations/spec.md (delta) — these exercise the branch actually
# *changing* what's required, not just the seeded-default path every other
# test above already covers implicitly.


async def _create_invitation_raw(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    payload: dict,
    include_primary_id_proof: bool = True,
    include_primary_photo: bool = True,
) -> Response:
    """Like `_create_invitation`, but lets a caller omit the primary
    contact's ID-proof/photo file parts entirely — needed to exercise a
    branch that has deactivated one of them.
    """
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    files = []
    if include_primary_id_proof:
        files.append(("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")))
    if include_primary_photo:
        files.append(("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")))
    return await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(payload)},
        files=files,
        headers=headers,
    )


async def _configure_and_publish_branch_field(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    step_key: str,
    field_key: str,
    changes: dict,
) -> None:
    """Admin-side setup shared by the tests below: fetches the branch's
    (form-builder-seeded) draft steps, finds `field_key` within `step_key`,
    PATCHes it with `changes`, then publishes the branch's scope so
    `create_invitation` actually reads the new configuration.
    """
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == step_key)
    field = next(f for f in step["fields"] if f["key"] == field_key)

    patch_response = await client.patch(
        f"/api/v1/form-builder/fields/{field['id']}", json=changes, headers=headers
    )
    assert patch_response.status_code == 200, patch_response.text

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])


async def test_create_invitation_id_proof_not_required_when_branch_deactivates_it(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """specs/invitations/spec.md (delta) "ID proof not required when the
    branch has deactivated it".
    """
    token = await _login(client, user.email)
    await _configure_and_publish_branch_field(
        client,
        token,
        branch,
        step_key="visitor_info",
        field_key="id_proof_upload",
        changes={"isActive": False, "isRequired": False},
    )

    payload = _individual_payload()
    del payload["primaryContact"]["idProofType"]
    response = await _create_invitation_raw(
        client, token, branch, payload=payload, include_primary_id_proof=False
    )
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("blank", ["", "null", " NULL "])
def test_blank_id_proof_type_is_normalized_to_none(blank: str) -> None:
    """`idProofType` is optional: `""`/`"null"` mean "not provided" for both
    the create-invitation and walk-in payloads (shared schemas).
    """
    from vmss_api.invitations.schemas import InvitationPrimaryContactCreate, VisitorSubmit

    assert (
        InvitationPrimaryContactCreate(
            full_name="A", email="a@example.com", id_proof_type=blank
        ).id_proof_type
        is None
    )
    assert (
        VisitorSubmit(full_name="A", email="a@example.com", id_proof_type=blank).id_proof_type
        is None
    )


async def test_create_invitation_photo_not_required_when_branch_deactivates_it(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """specs/invitations/spec.md (delta) "Missing primary contact photo is
    accepted when the branch has deactivated it".
    """
    token = await _login(client, user.email)
    await _configure_and_publish_branch_field(
        client,
        token,
        branch,
        step_key="visitor_info",
        field_key="profile_photo",
        changes={"isActive": False, "isRequired": False},
    )

    response = await _create_invitation_raw(
        client, token, branch, payload=_individual_payload(), include_primary_photo=False
    )
    assert response.status_code == 201, response.text


async def test_create_invitation_consent_not_required_when_branch_deactivates_it(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """specs/invitations/spec.md (delta) "Consent Is Mandatory and
    Recorded" — a consent the branch no longer marks required may be
    omitted.
    """
    token = await _login(client, user.email)
    await _configure_and_publish_branch_field(
        client,
        token,
        branch,
        step_key="consent_agreement",
        field_key="safety_guidelines_accepted",
        changes={"isRequired": False},
    )

    payload = _individual_payload()
    _remove_default_consent(payload, "safety_guidelines_accepted")
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 201, response.text


async def test_create_invitation_expected_duration_optional(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """ "Expected Duration" is no longer collected by either visitor-facing
    wizard at all (make-expected-duration-optional), so `create_invitation`
    must accept a submission that omits it regardless of the branch's own
    Form Builder configuration for the field — unlike ID proof/photo, there
    is no requiredness check for it any more.
    """
    token = await _login(client, user.email)
    payload = _individual_payload()
    del payload["visitDetails"]["expectedDuration"]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 201, response.text

    tracking_id = response.json()["data"]["trackingId"]
    track_response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": tracking_id}
    )
    assert track_response.status_code == 200, track_response.text
    assert track_response.json()["data"]["expectedDuration"] is None


async def test_create_invitation_carried_item_allowed_when_branch_adds_custom_item(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """specs/invitations/spec.md (delta) "Carried Items and Vehicles Are
    Optional Structured Declarations" — a key the branch adds to its
    Carried Items options becomes acceptable.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    step = next(s for s in steps_response.json()["data"] if s["key"] == "carried_items")
    field = next(f for f in step["fields"] if f["key"] == "items")

    patch_response = await client.patch(
        f"/api/v1/form-builder/fields/{field['id']}",
        json={"options": [*field["options"], "company_badge"]},
        headers=headers,
    )
    assert patch_response.status_code == 200, patch_response.text
    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])

    payload = _individual_payload()
    payload["carriedItems"] = {"items": ["company_badge"]}
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 201, response.text


async def test_create_invitation_carried_item_still_rejected_when_not_in_branch_config(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Sibling of the success case above — a key that was never added to
    the branch's Carried Items options is still rejected even after that
    branch has published its own configuration (not just the tenant
    default fallback).
    """
    token = await _login(client, user.email)
    # Gives this branch its own published configuration (distinct from the
    # tenant-default fallback) via an innocuous field edit, so this test
    # exercises the branch's own resolved config, not just the default.
    await _configure_and_publish_branch_field(
        client,
        token,
        branch,
        step_key="visitor_info",
        field_key="profile_photo",
        changes={"placeholder": "A clear, recent photo"},
    )

    payload = _individual_payload()
    payload["carriedItems"] = {"items": ["not_a_configured_item"]}
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


# --- add-generic-custom-field-support: admin-authored custom fields --------
#
# specs/invitations/spec.md (delta) "Invitation Creation Captures
# Admin-Defined Custom Field Answers" — every step now accepts new
# admin-authored fields (form-builder), and their answers are captured at
# the same per-visitor/per-vehicle/per-invitation scope their step's own
# fields already use.


async def _create_and_publish_custom_field(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    step_key: str,
    key: str,
    field_type: str = "text",
    is_required: bool = False,
    options: list[str] | None = None,
    help_text: str | None = None,
    hide_label: bool = False,
) -> dict:
    """Admin-side setup: creates a new admin-authored field on `step_key`
    and publishes the branch's scope so `create_invitation` reads it.
    """
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == step_key)

    body: dict = {"key": key, "label": key.replace("_", " ").title(), "fieldType": field_type}
    if is_required:
        body["isRequired"] = True
    if options is not None:
        body["options"] = options
    if help_text is not None:
        body["helpText"] = help_text
    if hide_label:
        body["hideLabel"] = True
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields", json=body, headers=headers
    )
    assert create_response.status_code == 201, create_response.text

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])
    return create_response.json()["data"]


async def _update_and_publish_field_options(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    step_key: str,
    field_key: str,
    options: list[str],
    field_type: str | None = None,
) -> dict:
    """Admin-side setup: sets an existing (e.g. system-seeded) field's
    options (and, optionally, its `field_type`) and publishes the
    branch's scope so `create_invitation` reads it — used for
    `id_proof_type`/`vehicle_type` (make-id-proof-and-vehicle-type-
    configurable), whose options are editable even though the field
    itself was seeded, not admin-created; `field_type` additionally
    supports retyping a system field that isn't option-bearing by default
    (e.g. "Purpose of Visit") to `dropdown_select`/`checkbox_list`
    (make-system-field-types-editable).
    """
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    fields_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert fields_response.status_code == 200, fields_response.text
    step = next(s for s in fields_response.json()["data"] if s["key"] == step_key)
    field = next(f for f in step["fields"] if f["key"] == field_key)

    body: dict[str, Any] = {"options": options}
    if field_type is not None:
        body["fieldType"] = field_type
    update_response = await client.patch(
        f"/api/v1/form-builder/fields/{field['id']}", json=body, headers=headers
    )
    assert update_response.status_code == 200, update_response.text

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(fields_response.json()["data"])
    return update_response.json()["data"]


async def test_create_invitation_captures_primary_contact_custom_field(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="visitor_info", key="employee_id"
    )

    payload = _individual_payload()
    # The primary contact's Visitor Info-step answers are sourced from the
    # invitation-level `customFields` array, not a nested
    # `primaryContact.customFields` — see `InvitationPrimaryContactCreate`'s
    # docstring in `schemas.py`.
    payload["customFields"] = [{"fieldId": field["id"], "value": "E-1001"}]
    data = await _create_invitation_success(client, token, branch, payload=payload)

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["data"]["customFields"] == [
        {"fieldId": field["id"], "value": "E-1001"}
    ]


async def test_create_invitation_captures_primary_contact_custom_field_on_system_group(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """An admin-authored custom field can be attached to the seeded
    (system) "visitors" group on Visitor Info — that group is never
    surfaced by `custom_groups_for_invitation_scope`/`custom_groups_for_step`
    (its cardinality is the `visitors` payload list's own length, not a
    `groups` entry), so such a field's answer must still be accepted
    through the ordinary per-visitor `customFields` array, the same as
    an ungrouped field. Regression test: `custom_fields_for_step` used to
    exclude any field with a `groupId`, including one on this system group,
    which meant the field's answer was rejected as unknown no matter which
    payload array it was submitted through.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == "visitor_info")
    [visitors_group] = step["groups"]
    assert visitors_group["key"] == "visitors"
    assert visitors_group["isSystem"] is True

    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "purpose_note",
            "label": "Purpose Note",
            "fieldType": "text",
            "groupId": visitors_group["id"],
        },
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    field_id = create_response.json()["data"]["id"]

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])

    payload = _individual_payload()
    payload["customFields"] = [{"fieldId": field_id, "value": "some value"}]
    data = await _create_invitation_success(client, token, branch, payload=payload)

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["data"]["customFields"] == [
        {"fieldId": field_id, "value": "some value"}
    ]


async def test_create_invitation_captures_co_visitor_custom_fields_independently(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Two visitors answering the same admin-authored Visitor Info field
    each keep their own independent answer."""
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="visitor_info", key="employee_id"
    )

    payload = _group_payload()
    payload["customFields"] = [{"fieldId": field["id"], "value": "E-1001"}]
    payload["visitors"][0]["customFields"] = [{"fieldId": field["id"], "value": "E-2002"}]
    data = await _create_invitation_success(
        client, token, branch, payload=payload, visitor_file_count=2
    )

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    body = detail_response.json()["data"]
    assert body["customFields"] == [{"fieldId": field["id"], "value": "E-1001"}]
    visitors_by_name = {v["fullName"]: v for v in body["visitors"]}
    assert visitors_by_name["Alexander Pierce"]["customFields"] == [
        {"fieldId": field["id"], "value": "E-2002"}
    ]
    assert visitors_by_name["Clara Oswald"]["customFields"] == []


async def test_create_invitation_captures_vehicle_custom_field(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="vehicle_info", key="parking_zone"
    )

    payload = _group_payload()
    payload["vehicles"][0]["customFields"] = [{"fieldId": field["id"], "value": "B2"}]
    data = await _create_invitation_success(
        client, token, branch, payload=payload, visitor_file_count=2
    )

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    vehicles = detail_response.json()["data"]["vehicles"]
    vehicles_by_plate = {v["licensePlate"]: v for v in vehicles}
    assert vehicles_by_plate["KA-01-AB-1234"]["customFields"] == [
        {"fieldId": field["id"], "value": "B2"}
    ]
    assert vehicles_by_plate["KA-05-CD-5678"]["customFields"] == []


async def test_create_invitation_captures_invitation_level_custom_field(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A custom field on Visit Details (no per-entity structure of its own)
    is captured once per invitation."""
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="visit_details", key="cost_center"
    )

    payload = _individual_payload()
    payload["customFields"] = [{"fieldId": field["id"], "value": "CC-42"}]
    data = await _create_invitation_success(client, token, branch, payload=payload)

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert detail_response.json()["data"]["customFields"] == [
        {"fieldId": field["id"], "value": "CC-42"}
    ]


async def test_create_invitation_custom_field_unresolvable_id_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["customFields"] = [{"fieldId": str(uuid.uuid4()), "value": "x"}]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_custom_field_missing_required_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    await _create_and_publish_custom_field(
        client, token, branch, step_key="visit_details", key="cost_center", is_required=True
    )

    payload = _individual_payload()
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_hidden_label_custom_field_missing_required_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """update-form-field-hide-label-option: `hideLabel` is a display-only
    property — a required field with its label hidden still rejects a
    missing submitted value the same way an always-visible required field
    does."""
    token = await _login(client, user.email)
    await _create_and_publish_custom_field(
        client,
        token,
        branch,
        step_key="visit_details",
        key="cost_center",
        is_required=True,
        hide_label=True,
    )

    payload = _individual_payload()
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_static_text_field_needs_no_submitted_value(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """specs/form-builder/spec.md (delta) "A `static_text` Field Renders
    Admin-Authored Content With No Input Control" — a `static_text` field
    (e.g. a Terms & Conditions block admin-authored on Visit Details)
    collects no answer, so an invitation created without any submitted
    value for its key must still succeed."""
    token = await _login(client, user.email)
    await _create_and_publish_custom_field(
        client,
        token,
        branch,
        step_key="visit_details",
        key="visit_notice",
        field_type="static_text",
        help_text="Please arrive 10 minutes early.",
    )

    payload = _individual_payload()
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]


async def test_create_invitation_seeded_carried_items_field_unaffected_by_custom_field(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Regression: adding an admin-authored field to Carried Items must not
    disturb the seeded `items` field's existing wire shape (`carriedItems.
    items`, mapped to the `carried_items` column) — only the new field's
    answer routes through `customFields`."""
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client,
        token,
        branch,
        step_key="carried_items",
        key="company_badge",
        field_type="toggle_switch",
    )

    payload = _individual_payload()
    payload["carriedItems"] = {"items": ["laptop_tablet"]}
    payload["customFields"] = [{"fieldId": field["id"], "value": True}]
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    body = detail_response.json()["data"]
    assert body["carriedItems"] == ["laptop_tablet"]
    assert body["customFields"] == [{"fieldId": field["id"], "value": True}]


async def test_create_invitation_custom_consent_field_goes_through_consents(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Regression for design.md Decision 6: a new admin-authored Consent
    Agreement field is already captured by the pre-existing `consents`
    array (every field on that step, system or not) - it must not also be
    required in `customFields`, and supplying it there instead of in
    `consents` must not satisfy the requirement.
    """
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client,
        token,
        branch,
        step_key="consent_agreement",
        key="extra_consent",
        field_type="toggle_switch",
        is_required=True,
    )

    payload = _individual_payload()
    _add_consent(payload, field["id"], True)
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]

    wrong_scope_payload = _individual_payload()
    wrong_scope_payload["customFields"] = [{"fieldId": field["id"], "value": True}]
    response = await _create_invitation(client, token, branch, payload=wrong_scope_payload)
    assert response.status_code == 422


async def test_create_invitation_custom_field_values_tenant_schema_isolation(
    client: AsyncClient,
    user: User,
    branch: Branch,
    make_tenant_schema,
    open_tenant_session,
) -> None:
    """testing-standards.md §2 tenant-isolation case: an invitation carrying
    custom field answers, created under this tenant's schema, must not be
    visible from a session bound to a different tenant's schema.
    """
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="visit_details", key="cost_center"
    )
    payload = _individual_payload()
    payload["customFields"] = [{"fieldId": field["id"], "value": "CC-42"}]
    data = await _create_invitation_success(client, token, branch, payload=payload)

    other_schema = "tenant_other_custom_field_test"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        result = await other_session.execute(
            select(Invitation).where(Invitation.tracking_id == data["trackingId"])
        )
        assert result.scalar_one_or_none() is None


# --- fix-registration-host-role-crash: default-host-role failure mode ------
#
# specs/approvals/spec.md (delta) "Unresolvable Default Host Role Fails the
# Submission as a Server Misconfiguration" — `get_default_host_role`
# (org_structure/service.py) already raises 500 + logs ERROR when a
# tenant's `reception` role can't be resolved; this was previously
# untested and undocumented in specs.


async def test_create_invitation_missing_default_host_role_fails_as_server_misconfiguration(
    client: AsyncClient, user: User, branch: Branch, tenant: Tenant, db_session: AsyncSession
) -> None:
    """`auth/service.py`'s `update_role`/`delete_role` protect any
    `STANDARD_ROLE_NAMES` role (including "reception") from rename/delete
    via the API, so this provisioning-gap state — a tenant with no
    resolvable default host role — isn't reachable through the product's
    own API. It's constructed directly at the repository layer instead,
    per `design.md`'s "Risks/Trade-offs" note, bypassing that protection on
    purpose (not a scenario a client can trigger).
    """
    token = await _login(client, user.email)
    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None
    await RoleRepository(db_session).soft_delete(reception_role)
    await db_session.commit()

    # `capture_logs()` disables every configured processor by default
    # (including `structlog.contextvars.merge_contextvars`), so a field
    # bound only via contextvars (`tenant_id`, here) has to have that
    # processor passed back in explicitly to show up in a captured entry.
    with capture_logs(processors=(structlog.contextvars.merge_contextvars,)) as captured:
        response = await _create_invitation(client, token, branch, payload=_individual_payload())

    assert response.status_code == 500

    [entry] = [e for e in captured if e["event"] == "default_host_role_not_seeded"]
    assert entry["log_level"] == "error"
    # tenant_id is bound into structlog's contextvars for every authenticated
    # request (core/tenancy.py) — no explicit parameter needed for this log
    # line to carry it (logging-observability.md §1).
    assert entry["tenant_id"] == str(tenant.id)

    # `create_invitation` calls `get_default_host_role` before
    # `tenant_db.commit()` (invitations/service.py), so nothing from this
    # failed attempt should have reached the database. The test client's
    # `get_tenant_db` override hands every request the same bare
    # `db_session` with no `async with` around it (unlike production's
    # `tenant_session_scope`), so this explicit rollback stands in for the
    # automatic rollback-on-exit production gets for free — see
    # `org_structure/tests.py`'s
    # `test_provision_branch_rolls_back_partial_tree_on_mid_transaction_conflict`.
    await db_session.rollback()
    for model in (Invitation, InvitationVisitor, InvitationVehicle, InvitationApprovalStep):
        count = await db_session.scalar(select(func.count()).select_from(model))
        assert count == 0, f"{model.__name__} row(s) leaked from a failed default-host-role lookup"


# --- fix-registration-host-role-crash: submission through a brand-new step -

# testing-standards.md §2 — every prior custom-field test above adds a field
# to an already-*seeded* step (visitor_info/vehicle_info/visit_details/
# carried_items/consent_agreement); none exercises a genuinely new custom
# step, the exact "test"/"test 2" shape reported in the originating bug
# (including one step left with zero fields configured).


async def test_create_invitation_through_new_custom_step_with_and_without_fields(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}

    step_with_field = (
        await client.post(
            "/api/v1/form-builder/steps",
            json={"key": "custom_step_one", "name": "Custom Step"},
            headers=headers,
        )
    ).json()["data"]
    field_response = await client.post(
        f"/api/v1/form-builder/steps/{step_with_field['id']}/fields",
        json={"key": "custom_answer", "label": "Custom Answer", "fieldType": "text"},
        headers=headers,
    )
    assert field_response.status_code == 201, field_response.text

    # A second new custom step deliberately left with zero fields — must
    # not break `resolve_effective_form`/validation for a submission that
    # simply has nothing to answer on it.
    empty_step_response = await client.post(
        "/api/v1/form-builder/steps",
        json={"key": "custom_step_two", "name": "Custom Step 2"},
        headers=headers,
    )
    assert empty_step_response.status_code == 201, empty_step_response.text

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    field_id = field_response.json()["data"]["id"]
    post_publish_steps = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert post_publish_steps.status_code == 200, post_publish_steps.text
    _record_live_consent_field_ids(post_publish_steps.json()["data"])

    payload = _individual_payload()
    payload["customFields"] = [{"fieldId": field_id, "value": "Some value"}]
    data = await _create_invitation_success(client, token, branch, payload=payload)

    detail_response = await client.get(f"/api/v1/invitations/{data['id']}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["data"]["customFields"] == [
        {"fieldId": field_id, "value": "Some value"}
    ]


# --- QR inline-only + reschedule QR (refine-email-templates-and-visimio-brand)


async def _run_reschedule_task(monkeypatch, fake_invitation, *, qr_code=None) -> list[dict]:
    sent: list[dict] = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, qr_code=qr_code)
    )
    result = await asyncio.to_thread(
        tasks.send_reschedule_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)
    return sent


def _reschedulable_invitation(status: str) -> _FakeInvitation:
    return _FakeInvitation(
        status=status,
        tracking_id="INV-RESCHED1",
        preferred_visit_date=date(2026, 12, 1),
        preferred_visit_time=time(15, 30),
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
    )


async def test_reschedule_of_approved_visit_embeds_the_persisted_qr(monkeypatch) -> None:
    fake_qr = InvitationQRCode(
        id=uuid.uuid4(),
        invitation_id=uuid.uuid4(),
        qr_token="persisted-token",
        image_storage_key="k",
    )
    sent = await _run_reschedule_task(
        monkeypatch, _reschedulable_invitation("approved"), qr_code=fake_qr
    )

    assert len(sent) == 1
    assert "attachment" not in sent[0]
    [inline] = sent[0]["inline_images"]
    assert inline.cid == "visit-qr@vmss"
    assert inline.content == await generate_qr_png("persisted-token")
    assert 'src="cid:visit-qr@vmss"' in sent[0]["html_body"]


async def test_reschedule_of_pending_visit_has_no_qr(monkeypatch) -> None:
    sent = await _run_reschedule_task(monkeypatch, _reschedulable_invitation("submitted"))

    assert sent[0]["inline_images"] == []
    assert "cid:visit-qr@vmss" not in sent[0]["html_body"]
    assert "as soon as it's approved" in sent[0]["body"]


async def test_reschedule_of_approved_visit_without_qr_row_warns_and_falls_back(
    monkeypatch,
) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(tasks.logger, "warning", lambda event, **kw: warnings.append(event))

    sent = await _run_reschedule_task(
        monkeypatch, _reschedulable_invitation("approved"), qr_code=None
    )

    assert warnings == ["reschedule_notification_qr_missing"]
    assert sent[0]["inline_images"] == []
    assert "as soon as it's approved" in sent[0]["body"]


async def test_approval_email_sends_qr_inline_only(monkeypatch) -> None:
    sent: list[dict] = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        status="approved",
        tracking_id="INV-INLINE01",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))
    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "qr_token": "tok",
        },
    )
    result.get(propagate=True)

    assert "attachment" not in sent[0]
    assert [image.cid for image in sent[0]["inline_images"]] == ["visit-qr@vmss"]


async def test_email_context_resolves_place_department_and_front_desk_from_org_chart(
    monkeypatch,
) -> None:
    """email-notifications "Confirmation email shows when, where and who"
    and "Branch contact preferred over company contact"."""
    branch = Branch(
        id=uuid.uuid4(),
        name="Technopark Campus",
        code="TPK",
        address="Phase 1",
        city="Trivandrum",
        contact_phone="+91 80000 22233",
    )
    department = Department(id=uuid.uuid4(), name="Engineering")
    building = SimpleNamespace(name="Tower A")
    company = CompanyFactory.build(id=uuid.uuid4(), phone="+91 11111 11111")
    fake_invitation = _FakeInvitation(
        status="approved",
        tracking_id="INV-PLACE001",
        branch_id=branch.id,
        department_id=department.id,
        department_to_visit="free text dept",
        poc_name="Priya Nair",
    )
    session = _FakeSession(
        fake_invitation, company=company, location=(branch, department, building)
    )

    context = await tasks._invitation_email_context(
        session, fake_invitation, recipient_name=None, recipient_email=None
    )

    assert context["place"] == "Tower A · Technopark Campus · Phase 1, Trivandrum"
    assert context["department"] == "Engineering"
    assert context["front_desk_contact"] == "+91 80000 22233"
    assert context["contact_name"] == "Priya Nair"


# --- Point-of-contact chain (serve-email-images-by-url-and-complete-contact
# design.md Decision 4) --------------------------------------------------------


class _UsersById:
    """Stands in for `UserRepository`: `get_active` by id, so each chain
    step can resolve a different person."""

    def __init__(self, people: dict[uuid.UUID, Any]) -> None:
        self._people = people

    def __call__(self, session):
        return self

    async def get_active(self, user_id: uuid.UUID):
        return self._people.get(user_id)


def _person(full_name: str, *, phone: str | None = None, email: str = "p@example.com"):
    return SimpleNamespace(full_name=full_name, phone_number=phone, email=email)


_HOST_ID, _BRANCH_CONTACT_ID = uuid.uuid4(), uuid.uuid4()


def _chain_branch(**overrides: Any) -> SimpleNamespace:
    return SimpleNamespace(
        **{"name": "Main Branch", "contact_person_user_id": _BRANCH_CONTACT_ID, **overrides}
    )


async def _contact_for(
    monkeypatch,
    *,
    poc_name: str | None = None,
    host_id: uuid.UUID | None = None,
    branch: SimpleNamespace | None,
    front_desk: str | None = "+91 80000 22233",
    people: dict[uuid.UUID, Any] | None = None,
) -> dict[str, str | None]:
    monkeypatch.setattr(tasks, "UserRepository", _UsersById(people or {}))
    invitation = _FakeInvitation(poc_name=poc_name, host_id=host_id)
    return await tasks._resolve_contact(
        None, invitation, branch=branch, front_desk_contact=front_desk
    )


_PEOPLE = {
    _HOST_ID: _person("Rahul Verma", phone="+91 90000 33344"),
    _BRANCH_CONTACT_ID: _person("Anil Menon", phone="+91 90000 55566"),
}


async def test_contact_chain_prefers_the_invitation_poc(monkeypatch) -> None:
    contact = await _contact_for(
        monkeypatch, poc_name="Priya Nair", host_id=_HOST_ID, branch=_chain_branch(), people=_PEOPLE
    )
    assert contact["contact_name"] == "Priya Nair"
    assert contact["contact_title"] == "Your point of contact"


async def test_contact_chain_falls_back_to_the_host(monkeypatch) -> None:
    contact = await _contact_for(
        monkeypatch, host_id=_HOST_ID, branch=_chain_branch(), people=_PEOPLE
    )
    assert (contact["contact_name"], contact["contact_detail"]) == (
        "Rahul Verma",
        "+91 90000 33344",
    )


async def test_contact_chain_falls_back_to_the_branch_contact_person(monkeypatch) -> None:
    contact = await _contact_for(monkeypatch, branch=_chain_branch(), people=_PEOPLE)
    assert (contact["contact_name"], contact["contact_detail"]) == (
        "Anil Menon",
        "+91 90000 55566",
    )
    assert contact["contact_title"] == "Your point of contact"


async def test_contact_chain_falls_back_to_the_front_desk(monkeypatch) -> None:
    contact = await _contact_for(
        monkeypatch, branch=_chain_branch(contact_person_user_id=None), people=_PEOPLE
    )
    assert (contact["contact_name"], contact["contact_detail"]) == ("Front desk", "+91 80000 22233")


async def test_contact_chain_ends_at_reception_when_nothing_is_configured(monkeypatch) -> None:
    contact = await _contact_for(
        monkeypatch, branch=_chain_branch(contact_person_user_id=None), front_desk=None
    )
    assert contact == {
        "contact_title": "Your point of contact",
        "contact_name": "Reception at Main Branch",
        "contact_detail": None,
    }


async def test_contact_chain_reception_without_a_branch(monkeypatch) -> None:
    contact = await _contact_for(monkeypatch, branch=None, front_desk=None)
    assert contact["contact_name"] == "Reception"


async def test_contact_chain_skips_untrustworthy_names(monkeypatch) -> None:
    """An opaque IdP subject as the host's name, and a branch contact whose
    "name" is just their email, are both skipped — the front desk wins."""
    people = {
        _HOST_ID: _person("ccbb9a1e304730e0512d912e18f6ce65", phone="+91 1"),
        _BRANCH_CONTACT_ID: _person("anil@example.com", email="anil@example.com"),
    }
    contact = await _contact_for(
        monkeypatch,
        poc_name="  ",
        host_id=_HOST_ID,
        branch=_chain_branch(),
        people=people,
    )
    assert contact["contact_name"] == "Front desk"


async def test_confirmation_without_poc_or_host_names_the_branch_contact_person(
    monkeypatch,
) -> None:
    """email-notifications "No POC or host falls back to the branch contact
    person", end to end through the task's rendering."""
    sent: list[dict] = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fakes = _realistic_email_fakes()
    branch, department, building = fakes["location"]
    branch.contact_person_user_id = _BRANCH_CONTACT_ID
    monkeypatch.setattr(tasks, "UserRepository", _UsersById(_PEOPLE))
    fake_invitation = _FakeInvitation(
        id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        status="approved",
        tracking_id="INV-CONTACT1",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
    )
    monkeypatch.setattr(
        tasks,
        "tenant_session_scope",
        _fake_tenant_session_scope(
            fake_invitation, company=fakes["company"], location=(branch, department, building)
        ),
    )

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(fake_invitation.id),
            "qr_token": "fake-qr-token",
        },
    )
    result.get(propagate=True)

    [email] = sent
    assert "Your point of contact" in email["html_body"]
    assert "Anil Menon" in email["html_body"]
    assert "+91 90000 55566" in email["html_body"]


# --- restrict-delegated-invitation-visibility ----------------------------------


async def _get_or_create_permission(db_session: AsyncSession, code: str) -> Permission:
    """Global `permissions.code` is unique, so reuse a row another fixture
    (e.g. `user`) may already have created instead of colliding with it.
    """
    existing = (
        await db_session.execute(select(Permission).where(Permission.code == code))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    permission = PermissionFactory.build(id=uuid.uuid4(), code=code, description=code)
    db_session.add(permission)
    await db_session.flush()
    return permission


async def _host_role(db_session: AsyncSession):
    """The standard `host` role — delegation-only, holding `invitations:view`
    but not `invitations:view-all`, same as `auth/rbac_catalog.py` seeds it.
    """
    role = RoleFactory.build(
        id=uuid.uuid4(),
        name="host",
        permissions=[await _get_or_create_permission(db_session, "invitations:view")],
    )
    db_session.add(role)
    await db_session.flush()
    return role


async def _reception_to_host_invitation(
    db_session: AsyncSession,
    branch_id: uuid.UUID,
    host_role,
    *,
    step0_actor: User,
    resolved_host: User | None = None,
):
    """A `submitted` reception → host invitation whose `stepOrder` 0 step
    (default host role) is already approved by `step0_actor` and whose
    `stepOrder` 1 step (`host` role) is current and undelegated — the state
    the dev tenant's workflow sits in after Reception's own step is done.
    `resolved_host` models step 0 having been delegated to (and approved by)
    that host. Every step field the relevance rule reads is pinned, not left
    to the factory's RNG.
    """
    reception = await RoleRepository(db_session).get_by_name("reception")
    assert reception is not None
    invitation = _build_invitation(
        db_session,
        branch_id,
        status="submitted",
        approved_at=None,
        host_id=resolved_host.id if resolved_host is not None else None,
    )
    db_session.add(invitation)
    await db_session.flush()
    step1 = InvitationApprovalStepFactory.build(
        id=uuid.uuid4(),
        invitation_id=invitation.id,
        step_order=1,
        approver_role_id=host_role.id,
        approver_user_id=None,
        status="pending",
        acted_by_user_id=None,
        acted_at=None,
        delegated_to_user_id=None,
        delegated_by_user_id=None,
        delegated_at=None,
    )
    db_session.add_all(
        [
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                step_order=0,
                approver_role_id=reception.id,
                approver_user_id=None,
                status="approved",
                acted_by_user_id=step0_actor.id,
                acted_at=datetime.now(UTC),
                delegated_to_user_id=resolved_host.id if resolved_host is not None else None,
                delegated_by_user_id=None,
                delegated_at=None,
            ),
            step1,
        ]
    )
    await db_session.commit()
    return invitation, step1


async def _reception_holder(db_session: AsyncSession, branch_id: uuid.UUID) -> User:
    reception = await RoleRepository(db_session).get_by_name("reception")
    assert reception is not None
    return _make_role_holder(db_session, reception, branch_id)


async def _relevant_tracking_ids(
    client: AsyncClient, issue_token: Callable[[User], str], caller: User
) -> set[str]:
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {issue_token(caller)}"},
    )
    assert response.status_code == 200, response.text
    return {row["trackingId"] for row in response.json()["data"]}


async def _get_detail(
    client: AsyncClient, issue_token: Callable[[User], str], caller: User, invitation_id
) -> Response:
    return await client.get(
        f"/api/v1/invitations/{invitation_id}",
        headers={"Authorization": f"Bearer {issue_token(caller)}"},
    )


async def test_relevant_to_me_unassigned_host_step_not_broadcast_to_other_hosts(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "An unassigned host-role step is not broadcast to every host"
    and "The delegate and Reception still see an unassigned host-role step".
    """
    host_role = await _host_role(db_session)
    host_x = _make_role_holder(db_session, host_role, branch.id)
    host_y = _make_role_holder(db_session, host_role, branch.id)
    receptionist = await _reception_holder(db_session, branch.id)
    await db_session.flush()
    invitation, _ = await _reception_to_host_invitation(
        db_session, branch.id, host_role, step0_actor=host_x, resolved_host=host_x
    )

    assert invitation.tracking_id not in await _relevant_tracking_ids(client, issue_token, host_y)
    assert invitation.tracking_id in await _relevant_tracking_ids(client, issue_token, host_x)
    assert invitation.tracking_id in await _relevant_tracking_ids(client, issue_token, receptionist)


async def test_relevant_to_me_approve_then_delegate_never_exposes_host_step_to_other_hosts(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "Approve-and-delegate never exposes the next host step to
    other hosts" — covers the gap between the web's approve and delegate
    calls, and the state after the delegate call.
    """
    host_role = await _host_role(db_session)
    host_x = _make_role_holder(db_session, host_role, branch.id)
    host_y = _make_role_holder(db_session, host_role, branch.id)
    receptionist = await _reception_holder(db_session, branch.id)
    await db_session.flush()
    invitation, step1 = await _reception_to_host_invitation(
        db_session, branch.id, host_role, step0_actor=receptionist
    )

    assert invitation.tracking_id not in await _relevant_tracking_ids(client, issue_token, host_y)
    assert invitation.tracking_id not in await _relevant_tracking_ids(client, issue_token, host_x)

    await InvitationApprovalStepRepository(db_session).delegate_if_eligible(
        step1.id, delegated_to_user_id=host_x.id, delegated_by_user_id=receptionist.id
    )
    await db_session.commit()

    assert invitation.tracking_id in await _relevant_tracking_ids(client, issue_token, host_x)
    assert invitation.tracking_id not in await _relevant_tracking_ids(client, issue_token, host_y)


async def test_list_invitations_branch_listing_rejects_host_without_view_all(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "A host holding only invitations:view cannot use the
    branch-wide listing" — permission-denied case for the narrowed gate.
    """
    host_role = await _host_role(db_session)
    host = _make_role_holder(db_session, host_role, branch.id)
    db_session.add(_build_invitation(db_session, branch.id))
    await db_session.commit()
    token = issue_token(host)

    for headers in (
        {"Authorization": f"Bearer {token}"},
        {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    ):
        response = await client.get("/api/v1/invitations", headers=headers)
        assert response.status_code == 403, response.text


async def test_invitation_detail_visible_to_reception_and_delegate_only(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "Reception opens any invitation at their branch", "The
    assigned user opens the invitation delegated to them", and "An
    uninvolved host cannot open a delegated invitation".
    """
    host_role = await _host_role(db_session)
    host_x = _make_role_holder(db_session, host_role, branch.id)
    host_y = _make_role_holder(db_session, host_role, branch.id)
    receptionist = await _reception_holder(db_session, branch.id)
    await db_session.flush()
    invitation, step1 = await _reception_to_host_invitation(
        db_session, branch.id, host_role, step0_actor=receptionist
    )
    await InvitationApprovalStepRepository(db_session).delegate_if_eligible(
        step1.id, delegated_to_user_id=host_x.id, delegated_by_user_id=receptionist.id
    )
    await db_session.commit()

    for caller in (receptionist, host_x):
        response = await _get_detail(client, issue_token, caller, invitation.id)
        assert response.status_code == 200, response.text
        assert response.json()["data"]["trackingId"] == invitation.tracking_id

    response = await _get_detail(client, issue_token, host_y, invitation.id)
    assert response.status_code == 404, response.text
    assert "data" not in response.json() or response.json()["data"] is None


async def test_invitation_detail_uninvolved_host_gets_404_for_unassigned_host_step(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "An uninvolved host cannot open an unassigned host-role
    step's invitation".
    """
    host_role = await _host_role(db_session)
    host_y = _make_role_holder(db_session, host_role, branch.id)
    receptionist = await _reception_holder(db_session, branch.id)
    await db_session.flush()
    invitation, _ = await _reception_to_host_invitation(
        db_session, branch.id, host_role, step0_actor=receptionist
    )

    response = await _get_detail(client, issue_token, host_y, invitation.id)
    assert response.status_code == 404, response.text


async def test_invitation_detail_delegate_without_any_grant_can_open_it(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "A delegate without invitations:view still opens their
    invitation" — the participant path skips the branch-permission check,
    same as `relevantToMe`.
    """
    host_role = await _host_role(db_session)
    receptionist = await _reception_holder(db_session, branch.id)
    delegate = UserFactory.build(
        id=uuid.uuid4(),
        email=f"delegate-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Delegate",
    )
    db_session.add(delegate)
    await db_session.flush()
    invitation, step1 = await _reception_to_host_invitation(
        db_session, branch.id, host_role, step0_actor=receptionist
    )
    await InvitationApprovalStepRepository(db_session).delegate_if_eligible(
        step1.id, delegated_to_user_id=delegate.id, delegated_by_user_id=receptionist.id
    )
    await db_session.commit()

    response = await _get_detail(client, issue_token, delegate, invitation.id)
    assert response.status_code == 200, response.text


async def test_invitation_detail_branch_wide_viewer_sees_uninvolved_invitation(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "Security and Admin keep branch-wide detail access" — any
    `invitations:view-all` holder at the branch, without participating.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, role)
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)

    response = await _get_detail(client, issue_token, viewer, invitation.id)
    assert response.status_code == 200, response.text


async def test_invitation_detail_caller_without_any_grant_gets_403(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    user_without_permissions: User,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "A caller with no viewing grant is still rejected with 403" —
    unchanged status code for the pre-existing condition.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, role)

    response = await _get_detail(client, issue_token, user_without_permissions, invitation.id)
    assert response.status_code == 403, response.text


async def test_invitation_detail_unknown_id_is_404(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "Detail from another tenant is never reachable" at the API
    level — an id absent from the caller's own tenant schema is 404; the
    schema-level isolation is covered directly below.
    """
    receptionist = await _reception_holder(db_session, branch.id)
    await db_session.commit()

    response = await _get_detail(client, issue_token, receptionist, uuid.uuid4())
    assert response.status_code == 404, response.text


async def test_is_relevant_to_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    """testing-standards.md §2 — the detail endpoint's participant check,
    run against another tenant's schema, never matches this tenant's
    invitation even for the same user and invitation ids.
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    invitation = await _invitation_with_host_step(db_session, branch.id, host)
    default_host_role_id = uuid.uuid4()
    assert await InvitationRepository(db_session).is_relevant_to(
        invitation.id, user_id=host.id, default_host_role_id=default_host_role_id
    )

    other_schema = "tenant_other_test_invitation_is_relevant_to"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        assert not await InvitationRepository(other_session).is_relevant_to(
            invitation.id, user_id=host.id, default_host_role_id=default_host_role_id
        )


# --- add-sms-numeric-checkin-code ---------------------------------------------


class _FakeRedis:
    """In-memory stand-in for the two Redis calls `code_lockout` makes, so the
    lockout tests don't leak per-IP failure counters between runs."""

    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def incr(self, key: str) -> int:
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    async def expire(self, key: str, seconds: int) -> None:
        return None


@pytest.fixture
def fake_lockout_redis(monkeypatch) -> _FakeRedis:
    fake = _FakeRedis()

    async def _get_redis() -> _FakeRedis:
        return fake

    monkeypatch.setattr(code_lockout, "get_redis", _get_redis)
    return fake


def _sms_invitation(db_session: AsyncSession, branch_id: uuid.UUID, code: str, **overrides):
    overrides.setdefault("primary_contact_preferred_contact_method", "sms")
    overrides.setdefault("primary_contact_phone", "+919876543210")
    return _approved_invitation(db_session, branch_id, checkin_code=code, **overrides)


async def test_issue_checkin_code_only_for_sms_contacts_and_is_stable(
    tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "SMS-Preferred Approved Invitation Gets a Numeric Check-In Code"."""
    sms = _approved_invitation(
        db_session, branch.id, primary_contact_preferred_contact_method="sms"
    )
    email = _approved_invitation(
        db_session, branch.id, primary_contact_preferred_contact_method="email"
    )
    whatsapp = _approved_invitation(
        db_session, branch.id, primary_contact_preferred_contact_method="whatsapp"
    )
    sms.checkin_code = email.checkin_code = whatsapp.checkin_code = None
    db_session.add_all([sms, email, whatsapp])
    await db_session.commit()

    for invitation in (sms, email, whatsapp):
        await invitations_service._issue_checkin_code(db_session, invitation)
    assert sms.checkin_code is not None
    assert re.fullmatch(r"\d{8}", sms.checkin_code)
    assert email.checkin_code is None
    assert whatsapp.checkin_code is None

    first = sms.checkin_code
    await invitations_service._issue_checkin_code(db_session, sms)
    assert sms.checkin_code == first


async def test_generate_unique_checkin_code_retries_on_collision(
    branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    taken = _sms_invitation(db_session, branch.id, "00000001")
    db_session.add(taken)
    await db_session.commit()

    draws = iter([1, 2])
    monkeypatch.setattr(invitations_service.secrets, "randbelow", lambda _n: next(draws))
    code = await invitations_service._generate_unique_checkin_code(InvitationRepository(db_session))
    assert code == "00000002"


async def test_send_approval_notification_sms_sends_code_template(monkeypatch) -> None:
    """specs "Approval SMS Carries the Check-In Code Instead of a QR"."""
    sms_sent: list[dict] = []

    class _RecordingSmsSender:
        async def send(self, **kwargs):
            sms_sent.append(kwargs)

    monkeypatch.setattr(notifications, "sms_sender", _RecordingSmsSender())
    fake_invitation = _FakeInvitation(
        id=uuid.uuid4(),
        status="approved",
        tracking_id="INV-TEST0010",
        checkin_code="12345678",
        primary_contact_preferred_contact_method="sms",
        primary_contact_email=None,
        primary_contact_phone="+919876543210",
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(fake_invitation.id),
            "qr_token": "fake-qr-token",
        },
    )
    result.get(propagate=True)

    assert len(sms_sent) == 1
    assert sms_sent[0]["template"] == SmsTemplate.registration_confirmed_code
    assert sms_sent[0]["variables"] == ["INV-TEST0010", "12345678"]


async def test_send_approval_notification_sms_code_template_not_configured_not_retried(
    monkeypatch,
) -> None:
    """The real sender with no template ID configured fails as not-configured,
    which `send_approval_notification` excludes from autoretry."""
    monkeypatch.setattr(settings, "fast2sms_api_key", "k")
    monkeypatch.setattr(settings, "fast2sms_sender_id", "S")
    monkeypatch.setattr(settings, "fast2sms_template_registration_confirmed_code", None)
    monkeypatch.setattr(notifications, "sms_sender", notifications.Fast2SmsSender())
    fake_invitation = _FakeInvitation(
        id=uuid.uuid4(),
        status="approved",
        tracking_id="INV-TEST0011",
        checkin_code="12345678",
        primary_contact_preferred_contact_method="sms",
        primary_contact_email=None,
        primary_contact_phone="+919876543210",
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(fake_invitation.id),
            "qr_token": "fake-qr-token",
        },
    )
    assert result.failed()
    assert result.traceback is not None and "SmsNotConfiguredError" in result.traceback


async def test_check_in_by_code_full_lifecycle(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    fake_lockout_redis,
) -> None:
    invitation = _sms_invitation(db_session, branch.id, "11112222")
    db_session.add(invitation)
    await db_session.commit()
    body = {"code": "11112222"}

    check_in = await client.patch("/api/v2/invitations/code/check-in", json=body)
    assert check_in.status_code == 200
    assert check_in.json()["data"]["checkInStatus"] == "checked_in"

    repeat = await client.patch("/api/v2/invitations/code/check-in", json=body)
    assert repeat.status_code == 200
    await db_session.refresh(invitation)
    assert invitation.check_in_status == "checked_in"

    check_out = await client.patch("/api/v2/invitations/code/check-out", json=body)
    assert check_out.status_code == 200
    assert check_out.json()["message"] == "Checked out successfully"

    not_in = await client.patch("/api/v2/invitations/code/check-out", json=body)
    assert not_in.status_code == 409

    re_entry = await client.patch("/api/v2/invitations/code/check-in", json=body)
    assert re_entry.status_code == 200
    assert re_entry.json()["data"]["checkInStatus"] == "checked_in"


async def _code_device(db_session: AsyncSession, branch: Branch, **overrides):
    from factories import DeviceFactory

    device = DeviceFactory.build(id=uuid.uuid4(), branch_id=branch.id, **overrides)
    db_session.add(device)
    await db_session.commit()
    return device


async def test_code_check_in_and_check_out_record_devices(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    fake_lockout_redis,
) -> None:
    entry = await _code_device(db_session, branch, name="Entry")
    exit_ = await _code_device(db_session, branch, name="Exit")
    invitation = _sms_invitation(db_session, branch.id, "44445555")
    db_session.add(invitation)
    await db_session.commit()
    body = {"code": "44445555"}

    checked_in = await client.patch(
        "/api/v2/invitations/code/check-in", json=body, headers={"device-id": entry.device_id}
    )
    assert checked_in.status_code == 200
    assert checked_in.json()["data"]["checkInDevice"]["name"] == "Entry"

    repeat = await client.patch(
        "/api/v2/invitations/code/check-in", json=body, headers={"device-id": exit_.device_id}
    )
    assert repeat.json()["data"]["checkInDevice"]["name"] == "Entry"

    checked_out = await client.patch(
        "/api/v2/invitations/code/check-out", json=body, headers={"device-id": exit_.device_id}
    )
    data = checked_out.json()["data"]
    assert data["checkInDevice"]["name"] == "Entry"
    assert data["checkOutDevice"]["name"] == "Exit"


async def test_code_check_in_without_device_header_leaves_devices_null(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    fake_lockout_redis,
) -> None:
    invitation = _sms_invitation(db_session, branch.id, "55556666")
    db_session.add(invitation)
    await db_session.commit()

    response = await client.patch("/api/v2/invitations/code/check-in", json={"code": "55556666"})
    assert response.status_code == 200
    assert response.json()["data"]["checkInDevice"] is None


async def test_code_check_in_rejects_unusable_device_without_state_change(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    fake_lockout_redis,
) -> None:
    pending = await _code_device(db_session, branch, approval_status="pending", is_active=False)
    invitation = _sms_invitation(db_session, branch.id, "66667777")
    db_session.add(invitation)
    await db_session.commit()

    for device_id in (pending.device_id, "never-registered"):
        for action in ("check-in", "check-out"):
            response = await client.patch(
                f"/api/v2/invitations/code/{action}",
                json={"code": "66667777"},
                headers={"device-id": device_id},
            )
            assert response.status_code == 403
    await db_session.refresh(invitation)
    assert invitation.check_in_status == "unused"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"expires_at": datetime.now(UTC) - timedelta(minutes=1)}, 410),
        ({"preferred_visit_date": date.today() + timedelta(days=30)}, 425),
        ({"watchlist_flagged": True}, 409),
    ],
)
async def test_check_in_by_code_rejections(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    fake_lockout_redis,
    overrides: dict,
    expected: int,
) -> None:
    invitation = _sms_invitation(db_session, branch.id, "22223333", **overrides)
    db_session.add(invitation)
    await db_session.commit()

    response = await client.patch("/api/v2/invitations/code/check-in", json={"code": "22223333"})
    assert response.status_code == expected


async def test_check_in_by_code_unknown_and_malformed(
    client: AsyncClient, tenant: Tenant, fake_lockout_redis
) -> None:
    unknown = await client.patch("/api/v2/invitations/code/check-in", json={"code": "99999999"})
    assert unknown.status_code == 400
    assert "invalid code" in unknown.json()["message"].lower()
    for bad in ("1234", "abcdefgh", "123456789"):
        response = await client.patch("/api/v2/invitations/code/check-in", json={"code": bad})
        assert response.status_code == 422


async def test_check_in_by_code_locks_out_ip_after_repeated_failures(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    fake_lockout_redis,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "checkin_code_max_failures", 3)
    invitation = _sms_invitation(db_session, branch.id, "33334444")
    db_session.add(invitation)
    await db_session.commit()

    for _ in range(3):
        wrong = await client.patch("/api/v2/invitations/code/check-in", json={"code": "00000000"})
        assert wrong.status_code == 400

    locked = await client.patch("/api/v2/invitations/code/check-in", json={"code": "33334444"})
    assert locked.status_code == 429
    await db_session.refresh(invitation)
    assert invitation.check_in_status == "unused"


async def test_qr_check_in_still_works_for_sms_invitation(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _sms_invitation(db_session, branch.id, "44445555")
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    assert (await client.patch(f"/api/v2/invitations/qr/{token}/check-in")).status_code == 200
    assert (await client.patch(f"/api/v2/invitations/qr/{token}/check-out")).status_code == 200


# --- expire-invitation-at-end-of-visit-day ------------------------------------
# `expiresAt` is 23:59:59 on the visit day in the visit timezone
# (company `default_timezone` → tenant `timezone` → UTC), recomputed whenever
# the visit date actually changes. The `tenant` fixture is pinned to UTC, so
# a company zone of Asia/Kolkata is what distinguishes the two precedence
# levels here.

_KOLKATA = "Asia/Kolkata"


def test_end_of_visit_day_utc_is_end_of_day_in_given_zone() -> None:
    visit = date(2026, 10, 2)
    assert invitations_service._end_of_visit_day_utc(visit, ZoneInfo(_KOLKATA)) == datetime(
        2026, 10, 2, 18, 29, 59, tzinfo=UTC
    )
    assert invitations_service._end_of_visit_day_utc(visit, ZoneInfo("UTC")) == datetime(
        2026, 10, 2, 23, 59, 59, tzinfo=UTC
    )


@pytest.mark.parametrize(
    ("company", "tenant_tz", "expected"),
    [
        (SimpleNamespace(default_timezone=_KOLKATA), "UTC", _KOLKATA),
        (SimpleNamespace(default_timezone=None), _KOLKATA, _KOLKATA),
        (None, _KOLKATA, _KOLKATA),
        # A region directory, not a zone — `ZoneInfo` raises `IsADirectoryError`.
        (SimpleNamespace(default_timezone="Asia"), _KOLKATA, _KOLKATA),
        (SimpleNamespace(default_timezone="Not/AZone"), _KOLKATA, _KOLKATA),
        (SimpleNamespace(default_timezone="bogus"), "also-bogus", "UTC"),
    ],
)
def test_visit_timezone_precedence(company: Any, tenant_tz: str, expected: str) -> None:
    tz = invitations_service._visit_timezone(company, SimpleNamespace(timezone=tenant_tz))
    assert tz.key == expected


async def test_create_invitation_expires_at_end_of_visit_day_in_company_timezone(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    db_session.add(
        CompanyFactory.build(
            id=uuid.uuid4(),
            default_timezone=_KOLKATA,
            auto_approve_pre_registered_visitors=False,
        )
    )
    await db_session.commit()
    monkeypatch.setattr(tasks.send_tracking_notification, "delay", lambda **kw: None)

    building = BuildingFactory.build(id=uuid.uuid4(), branch_id=branch.id)
    db_session.add(building)
    await db_session.commit()
    payload = _individual_payload()
    payload["visitDetails"]["branchId"] = str(branch.id)
    payload["visitDetails"]["buildingId"] = str(building.id)
    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=payload)

    # `_individual_payload()` schedules 2026-08-12 10:00 — expiry ignores both
    # the visit time and the submission time.
    assert datetime.fromisoformat(data["expiresAt"]) == datetime(
        2026, 8, 12, 18, 29, 59, tzinfo=UTC
    )


async def test_create_invitation_without_company_falls_back_to_tenant_timezone(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(tasks.send_tracking_notification, "delay", lambda **kw: None)

    building = BuildingFactory.build(id=uuid.uuid4(), branch_id=branch.id)
    db_session.add(building)
    await db_session.commit()
    payload = _individual_payload()
    payload["visitDetails"]["branchId"] = str(branch.id)
    payload["visitDetails"]["buildingId"] = str(building.id)
    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=payload)

    assert datetime.fromisoformat(data["expiresAt"]) == datetime(
        2026, 8, 12, 23, 59, 59, tzinfo=UTC
    )


@pytest.mark.parametrize("initial_status", ["submitted", "approved"])
async def test_reschedule_moves_expiry_to_end_of_new_visit_day(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    initial_status: str,
) -> None:
    """A `submitted` invitation used to keep the old day's expiry on
    reschedule; both statuses now realign.
    """
    monkeypatch.setattr(tasks.send_reschedule_notification, "delay", lambda **kw: None)
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), default_timezone=_KOLKATA))
    invitation = _build_invitation(
        db_session,
        branch.id,
        status=initial_status,
        approved_at=datetime.now(UTC) if initial_status == "approved" else None,
        preferred_visit_date=date(2026, 10, 2),
        expires_at=datetime(2026, 10, 2, 18, 29, 59, tzinfo=UTC),
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/reschedule",
        json={"preferredVisitDate": "2026-10-20", "preferredVisitTime": "11:00:00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    await db_session.refresh(invitation)
    assert invitation.expires_at == datetime(2026, 10, 20, 18, 29, 59, tzinfo=UTC)


async def test_edit_changing_visit_date_moves_expiry(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: None)
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), default_timezone=_KOLKATA))
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="submitted",
        preferred_visit_date=date(2026, 10, 2),
        expires_at=datetime(2026, 10, 2, 18, 29, 59, tzinfo=UTC),
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"preferredVisitDate": "2026-10-03"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    await db_session.refresh(invitation)
    assert invitation.expires_at == datetime(2026, 10, 3, 18, 29, 59, tzinfo=UTC)


async def test_edit_resending_same_visit_date_keeps_extended_expiry(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """The edit modal resubmits the whole form, unchanged date included —
    that must not wipe a staff expiry extension.
    """
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: None)
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), default_timezone=_KOLKATA))
    extended = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        preferred_visit_date=date(2026, 10, 2),
        expires_at=extended,
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/edit",
        json={"preferredVisitDate": "2026-10-02", "additionalNotes": "Bring a laptop"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    await db_session.refresh(invitation)
    assert invitation.additional_notes == "Bring a laptop"
    assert invitation.expires_at == extended


async def test_qr_check_in_visit_date_gate_uses_company_timezone(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """00:30 IST on the visit day is still the previous day in UTC (the
    tenant's zone) — the gate must agree with the expiry's company zone
    and let the visitor in rather than answer 425.
    """

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return datetime(2026, 10, 1, 19, 0, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(invitations_service, "datetime", _FrozenDatetime)
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), default_timezone=_KOLKATA))
    invitation = _approved_invitation(
        db_session,
        branch.id,
        preferred_visit_date=date(2026, 10, 2),
        # The repository's own expiry check reads the real clock.
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    assert (await client.patch(f"/api/v2/invitations/qr/{token}/check-in")).status_code == 200
    assert (await client.patch(f"/api/v2/invitations/qr/{token}/check-out")).status_code == 200


async def test_checkin_code_tenant_isolation(
    branch: Branch,
    db_session: AsyncSession,
    make_tenant_schema,
    open_tenant_session,
) -> None:
    invitation = _sms_invitation(db_session, branch.id, "55556666")
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_checkin_code_test"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        assert await InvitationRepository(other_session).get_by_checkin_code("55556666") is None


async def test_whatsapp_confirmed_uploads_qr_png_and_sends_media_id_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    from vmss_api.core import whatsapp as whatsapp_module
    from vmss_api.core.config import settings

    monkeypatch.setattr(settings, "fast2sms_api_key", "k")
    monkeypatch.setattr(settings, "fast2sms_whatsapp_phone_number_id", "123")
    monkeypatch.setattr(settings, "fast2sms_whatsapp_template_registration_confirmed", "qr")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/media"):
            return httpx.Response(200, json={"id": "MEDIA1"})
        return httpx.Response(200, json={"messages": [{"id": "wamid.1"}]})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        whatsapp_module.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    await whatsapp_module.Fast2WhatsAppSender().send(
        to="9876543210",
        template=whatsapp_module.WhatsAppTemplate.registration_confirmed,
        variables=["Asha", "INV-1", "15 Oct 2026"],
        header_image_png=b"\x89PNG",
    )
    assert requests[0].url.path.endswith("/media")
    sent = json.loads(requests[1].content)
    components = sent["template"]["components"]
    assert components[0] == {
        "type": "header",
        "parameters": [{"type": "image", "image": {"id": "MEDIA1"}}],
    }
    assert [p["text"] for p in components[1]["parameters"]] == ["Asha", "INV-1", "15 Oct 2026"]


async def test_visit_timezone_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, tenant: Tenant, db_session: AsyncSession
) -> None:
    """One tenant's company timezone must never leak into another tenant's
    expiry — the company lookup resolves against the session's own schema.
    """
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), default_timezone=_KOLKATA))
    await db_session.commit()
    assert (await invitations_service._resolve_visit_timezone(db_session, tenant)).key == _KOLKATA

    other_schema = "tenant_other_test_visit_timezone"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        tz = await invitations_service._resolve_visit_timezone(other_session, tenant)
    assert tz.key == "UTC"


# --- grant-reception-checkout-permission --------------------------------------


def _checked_in_invitation(db_session: AsyncSession, branch_id: uuid.UUID):
    invitation = _build_invitation(
        db_session,
        branch_id,
        status="checked_in",
        check_in_status="checked_in",
        approved_at=datetime.now(UTC),
        checked_in_at=datetime.now(UTC),
    )
    db_session.add(invitation)
    return invitation


async def test_reception_checks_out_checked_in_visitor(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """auth spec "Reception checks out a checked-in visitor" — goes through
    `seed_default_roles` so this exercises the catalog default itself.
    """
    await seed_default_roles(db_session)
    receptionist = await _reception_holder(db_session, branch.id)
    invitation = _checked_in_invitation(db_session, branch.id)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/check-out",
        headers={"Authorization": f"Bearer {issue_token(receptionist)}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "checked_out"

    await db_session.refresh(invitation)
    assert invitation.status == "checked_out"
    assert invitation.checked_out_by_user_id == receptionist.id


async def test_reception_cannot_check_out_at_another_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """auth spec "Reception at a different branch is still rejected"."""
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-CHECKOUT")
    db_session.add(other_branch)
    await seed_default_roles(db_session)
    receptionist = await _reception_holder(db_session, branch.id)
    invitation = _checked_in_invitation(db_session, other_branch.id)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/check-out",
        headers={"Authorization": f"Bearer {issue_token(receptionist)}"},
    )
    assert response.status_code == 403, response.text

    await db_session.refresh(invitation)
    assert invitation.status == "checked_in"


async def test_host_cannot_check_out_visitor(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """auth spec "Host still cannot check visitors out"."""
    await seed_default_roles(db_session)
    host_role = await RoleRepository(db_session).get_by_name("host")
    assert host_role is not None
    host = _make_role_holder(db_session, host_role, branch.id)
    invitation = _checked_in_invitation(db_session, branch.id)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/check-out",
        headers={"Authorization": f"Bearer {issue_token(host)}"},
    )
    assert response.status_code == 403, response.text

    await db_session.refresh(invitation)
    assert invitation.status == "checked_in"


# --- add-invitation-approval-revert: PATCH /invitations/{id}/revert-approval --


async def _branch_scoped_user_with(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID, codes: tuple[str, ...]
) -> User:
    """A caller holding exactly `codes` at `branch_id`. Get-or-create on each
    `Permission` because `code` is unique across the global catalog and the
    `user` fixture (Admin) may already have inserted the same code in this
    test.
    """
    permissions = []
    for code in codes:
        existing = (
            await db_session.execute(select(Permission).where(Permission.code == code))
        ).scalar_one_or_none()
        if existing is None:
            existing = PermissionFactory.build(id=uuid.uuid4(), code=code, description=code)
            db_session.add(existing)
        permissions.append(existing)
    role = RoleFactory.build(
        id=uuid.uuid4(), name=f"revert-test-{uuid.uuid4().hex[:8]}", permissions=permissions
    )
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"revert-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Revert Caller",
        branch_roles=[branch_role],
    )
    db_session.add_all([role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


def _capture_revert_dispatch(monkeypatch) -> tuple[list[dict], list[dict]]:
    """Captures `(revert_email_calls, host_push_calls)`."""
    email_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_revert_notification, "delay", lambda **kw: email_calls.append(kw)
    )
    push_calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        push_calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)
    return email_calls, push_calls


async def _revert(
    client: AsyncClient, token: str, invitation_id: uuid.UUID, reason: Any
) -> Response:
    return await client.patch(
        f"/api/v1/invitations/{invitation_id}/revert-approval",
        json={"reason": reason},
        headers={"Authorization": f"Bearer {token}"},
    )


async def test_revert_approval_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host = _make_host(db_session)
    db_session.add(host)
    await db_session.flush()
    invitation = _approved_invitation(db_session, branch.id, host_id=host.id)
    db_session.add(invitation)
    await db_session.commit()
    # Plain ids up front: the shared test session's `get_tenant` rollback
    # expires ORM objects mid-request (see `0c4d1c1`).
    host_id, invitation_id, user_id = host.id, invitation.id, user.id
    email_calls, push_calls = _capture_revert_dispatch(monkeypatch)

    token = await _login(client, user.email)
    response = await _revert(client, token, invitation_id, "  Approved the wrong visitor  ")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "submitted"
    assert data["approvedAt"] is None
    assert data["approvalRevertedAt"] is not None
    assert data["approvalRevertedByUserId"] == str(user_id)
    assert data["approvalRevertReason"] == "Approved the wrong visitor"

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"
    assert invitation.approved_at is None
    assert invitation.approval_revert_reason == "Approved the wrong visitor"
    assert [c["invitation_id"] for c in email_calls] == [str(invitation_id)]
    assert len(push_calls) == 1
    assert push_calls[0]["user_id"] == host_id
    assert push_calls[0]["data"]["action"] == "approval_reverted"

    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "invitation_approval_reverted",
                AuditLog.entity_id == invitation_id,
            )
        )
    ).scalar_one()
    assert audit.actor_user_id == user_id


async def test_revert_approval_auto_approved_invitation_can_be_reapproved_or_denied(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """An auto-approved invitation has no steps, so after a revert the
    blanket approve endpoint (and deny) work on it again."""
    approve_target = _approved_invitation(db_session, branch.id)
    deny_target = _approved_invitation(db_session, branch.id)
    db_session.add_all([approve_target, deny_target])
    await db_session.commit()
    _capture_revert_dispatch(monkeypatch)
    monkeypatch.setattr(tasks.send_approval_notification, "delay", lambda **kw: None)
    monkeypatch.setattr(tasks.send_denial_notification, "delay", lambda **kw: None)

    approve_id, deny_id = approve_target.id, deny_target.id

    token = await _login(client, user.email)
    for target_id in (approve_id, deny_id):
        assert (await _revert(client, token, target_id, "Mistake")).status_code == 200

    response = await client.post(
        f"/api/v1/invitations/{approve_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "approved"

    response = await client.patch(
        f"/api/v1/invitations/{deny_id}/deny",
        json={"reason": "Not expected after all"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "denied"


async def test_revert_approval_without_host_skips_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    invitation = _approved_invitation(db_session, branch.id, host_id=None)
    db_session.add(invitation)
    await db_session.commit()
    email_calls, push_calls = _capture_revert_dispatch(monkeypatch)

    token = await _login(client, user.email)
    response = await _revert(client, token, invitation.id, "Mistake")
    assert response.status_code == 200, response.text
    assert push_calls == []
    assert len(email_calls) == 1


@pytest.mark.parametrize("reason", [None, "", "   ", "x" * 501])
async def test_revert_approval_invalid_reason_rejected(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    reason: str | None,
) -> None:
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    email_calls, _ = _capture_revert_dispatch(monkeypatch)

    token = await _login(client, user.email)
    response = await _revert(client, token, invitation.id, reason)
    assert response.status_code == 422

    await db_session.refresh(invitation)
    assert invitation.status == "approved"
    assert email_calls == []


@pytest.mark.parametrize(
    ("status_value", "check_in_status"),
    [
        ("submitted", "unused"),
        ("denied", "unused"),
        ("checked_in", "checked_in"),
        ("checked_out", "checked_out"),
        # Approved, but the visitor has already entered at some point.
        ("approved", "checked_out"),
    ],
)
async def test_revert_approval_ineligible_state_conflicts(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    status_value: str,
    check_in_status: str,
) -> None:
    invitation = _approved_invitation(
        db_session, branch.id, status=status_value, check_in_status=check_in_status
    )
    db_session.add(invitation)
    await db_session.commit()
    email_calls, push_calls = _capture_revert_dispatch(monkeypatch)

    token = await _login(client, user.email)
    response = await _revert(client, token, invitation.id, "Mistake")
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == status_value
    assert invitation.approval_reverted_at is None
    assert email_calls == []
    assert push_calls == []


@pytest.mark.parametrize(
    "codes",
    [
        # Security's default grants: no revert permission.
        ("invitations:view", "invitations:checkin", "invitations:checkout"),
        # Can approve, but approve does not imply revert.
        ("invitations:view", "invitations:approve"),
    ],
)
async def test_revert_approval_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
    monkeypatch,
    codes: tuple[str, ...],
) -> None:
    caller = await _branch_scoped_user_with(db_session, tenant, branch.id, codes)
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    email_calls, _ = _capture_revert_dispatch(monkeypatch)

    response = await _revert(client, issue_token(caller), invitation.id, "Mistake")
    assert response.status_code == 403

    await db_session.refresh(invitation)
    assert invitation.status == "approved"
    assert email_calls == []


async def test_revert_approval_permission_at_other_branch_forbidden(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-REVERT")
    db_session.add(other_branch)
    await db_session.flush()
    caller = await _branch_scoped_user_with(
        db_session, tenant, other_branch.id, ("invitations:view", "invitations:revert-approval")
    )
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    _capture_revert_dispatch(monkeypatch)

    response = await _revert(client, issue_token(caller), invitation.id, "Mistake")
    assert response.status_code == 403

    await db_session.refresh(invitation)
    assert invitation.status == "approved"


async def test_revert_approval_branch_scoped_holder_succeeds(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    caller = await _branch_scoped_user_with(
        db_session, tenant, branch.id, ("invitations:view", "invitations:revert-approval")
    )
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    _capture_revert_dispatch(monkeypatch)

    response = await _revert(client, issue_token(caller), invitation.id, "Mistake")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["approvalRevertedByUserId"] == str(caller.id)


async def test_revert_approval_unknown_invitation_not_found(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await _revert(client, token, uuid.uuid4(), "Mistake")
    assert response.status_code == 404


async def test_revert_approval_concurrent_requests_transition_exactly_once(
    branch: Branch, tenant: Tenant, user: User, db_session: AsyncSession, monkeypatch
) -> None:
    """Same stale-object simulation as
    `test_approve_invitation_concurrent_requests_transition_exactly_once`:
    both calls see the pre-revert `approved` row, and only the atomic
    `UPDATE` decides."""
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    email_calls, _ = _capture_revert_dispatch(monkeypatch)

    first = await invitations_service.revert_invitation_approval(
        db_session, invitation, user=user, reason="Mistake", tenant=tenant
    )
    assert first.status == "submitted"

    with pytest.raises(HTTPException) as exc_info:
        await invitations_service.revert_invitation_approval(
            db_session, invitation, user=user, reason="Mistake", tenant=tenant
        )
    assert exc_info.value.status_code == 409
    assert len(email_calls) == 1


async def test_revert_approval_if_eligible_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_revert"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).revert_approval_if_eligible(
            invitation.id, user_id=uuid.uuid4(), reason="Mistake"
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.status == "approved"


async def test_reverted_invitation_pass_is_on_hold_until_reapproved(
    client: AsyncClient,
    tenant: Tenant,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
) -> None:
    """The QR issued at the first approval is refused while reverted, and
    re-approval re-sends — and re-validates — the same token."""
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="submitted",
        preferred_visit_date=None,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(invitation)
    await db_session.commit()
    approval_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )
    _capture_revert_dispatch(monkeypatch)
    token = await _login(client, user.email)
    approve_url = f"/api/v1/invitations/{invitation.id}/approve"
    auth = {"Authorization": f"Bearer {token}"}

    assert (await client.post(approve_url, headers=auth)).status_code == 200
    assert (await _revert(client, token, invitation.id, "Mistake")).status_code == 200

    qr = approval_calls[0]["qr_token"]
    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-in")
    # Same rejection any not-yet-approved invitation's scan gets.
    assert response.status_code == 400, response.text
    await db_session.refresh(invitation)
    assert invitation.status == "submitted"
    assert invitation.check_in_status == "unused"

    assert (await client.post(approve_url, headers=auth)).status_code == 200
    assert [c["qr_token"] for c in approval_calls] == [qr, qr]
    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-in")
    assert response.status_code == 200, response.text


async def test_approval_revert_notification_skipped_once_reapproved(
    tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """A redelivered revert email must not reach a visitor whose request
    has since been re-approved (background-jobs.md §2)."""
    invitation = _approved_invitation(db_session, branch.id, approval_reverted_at=datetime.now(UTC))
    db_session.add(invitation)
    await db_session.commit()
    sent: list[Invitation] = []

    async def _fake_dispatch(inv, **kwargs):
        sent.append(inv)

    monkeypatch.setattr(tasks, "_dispatch", _fake_dispatch)
    await tasks._send_approval_revert_notification(tenant.schema_name, str(invitation.id))
    assert sent == []

    await db_session.execute(
        update(Invitation).where(Invitation.id == invitation.id).values(status="submitted")
    )
    await db_session.commit()
    await tasks._send_approval_revert_notification(tenant.schema_name, str(invitation.id))
    assert [inv.id for inv in sent] == [invitation.id]


# --- add-invitation-export: GET /invitations/export --------------------------
# specs/invitation-export/spec.md. Attribute values are read into locals
# before any request: the test client shares `db_session`, and a request can
# expire the ORM objects a test built (gotcha: get_tenant's rollback).

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_ALL_HEADERS = [column.header for column in invitation_export.COLUMNS]


def _names(**overrides: str | None) -> InvitationExportNames:
    fields: dict[str, str | None] = dict.fromkeys(InvitationExportNames._fields)
    fields.update(overrides)
    return InvitationExportNames(**fields)


def _base_header(header: str) -> str:
    """Strips a timestamp header's ` (<timezone>)` suffix."""
    return header.split(" (")[0]


def _csv_rows(content: bytes) -> list[dict[str, str]]:
    """Rows keyed by header with the timezone suffix stripped, so callers
    needn't know which zone the tenant resolves to.
    """
    assert content.startswith(b"\xef\xbb\xbf")
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    return [{_base_header(key): value for key, value in row.items()} for row in reader]


def _csv_headers(content: bytes) -> list[str]:
    return next(csv.reader(io.StringIO(content.decode("utf-8-sig"))))


def _export_visitor(invitation_id: uuid.UUID, name: str) -> InvitationVisitor:
    return InvitationVisitorFactory.build(
        id=uuid.uuid4(),
        invitation_id=invitation_id,
        full_name=name,
        email=f"{name.lower().replace(' ', '.')}@visitor.example",
        phone="5550100",
        id_proof_type="passport",
        id_proof_storage_key=f"vmss:secret-id-proof-{name}",
        photo_storage_key=f"vmss:secret-photo-{name}",
    )


async def _service_export(db_session: AsyncSession, tenant: Any, **overrides: Any):
    kwargs: dict[str, Any] = {
        "branch_scope": "all",
        "relevant_to_user_id": None,
        "default_host_role_id": None,
        "status": None,
        "registration_type": None,
        "source": None,
        "search": None,
        "purpose_of_visit": None,
        "date_range": InvitationExportDateRange(),
        "export_format": ExportFormat.csv,
    }
    kwargs.update(overrides)
    return await invitations_service.export_invitations(db_session, tenant, **kwargs)


def test_export_build_rows_one_per_person_primary_contact_first() -> None:
    individual = InvitationFactory.build(
        id=uuid.uuid4(), registration_type="individual", source="staff_pre_registration"
    )
    individual.visitors = []
    group = InvitationFactory.build(
        id=uuid.uuid4(),
        registration_type="group",
        source="visitor_walk_in",
        primary_contact_full_name="Group Lead",
    )
    group.visitors = [_export_visitor(group.id, f"Guest {i}") for i in range(3)]
    names = _names(branch="Main")

    rows = invitation_export.build_rows([(individual, names), (group, names)], ZoneInfo("UTC"))

    assert len(rows) == 5
    assert rows[0]["visitor_role"] == invitation_export.PRIMARY_CONTACT
    group_rows = rows[1:]
    assert {row["tracking_id"] for row in group_rows} == {group.tracking_id}
    assert [row["visitor_role"] for row in group_rows] == [
        invitation_export.PRIMARY_CONTACT,
        *[invitation_export.CO_VISITOR] * 3,
    ]
    assert group_rows[0]["visitor_name"] == "Group Lead"
    assert "secret" not in repr(rows)


def test_export_labels_cover_every_enum_member_and_fall_back_readably() -> None:
    """Spec "Exported Values Are Human-Readable Labels"."""
    assert set(InvitationStatus) <= invitation_export.STATUS_LABELS.keys()
    assert set(RegistrationSource) <= invitation_export.SOURCE_LABELS.keys()
    assert set(RegistrationType) <= invitation_export.REGISTRATION_TYPE_LABELS.keys()
    assert invitation_export.label("pending", invitation_export.STATUS_LABELS) == "Pending"

    invitation = InvitationFactory.build(
        id=uuid.uuid4(), registration_type="group", source="visitor_walk_in", status="checked_in"
    )
    invitation.visitors = []
    [row] = invitation_export.build_rows([(invitation, _names())], ZoneInfo("UTC"))
    assert (row["status"], row["source"], row["registration_type"]) == (
        "Checked-in",
        "Visitor Walk-in",
        "Group",
    )


@pytest.mark.parametrize(
    ("status", "lifecycle_headers"),
    [
        ("submitted", ["Requested At"]),
        ("approved", ["Requested At", "Approved At"]),
        ("denied", ["Requested At", "Denied At", "Denial Reason"]),
        ("checked_in", ["Requested At", "Approved At", "Checked In At", "Checked In By"]),
        (
            "checked_out",
            [
                "Requested At",
                "Approved At",
                "Checked In At",
                "Checked In By",
                "Checked Out At",
                "Checked Out By",
            ],
        ),
        ("archived", ["Requested At", "Approved At", "Archived At"]),
        (
            None,
            [
                "Requested At",
                "Approved At",
                "Denied At",
                "Denial Reason",
                "Checked In At",
                "Checked In By",
                "Checked Out At",
                "Checked Out By",
                "Archived At",
            ],
        ),
    ],
)
def test_export_columns_follow_the_status_filter(
    status: str | None, lifecycle_headers: list[str]
) -> None:
    """Spec "Date Columns Follow the Status Filter"."""
    headers = [column.header for column in invitation_export.columns_for(status)]
    assert headers == _ALL_HEADERS[: _ALL_HEADERS.index("Requested At")] + lifecycle_headers
    assert len(invitation_export.columns_for(None)) == 32


def test_export_formats_timestamps_in_the_given_timezone() -> None:
    """Spec "Status-specific timestamps populated" and "XLSX dates are real
    date values".
    """
    invitation = InvitationFactory.build(
        id=uuid.uuid4(),
        registration_type="individual",
        source="staff_pre_registration",
        checked_in_at=datetime(2026, 10, 13, 9, 5, 42, tzinfo=UTC),
        approved_at=datetime(2026, 10, 12, 4, 0, tzinfo=UTC),
        preferred_visit_date=date(2026, 10, 13),
        preferred_visit_time=time(10, 0),
        denied_at=None,
    )
    invitation.visitors = []
    rows = invitation_export.build_rows([(invitation, _names())], ZoneInfo(_KOLKATA))
    columns = invitation_export.COLUMNS

    content = invitation_export.render_csv(rows, columns, _KOLKATA)
    [csv_row] = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    assert csv_row[f"Checked In At ({_KOLKATA})"] == "2026-10-13 14:35"
    assert csv_row[f"Approved At ({_KOLKATA})"] == "2026-10-12 09:30"
    assert csv_row["Visit Date"] == "2026-10-13"
    assert csv_row["Visit Time"] == "10:00"
    assert csv_row[f"Denied At ({_KOLKATA})"] == ""

    sheet = openpyxl.load_workbook(
        io.BytesIO(invitation_export.render_xlsx(rows, columns, _KOLKATA))
    ).active
    headers = [cell.value for cell in sheet[1]]
    data = {header: cell for header, cell in zip(headers, sheet[2], strict=True)}
    assert data[f"Checked In At ({_KOLKATA})"].value == datetime(2026, 10, 13, 14, 35, 42)
    assert data[f"Checked In At ({_KOLKATA})"].number_format == "yyyy-mm-dd hh:mm"
    assert data["Visit Date"].is_date
    assert data["Visit Date"].number_format == "yyyy-mm-dd"


@pytest.mark.parametrize("trigger", ["=", "+", "-", "@", "\t", "\r"])
def test_export_neutralizes_formula_triggers_in_csv_and_types_cells_in_xlsx(trigger: str) -> None:
    """Spec "Exported Cells Are Safe Against Formula Injection": CSV gets
    the `'` guard, XLSX keeps the original text in a string-typed cell.
    """
    payload = f'{trigger}HYPERLINK("http://evil","x")'
    invitation = InvitationFactory.build(
        id=uuid.uuid4(),
        registration_type="individual",
        source="staff_pre_registration",
        primary_contact_full_name=payload,
        primary_contact_phone="+919800000261",
    )
    invitation.visitors = []
    rows = invitation_export.build_rows([(invitation, _names())], ZoneInfo("UTC"))
    columns = invitation_export.COLUMNS

    [csv_row] = _csv_rows(invitation_export.render_csv(rows, columns, "UTC"))
    assert csv_row["Visitor Name"] == f"'{payload}"
    assert csv_row["Phone Number"] == "'+919800000261"

    sheet = openpyxl.load_workbook(
        io.BytesIO(invitation_export.render_xlsx(rows, columns, "UTC"))
    ).active
    headers = [cell.value for cell in sheet[1]]
    data = {header: cell for header, cell in zip(headers, sheet[2], strict=True)}
    for cell in sheet[2]:
        assert cell.data_type != "f"
    # XML parsing normalizes a carriage return to a newline on read-back.
    assert data["Visitor Name"].value == payload.replace("\r", "\n")
    assert data["Visitor Name"].data_type == "s"
    assert data["Phone Number"].value == "+919800000261"
    assert data["Phone Number"].data_type == "s"


def test_export_xlsx_header_is_bold_frozen_and_filterable() -> None:
    """Spec "XLSX Export Is Presented for Reading"."""
    columns = invitation_export.columns_for("approved")
    sheet = openpyxl.load_workbook(
        io.BytesIO(invitation_export.render_xlsx([], columns, "UTC"))
    ).active
    assert sheet.freeze_panes == "A2"
    assert sheet.auto_filter.ref == f"A1:{get_column_letter(len(columns))}1"
    assert all(cell.font.b for cell in sheet[1])
    assert sheet.column_dimensions["A"].width == columns[0].width


async def test_export_invitations_csv_by_default(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="approved")
    db_session.add(invitation)
    await db_session.commit()
    tracking_id = invitation.tracking_id

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations/export",
        params={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    disposition = response.headers["content-disposition"]
    assert re.fullmatch(
        r'attachment; filename="invitations-approved-\d{4}-\d{2}-\d{2}\.csv"', disposition
    )
    assert [_base_header(h) for h in _csv_headers(response.content)] == [
        column.header for column in invitation_export.columns_for("approved")
    ]
    rows = _csv_rows(response.content)
    assert [row["Tracking ID"] for row in rows] == [tracking_id]
    assert rows[0]["Status"] == "Approved"
    assert rows[0]["Branch"] == "Main Branch"


async def test_export_invitations_xlsx_on_request(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    tracking_id = invitation.tracking_id

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations/export",
        params={"format": "xlsx"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == _XLSX_MEDIA_TYPE
    assert 'filename="invitations-all-' in response.headers["content-disposition"]
    assert response.headers["content-disposition"].endswith('.xlsx"')
    sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
    values = [[c.value for c in row] for row in sheet.iter_rows()]
    assert [_base_header(h) for h in values[0]] == _ALL_HEADERS
    assert [row[0] for row in values[1:]] == [tracking_id]


async def test_export_denied_status_shows_reason_and_drops_later_columns(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> None:
    """Spec "Denied export shows the reason" and "Approved export omits
    later-stage columns".
    """
    denied = _build_invitation(
        db_session,
        branch.id,
        status="denied",
        denied_at=datetime.now(UTC),
        denial_reason="No host available",
    )
    approved = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add_all([denied, approved])
    await db_session.commit()

    denied_file = await _service_export(db_session, tenant, status="denied")
    headers = [_base_header(h) for h in _csv_headers(denied_file.content)]
    assert "Denial Reason" in headers
    assert "Approved At" not in headers
    assert [row["Denial Reason"] for row in _csv_rows(denied_file.content)] == ["No host available"]

    approved_file = await _service_export(db_session, tenant, status="approved")
    headers = [_base_header(h) for h in _csv_headers(approved_file.content)]
    assert {"Requested At", "Approved At"} <= set(headers)
    assert not {
        "Denied At",
        "Denial Reason",
        "Checked In At",
        "Checked In By",
        "Checked Out At",
        "Checked Out By",
    } & set(headers)


async def test_export_group_rows_repeat_visit_details(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, user: User
) -> None:
    """Spec "Visit-level details repeated on group rows" and "Check-in and
    check-out staff named".
    """
    checker_out = UserFactory.build(
        id=uuid.uuid4(), email="gate-officer@acme-test.example", full_name="Gate Officer"
    )
    category = VisitorCategoryFactory.build(id=uuid.uuid4(), name="Vendor", code="EXPORT-VENDOR")
    db_session.add_all([checker_out, category])
    await db_session.flush()
    group = _build_invitation(
        db_session,
        branch.id,
        registration_type="group",
        status="checked_out",
        visitor_category_id=category.id,
        badge_number="B-0042",
        poc_name="Front Desk",
        carried_items=["Laptop", "Toolbox"],
        carried_items_description="Sealed",
        additional_notes="Arrives by cab",
        checked_in_by_user_id=user.id,
        checked_out_by_user_id=checker_out.id,
    )
    group.visitors = [_export_visitor(group.id, f"Guest {i}") for i in range(2)]
    group.vehicles = [
        InvitationVehicleFactory.build(id=uuid.uuid4(), license_plate=plate)
        for plate in ("KA-01-AB-1234", "KL-07-CD-5678")
    ]
    db_session.add(group)
    await db_session.commit()

    rows = _csv_rows((await _service_export(db_session, tenant)).content)

    assert len(rows) == 3
    for row in rows:
        assert row["Badge Number"] == "B-0042"
        assert set(row["Vehicle Number(s)"].split(", ")) == {"KA-01-AB-1234", "KL-07-CD-5678"}
        assert row["Visitor Category"] == "Vendor"
        assert row["Point of Contact"] == "Front Desk"
        assert row["Carried Items"] == "Laptop, Toolbox — Sealed"
        assert row["Additional Notes"] == "Arrives by cab"
        assert row["Checked In By"] == "Admin User"
        assert row["Checked Out By"] == "Gate Officer"
        assert row["Status"] == "Checked-out"


async def test_export_invitations_no_match_returns_header_only(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations/export",
        params={"status": "denied"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert _csv_rows(response.content) == []


@pytest.mark.parametrize(
    "params",
    [
        {"format": "pdf"},
        {"dateFrom": "2026-10-14", "dateTo": "2026-10-13"},
        {"status": "cancelled"},
    ],
)
async def test_export_invitations_rejects_invalid_params(
    client: AsyncClient, user: User, params: dict[str, str]
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations/export",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422, response.text
    assert "content-disposition" not in response.headers


async def test_export_checked_in_for_one_day_uses_visit_timezone(
    db_session: AsyncSession, branch: Branch
) -> None:
    """Spec "Export checked-in visitors for one day" — the day boundary is
    the visit timezone's midnight, not UTC's.
    """
    same_day = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        checked_in_at=datetime(2026, 10, 12, 19, 0, tzinfo=UTC),  # 00:30 IST on the 13th
    )
    day_before = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        checked_in_at=datetime(2026, 10, 12, 18, 0, tzinfo=UTC),  # 23:30 IST on the 12th
    )
    approved = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        checked_in_at=datetime(2026, 10, 12, 19, 0, tzinfo=UTC),
    )
    db_session.add_all([same_day, day_before, approved])
    await db_session.commit()

    export_file = await _service_export(
        db_session,
        SimpleNamespace(timezone=_KOLKATA),
        status="checked_in",
        date_range=InvitationExportDateRange(
            date_from=date(2026, 10, 13), date_to=date(2026, 10, 13)
        ),
    )

    rows = _csv_rows(export_file.content)
    assert [row["Tracking ID"] for row in rows] == [same_day.tracking_id]
    assert export_file.row_count == 1
    assert export_file.filename.startswith("invitations-checked-in-")


async def test_export_approved_excludes_invitations_that_moved_on(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> None:
    approved = _build_invitation(db_session, branch.id, status="approved")
    checked_in = _build_invitation(
        db_session, branch.id, status="checked_in", checked_in_at=datetime.now(UTC)
    )
    db_session.add_all([approved, checked_in])
    await db_session.commit()

    export_file = await _service_export(db_session, tenant, status="approved")

    assert [r["Tracking ID"] for r in _csv_rows(export_file.content)] == [approved.tracking_id]


async def test_export_date_range_without_status_filters_on_created_at(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> None:
    inside = _build_invitation(
        db_session, branch.id, status="denied", created_at=datetime(2026, 10, 5, 9, tzinfo=UTC)
    )
    outside = _build_invitation(
        db_session, branch.id, status="approved", created_at=datetime(2026, 9, 5, 9, tzinfo=UTC)
    )
    db_session.add_all([inside, outside])
    await db_session.commit()

    export_file = await _service_export(
        db_session,
        tenant,
        date_range=InvitationExportDateRange(
            date_from=date(2026, 10, 1), date_to=date(2026, 10, 31)
        ),
    )

    assert [r["Tracking ID"] for r in _csv_rows(export_file.content)] == [inside.tracking_id]


async def test_export_group_invitation_rows_are_adjacent_without_document_references(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> None:
    """Spec "Group invitation yields a row per person" and "No document or
    photo references leak" — the service never consults `documents:view`,
    so no caller can get storage keys or URLs into the file.
    """
    group = _build_invitation(
        db_session,
        branch.id,
        registration_type="group",
        primary_contact_id_proof_storage_key="vmss:secret-primary-id",
        primary_contact_photo_storage_key="vmss:secret-primary-photo",
    )
    group.visitors = [_export_visitor(group.id, f"Guest {i}") for i in range(3)]
    individual = _build_invitation(db_session, branch.id)
    db_session.add_all([group, individual])
    await db_session.commit()

    export_file = await _service_export(db_session, tenant)

    rows = _csv_rows(export_file.content)
    assert len(rows) == 5
    group_positions = [i for i, row in enumerate(rows) if row["Tracking ID"] == group.tracking_id]
    assert group_positions == list(range(group_positions[0], group_positions[0] + 4))
    assert rows[group_positions[0]]["Visitor Role"] == invitation_export.PRIMARY_CONTACT
    body = export_file.content.decode("utf-8-sig")
    assert "secret" not in body
    assert "http" not in body


async def test_export_list_filters_narrow_the_export_like_the_list(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> None:
    match = _build_invitation(
        db_session,
        branch.id,
        registration_type="individual",
        source="visitor_walk_in",
        purpose_of_visit="Interview",
        primary_contact_full_name="Priya Export",
    )
    wrong_source = _build_invitation(
        db_session,
        branch.id,
        source="staff_pre_registration",
        purpose_of_visit="Interview",
        primary_contact_full_name="Priya Export",
    )
    wrong_purpose = _build_invitation(
        db_session,
        branch.id,
        source="visitor_walk_in",
        purpose_of_visit="Delivery",
        primary_contact_full_name="Priya Export",
    )
    wrong_name = _build_invitation(
        db_session,
        branch.id,
        source="visitor_walk_in",
        purpose_of_visit="Interview",
        primary_contact_full_name="Someone Else",
    )
    db_session.add_all([match, wrong_source, wrong_purpose, wrong_name])
    await db_session.commit()

    export_file = await _service_export(
        db_session,
        tenant,
        registration_type="individual",
        source="visitor_walk_in",
        purpose_of_visit="Interview",
        search="priya",
    )

    assert [r["Tracking ID"] for r in _csv_rows(export_file.content)] == [match.tracking_id]


async def test_export_row_cap_rejects_over_and_allows_exactly_at_the_cap(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group = _build_invitation(db_session, branch.id, registration_type="group")
    db_session.add(group)
    await db_session.flush()
    db_session.add_all([_export_visitor(group.id, f"Guest {i}") for i in range(2)])
    await db_session.commit()
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}

    monkeypatch.setattr(settings, "invitation_export_max_rows", 2)
    over = await client.get("/api/v1/invitations/export", headers=headers)
    assert over.status_code == 422, over.text
    assert "Narrow the filters" in over.json()["message"]
    assert "content-disposition" not in over.headers

    monkeypatch.setattr(settings, "invitation_export_max_rows", 3)
    at_cap = await client.get("/api/v1/invitations/export", headers=headers)
    assert at_cap.status_code == 200, at_cap.text
    assert len(_csv_rows(at_cap.content)) == 3

    actions = (
        (
            await db_session.execute(
                select(AuditLog.diff).where(AuditLog.action == "invitations_exported")
            )
        )
        .scalars()
        .all()
    )
    assert [diff["row_count"] for diff in actions] == [3]


async def test_export_successful_export_is_audited_with_filters(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    db_session.add_all([_build_invitation(db_session, branch.id, status="approved")])
    await db_session.commit()
    user_id = user.id

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations/export",
        params={"status": "approved", "format": "xlsx", "search": "INV"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    [entry] = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "invitations_exported")
            )
        )
        .scalars()
        .all()
    )
    assert entry.actor_user_id == user_id
    assert entry.entity_type == "Invitation"
    assert entry.diff == {
        "filters": {"status": "approved", "search": "INV"},
        "format": "xlsx",
        "row_count": 1,
    }


async def test_export_reception_exports_their_branch_only(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    await seed_default_roles(db_session)
    other_branch = BranchFactory.build(id=uuid.uuid4(), name="Other Branch", code="OTHER")
    db_session.add(other_branch)
    await db_session.flush()
    receptionist = await _reception_holder(db_session, branch.id)
    own = _build_invitation(db_session, branch.id)
    elsewhere = _build_invitation(db_session, other_branch.id)
    db_session.add_all([own, elsewhere])
    await db_session.commit()
    own_tracking_id, other_branch_id = own.tracking_id, other_branch.id
    token = issue_token(receptionist)

    response = await client.get(
        "/api/v1/invitations/export",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200, response.text
    assert [r["Tracking ID"] for r in _csv_rows(response.content)] == [own_tracking_id]

    response = await client.get(
        "/api/v1/invitations/export",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(other_branch_id)},
    )
    assert response.status_code == 403, response.text


async def test_export_requires_invitations_export_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """Spec "Caller without invitations:export is denied" and "Host is
    denied by default" — `relevantToMe` narrows the export scope, it never
    replaces the permission check.
    """
    viewer_role = RoleFactory.build(
        id=uuid.uuid4(),
        name="board-viewer",
        permissions=[await _get_or_create_permission(db_session, "invitations:view-all")],
    )
    db_session.add(viewer_role)
    await db_session.flush()
    viewer = _make_role_holder(db_session, viewer_role, branch.id)
    host = _make_role_holder(db_session, await _host_role(db_session), branch.id)
    db_session.add(_build_invitation(db_session, branch.id))
    await db_session.commit()

    viewer_token, host_token = issue_token(viewer), issue_token(host)

    for token, params in (
        (viewer_token, {}),
        (host_token, {}),
        (host_token, {"relevantToMe": "true"}),
    ):
        response = await client.get(
            "/api/v1/invitations/export",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403, response.text
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "invitations_exported")
        )
        == 0
    )


async def test_export_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, db_session: AsyncSession, branch: Branch
) -> None:
    """testing-standards.md §2: an export through one tenant's session never
    sees another tenant schema's invitations.
    """
    other_schema = "tenant_other_export_test"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        other_branch = BranchFactory.build(id=uuid.uuid4(), name="Elsewhere", code="ELSE")
        other_session.add(other_branch)
        await other_session.flush()
        foreign = _build_invitation(other_session, other_branch.id)
        other_session.add(foreign)
        await other_session.commit()
        foreign_tracking_id = foreign.tracking_id

    own = _build_invitation(db_session, branch.id)
    db_session.add(own)
    await db_session.commit()

    export_file = await _service_export(db_session, SimpleNamespace(timezone="UTC"))

    tracking_ids = [r["Tracking ID"] for r in _csv_rows(export_file.content)]
    assert tracking_ids == [own.tracking_id]
    assert foreign_tracking_id not in tracking_ids


# --- auto-checkout-and-archive-no-shows: visit-lifecycle sweep ---------------


def _expired() -> datetime:
    return datetime.now(UTC) - timedelta(hours=1)


def _later() -> datetime:
    return datetime.now(UTC) + timedelta(hours=1)


async def _sweep(session: AsyncSession) -> tuple[int, int]:
    return await tasks.sweep_visit_lifecycle(session, now=datetime.now(UTC))


async def _sweep_audits(db_session: AsyncSession, invitation_id: uuid.UUID) -> list[AuditLog]:
    stmt = select(AuditLog).where(
        AuditLog.entity_id == invitation_id,
        AuditLog.action.in_(("invitation_auto_checked_out", "invitation_archived")),
    )
    return list((await db_session.execute(stmt)).scalars().all())


def _archived_invitation(db_session: AsyncSession, branch_id: uuid.UUID, **overrides):
    overrides.setdefault("status", "archived")
    overrides.setdefault("archived_at", datetime.now(UTC))
    overrides.setdefault("expires_at", _expired())
    overrides.setdefault("preferred_visit_date", datetime.now(UTC).date() - timedelta(days=1))
    return _approved_invitation(db_session, branch_id, **overrides)


async def test_sweep_auto_checks_out_expired_check_ins(
    branch: Branch, db_session: AsyncSession
) -> None:
    """visit-lifecycle-sweep "Expired Check-Ins Are Checked Out Automatically"
    — including a legacy row where only `status` says `checked_in`, and an
    extended pass that isn't due yet.
    """
    expired = _checked_in_invitation(db_session, branch.id)
    expired.expires_at = _expired()
    extended = _checked_in_invitation(db_session, branch.id)
    extended.expires_at = _later()
    legacy = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        check_in_status="unused",
        approved_at=datetime.now(UTC),
        checked_in_at=datetime.now(UTC),
        expires_at=_expired(),
    )
    db_session.add(legacy)
    await db_session.commit()

    await _sweep(db_session)

    for invitation in (expired, legacy):
        await db_session.refresh(invitation)
        assert invitation.status == "checked_out"
        assert invitation.check_in_status == "checked_out"
        assert invitation.checked_out_at == invitation.expires_at
        assert invitation.checked_out_by_user_id is None
        assert invitation.checked_out_automatically is True
    await db_session.refresh(extended)
    assert extended.status == "checked_in"
    assert extended.checked_out_automatically is False


async def test_sweep_archives_only_expired_approved_no_shows(
    branch: Branch, db_session: AsyncSession
) -> None:
    """visit-lifecycle-sweep "Approved No-Shows Are Archived the Day After the
    Visit" — pending, upcoming, visited and denied rows are left alone.
    """
    no_show = _approved_invitation(db_session, branch.id, expires_at=_expired())
    upcoming = _approved_invitation(db_session, branch.id, expires_at=_later())
    pending = _build_invitation(db_session, branch.id, status="submitted", expires_at=_expired())
    visited = _build_invitation(
        db_session,
        branch.id,
        status="checked_out",
        check_in_status="checked_out",
        expires_at=_expired(),
    )
    denied = _build_invitation(db_session, branch.id, status="denied", expires_at=_expired())
    db_session.add_all([no_show, upcoming, pending, visited, denied])
    await db_session.commit()

    before = datetime.now(UTC)
    await _sweep(db_session)

    await db_session.refresh(no_show)
    assert no_show.status == "archived"
    assert no_show.archived_at is not None and no_show.archived_at >= before
    assert no_show.check_in_status == "unused"
    for invitation, expected in (
        (upcoming, "approved"),
        (pending, "submitted"),
        (visited, "checked_out"),
        (denied, "denied"),
    ):
        await db_session.refresh(invitation)
        assert invitation.status == expected
        assert invitation.archived_at is None


async def test_sweep_audits_once_and_notifies_nobody(
    branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """visit-lifecycle-sweep "The Sweep Is Silent, Audited, and Safe to Repeat"."""
    checked_in = _checked_in_invitation(db_session, branch.id)
    checked_in.expires_at = _expired()
    no_show = _approved_invitation(db_session, branch.id, expires_at=_expired())
    db_session.add(no_show)
    await db_session.commit()
    checked_in_id, no_show_id = checked_in.id, no_show.id

    pushes: list[dict] = []

    async def _fake_notify_user(**kwargs):
        pushes.append(kwargs)

    sends: list[dict] = []

    async def _fake_send(**kwargs):
        sends.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)
    monkeypatch.setattr(notifications.email_sender, "send", _fake_send)
    monkeypatch.setattr(notifications.sms_sender, "send", _fake_send)

    assert await _sweep(db_session) == (1, 1)
    assert await _sweep(db_session) == (0, 0)

    [checkout_audit] = await _sweep_audits(db_session, checked_in_id)
    assert checkout_audit.action == "invitation_auto_checked_out"
    assert checkout_audit.actor_user_id is None
    assert checkout_audit.entity_type == "invitation"
    [archive_audit] = await _sweep_audits(db_session, no_show_id)
    assert archive_audit.action == "invitation_archived"
    assert archive_audit.actor_user_id is None
    assert pushes == []
    assert sends == []


async def test_sweep_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, branch: Branch, db_session: AsyncSession
) -> None:
    no_show = _approved_invitation(db_session, branch.id, expires_at=_expired())
    db_session.add(no_show)
    await db_session.commit()

    other_schema = "tenant_other_test_visit_lifecycle_sweep"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        assert await _sweep(other_session) == (0, 0)

    await db_session.refresh(no_show)
    assert no_show.status == "approved"


async def test_dispatch_visit_lifecycle_sweep_survives_one_tenant_failing(
    monkeypatch, tenant: Tenant, make_tenant_schema
) -> None:
    """background-jobs "One tenant's failure does not block another"."""
    second_schema = "tenant_other_test_sweep_dispatch"
    await make_tenant_schema(second_schema)
    second_tenant = Tenant(
        id=uuid.uuid4(),
        name="Second Co",
        slug=f"second-{uuid.uuid4().hex[:8]}",
        schema_name=second_schema,
    )
    async with AsyncSessionLocal() as global_session:
        global_session.add(second_tenant)
        await global_session.commit()

    enqueued: list[str] = []

    def _fake_delay(*, tenant_id: str, tenant_schema: str) -> None:
        if tenant_id == str(tenant.id):
            raise RuntimeError("broker hiccup")
        enqueued.append(tenant_id)

    monkeypatch.setattr(tasks.sweep_tenant_visit_lifecycle, "delay", _fake_delay)

    await tasks._dispatch_visit_lifecycle_sweep()

    assert str(second_tenant.id) in enqueued
    assert str(tenant.id) not in enqueued


async def test_manual_check_out_after_auto_check_out_cycle_clears_flag(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """An auto-checked-out visit whose pass is extended can be re-entered,
    and a later manual check-out is not reported as automatic.
    """
    invitation = _approved_invitation(
        db_session,
        branch.id,
        status="checked_out",
        check_in_status="checked_out",
        checked_out_at=_expired(),
        checked_out_automatically=True,
        expires_at=_later(),
    )
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    monkeypatch.setattr(notifications_service, "notify_user", _noop_async)

    qr = qr_token.encrypt_invitation_token(invitation_id)
    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-in")
    assert response.status_code == 200, response.text

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/check-out",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["checkedOutAutomatically"] is False

    await db_session.refresh(invitation)
    assert invitation.checked_out_automatically is False


async def test_qr_check_out_after_auto_check_out_is_rejected(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """invitations "Check-out after the sweep already closed the visit is rejected"."""
    invitation = _checked_in_invitation(db_session, branch.id)
    invitation.expires_at = _expired()
    await db_session.commit()
    await _sweep(db_session)
    await db_session.refresh(invitation)
    checked_out_at = invitation.checked_out_at

    qr = qr_token.encrypt_invitation_token(invitation.id)
    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-out")
    assert response.status_code == 409, response.text

    await db_session.refresh(invitation)
    assert invitation.checked_out_at == checked_out_at
    assert invitation.checked_out_automatically is True


async def _noop_async(**kwargs: Any) -> None:
    return None


# --- auto-checkout-and-archive-no-shows: the archived state ------------------


async def test_archived_invitation_check_in_rejected_on_every_path(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """invitations "An Archived Invitation Does Not Admit the Visitor"."""
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()

    qr = qr_token.encrypt_invitation_token(invitation.id)
    for url in (
        f"/api/v2/invitations/qr/{qr}/check-in",
        f"/api/v2/invitations/{invitation.tracking_id}/check-in",
    ):
        response = await client.patch(url)
        assert response.status_code == 409, response.text
        assert "archived" in response.text

    await db_session.refresh(invitation)
    assert invitation.status == "archived"
    assert invitation.check_in_status == "unused"


async def test_archived_invitation_expiry_cannot_be_extended(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id, expires_at = invitation.id, invitation.expires_at

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/extend",
        json={"expiresAt": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409, response.text

    await db_session.refresh(invitation)
    assert invitation.expires_at == expires_at


def _capture_reschedule_dispatch(monkeypatch) -> tuple[list[dict], list[dict]]:
    """Captures `(reschedule_email_calls, host_push_calls)`."""
    email_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_reschedule_notification, "delay", lambda **kw: email_calls.append(kw)
    )
    push_calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        push_calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)
    return email_calls, push_calls


async def _reschedule(
    client: AsyncClient, token: str, invitation_id: uuid.UUID, visit_date: date
) -> Response:
    return await client.patch(
        f"/api/v1/invitations/{invitation_id}/reschedule",
        json={"preferredVisitDate": visit_date.isoformat(), "preferredVisitTime": "10:30:00"},
        headers={"Authorization": f"Bearer {token}"},
    )


async def test_reschedule_archived_invitation_returns_it_to_approval(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """invitations "An Archived Invitation Is Rescheduled Back Into Approval"."""
    archived_at = datetime.now(UTC) - timedelta(hours=2)
    invitation = _archived_invitation(db_session, branch.id, archived_at=archived_at)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id, old_date = invitation.id, invitation.preferred_visit_date
    email_calls, _ = _capture_reschedule_dispatch(monkeypatch)
    new_date = datetime.now(UTC).date() + timedelta(days=3)

    token = await _login(client, user.email)
    response = await _reschedule(client, token, invitation_id, new_date)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "submitted"
    assert data["approvedAt"] is None
    assert data["archivedAt"] is not None

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"
    assert invitation.approved_at is None
    assert invitation.archived_at == archived_at
    assert invitation.preferred_visit_date == new_date
    assert invitation.previous_preferred_visit_date == old_date
    assert invitation.reschedule_count >= 1
    assert invitation.expires_at == datetime.combine(new_date, time(23, 59, 59), tzinfo=UTC)
    assert [c["invitation_id"] for c in email_calls] == [str(invitation_id)]


async def test_reschedule_archived_stays_submitted_when_company_auto_approves(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    db_session.add(
        CompanyFactory.build(
            id=uuid.uuid4(), auto_approve_pre_registered_visitors=True, default_timezone="UTC"
        )
    )
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    _capture_reschedule_dispatch(monkeypatch)

    token = await _login(client, user.email)
    response = await _reschedule(client, token, invitation_id, datetime.now(UTC).date())
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "submitted"


async def test_reschedule_archived_to_past_date_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    email_calls, push_calls = _capture_reschedule_dispatch(monkeypatch)

    token = await _login(client, user.email)
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    response = await _reschedule(client, token, invitation_id, yesterday)
    assert response.status_code == 422, response.text

    await db_session.refresh(invitation)
    assert invitation.status == "archived"
    assert email_calls == [] and push_calls == []


async def test_reschedule_archived_requires_permission(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    _capture_reschedule_dispatch(monkeypatch)
    viewer = await _branch_scoped_user_with(
        db_session, tenant, branch.id, ("invitations:view", "invitations:view-all")
    )

    token = issue_token(viewer)
    response = await _reschedule(client, token, invitation_id, datetime.now(UTC).date())
    assert response.status_code == 403, response.text

    await db_session.refresh(invitation)
    assert invitation.status == "archived"


async def test_rescheduled_archived_invitation_reapproval_restores_original_pass(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """Approved → never came → archived by the sweep → rescheduled → approved
    again: the approval email carries the original QR token, which now admits.
    """
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="submitted",
        preferred_visit_date=None,
        expires_at=_expired(),
    )
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    approval_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )
    _capture_reschedule_dispatch(monkeypatch)
    token = await _login(client, user.email)
    approve_url = f"/api/v1/invitations/{invitation_id}/approve"
    auth = {"Authorization": f"Bearer {token}"}

    assert (await client.post(approve_url, headers=auth)).status_code == 200
    await _sweep(db_session)
    await db_session.refresh(invitation)
    assert invitation.status == "archived"

    response = await _reschedule(client, token, invitation_id, datetime.now(UTC).date())
    assert response.status_code == 200, response.text
    qr = approval_calls[0]["qr_token"]
    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-in")
    assert response.status_code == 400, response.text  # submitted again: not admitted

    assert (await client.post(approve_url, headers=auth)).status_code == 200
    assert [c["qr_token"] for c in approval_calls] == [qr, qr]
    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-in")
    assert response.status_code == 200, response.text


async def _edit(
    client: AsyncClient, token: str, invitation_id: uuid.UUID, payload: dict
) -> Response:
    return await client.patch(
        f"/api/v1/invitations/{invitation_id}/edit",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )


async def test_edit_archived_invitation_without_date_change_stays_archived(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: None)
    monkeypatch.setattr(notifications_service, "notify_user", _noop_async)

    token = await _login(client, user.email)
    response = await _edit(client, token, invitation_id, {"additionalNotes": "Call ahead"})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "archived"

    await db_session.refresh(invitation)
    assert invitation.status == "archived"
    assert invitation.additional_notes == "Call ahead"


async def test_edit_archived_invitation_date_change_returns_it_to_approval(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: None)
    monkeypatch.setattr(notifications_service, "notify_user", _noop_async)
    new_date = datetime.now(UTC).date() + timedelta(days=1)

    token = await _login(client, user.email)
    response = await _edit(
        client, token, invitation_id, {"preferredVisitDate": new_date.isoformat()}
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "submitted"

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"
    assert invitation.approved_at is None
    assert invitation.preferred_visit_date == new_date
    assert invitation.expires_at == datetime.combine(new_date, time(23, 59, 59), tzinfo=UTC)


async def test_edit_archived_invitation_to_past_date_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    invitation = _archived_invitation(
        db_session, branch.id, preferred_visit_date=datetime.now(UTC).date() - timedelta(days=5)
    )
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    edit_calls: list[dict] = []
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: edit_calls.append(kw))

    token = await _login(client, user.email)
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    response = await _edit(
        client,
        token,
        invitation_id,
        {"preferredVisitDate": yesterday.isoformat(), "additionalNotes": "Too late"},
    )
    assert response.status_code == 422, response.text

    await db_session.refresh(invitation)
    assert invitation.status == "archived"
    assert invitation.additional_notes != "Too late"
    assert edit_calls == []


async def test_edit_archived_invitation_requires_permission(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    viewer = await _branch_scoped_user_with(
        db_session, tenant, branch.id, ("invitations:view", "invitations:view-all")
    )

    token = issue_token(viewer)
    response = await _edit(client, token, invitation_id, {"additionalNotes": "Nope"})
    assert response.status_code == 403, response.text


async def test_list_invitations_filters_archived(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """invitations "Invitation List Filters and Surfaces Archived and Auto
    Check-Out State".
    """
    archived = _archived_invitation(db_session, branch.id)
    approved = _approved_invitation(db_session, branch.id)
    db_session.add_all([archived, approved])
    await db_session.commit()
    archived_tracking_id = archived.tracking_id

    token = await _login(client, user.email)
    auth = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/v1/invitations?status=archived", headers=auth)
    assert response.status_code == 200, response.text
    rows = response.json()["data"]
    assert [row["trackingId"] for row in rows] == [archived_tracking_id]
    assert rows[0]["archivedAt"] is not None
    assert rows[0]["checkedOutAutomatically"] is False

    response = await client.get("/api/v1/invitations?status=expired", headers=auth)
    assert response.status_code == 422, response.text


def test_export_names_the_sweep_as_check_out_actor() -> None:
    """invitation-export "Automatic check-out is labelled"."""
    invitation = InvitationFactory.build(
        id=uuid.uuid4(),
        registration_type="individual",
        source="staff_pre_registration",
        status="checked_out",
        checked_out_automatically=True,
    )
    invitation.visitors = []
    [row] = invitation_export.build_rows(
        [(invitation, _names(checked_out_by="Someone"))], ZoneInfo("UTC")
    )
    assert row["checked_out_by"] == invitation_export.AUTO_CHECK_OUT
    assert row["status"] == "Checked-out"

    invitation.status = "archived"
    [row] = invitation_export.build_rows([(invitation, _names())], ZoneInfo("UTC"))
    assert row["status"] == "Archived"


async def test_export_archived_date_range_applies_to_archived_at(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> None:
    """invitation-export "Archived export uses the archive date"."""
    today = datetime.now(UTC).date()
    recent = _archived_invitation(db_session, branch.id, archived_at=datetime.now(UTC))
    old = _archived_invitation(
        db_session, branch.id, archived_at=datetime.now(UTC) - timedelta(days=10)
    )
    db_session.add_all([recent, old])
    await db_session.commit()

    exported = await _service_export(
        db_session,
        tenant,
        status="archived",
        date_range=InvitationExportDateRange(date_from=today, date_to=today),
    )
    headers = [_base_header(h) for h in _csv_headers(exported.content)]
    assert headers[headers.index("Requested At") :] == [
        "Requested At",
        "Approved At",
        "Archived At",
    ]
    assert [row["Tracking ID"] for row in _csv_rows(exported.content)] == [recent.tracking_id]


# --- staff-lifecycle-emails-and-dashboard-landing ----------------------------
# invitations spec "Denial, Approval Revert, and Reschedule Email the
# Responsible Staff" / "... Push the Point of Contact" / "Invitation Expiry
# Extension Notifies the Host via Push". `staff_lifecycle_email_calls` is the
# root conftest's autouse capture of the staff email task's `.delay`. Ids are
# read into locals before any request (gotcha: get_tenant's rollback).


def _capture_pushes(monkeypatch) -> tuple[list[dict], list[dict]]:
    """Captures `(user_push_calls, role_push_calls)`."""
    user_calls: list[dict] = []
    role_calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        user_calls.append(kwargs)

    async def _fake_notify_role_at_branch(tenant_db, **kwargs):
        role_calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)
    monkeypatch.setattr(notifications_service, "notify_role_at_branch", _fake_notify_role_at_branch)
    return user_calls, role_calls


def _silence_visitor_dispatch(monkeypatch) -> None:
    for task in (
        tasks.send_denial_notification,
        tasks.send_approval_revert_notification,
        tasks.send_reschedule_notification,
    ):
        monkeypatch.setattr(task, "delay", lambda **kw: None)


async def _staff_pair(db_session: AsyncSession) -> tuple[User, User]:
    host = _make_host(db_session)
    poc = UserFactory.build(
        id=uuid.uuid4(), email=f"poc-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="POC"
    )
    db_session.add_all([host, poc])
    await db_session.flush()
    return host, poc


async def test_revert_emails_host_and_poc_and_pushes_poc(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    staff_lifecycle_email_calls: list[dict],
) -> None:
    host, poc = await _staff_pair(db_session)
    invitation = _approved_invitation(db_session, branch.id, host_id=host.id, poc_user_id=poc.id)
    db_session.add(invitation)
    await db_session.commit()
    host_id, poc_id, invitation_id, user_id = host.id, poc.id, invitation.id, user.id
    _silence_visitor_dispatch(monkeypatch)
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await _revert(client, token, invitation_id, "Host on leave that day")
    assert response.status_code == 200, response.text

    assert sorted(c["recipient_user_id"] for c in staff_lifecycle_email_calls) == sorted(
        [str(host_id), str(poc_id)]
    )
    for call in staff_lifecycle_email_calls:
        assert call["event"] == "approval_reverted"
        assert call["actor_user_id"] == str(user_id)
        assert call["invitation_id"] == str(invitation_id)
    assert sorted(str(c["user_id"]) for c in user_pushes) == sorted([str(host_id), str(poc_id)])
    assert all(c["data"]["action"] == "approval_reverted" for c in user_pushes)
    assert role_pushes == []


async def test_reschedule_by_host_does_not_email_the_actor(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    staff_lifecycle_email_calls: list[dict],
) -> None:
    _, poc = await _staff_pair(db_session)
    invitation = _build_invitation(
        db_session, branch.id, status="submitted", host_id=user.id, poc_user_id=poc.id
    )
    db_session.add(invitation)
    await db_session.commit()
    poc_id, invitation_id, user_id = poc.id, invitation.id, user.id
    _silence_visitor_dispatch(monkeypatch)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await _reschedule(
        client, token, invitation_id, datetime.now(UTC).date() + timedelta(days=5)
    )
    assert response.status_code == 200, response.text

    assert [c["recipient_user_id"] for c in staff_lifecycle_email_calls] == [str(poc_id)]
    assert staff_lifecycle_email_calls[0]["event"] == "rescheduled"
    # Host push is unchanged (still sent to the acting host); POC pushed once.
    assert sorted(str(c["user_id"]) for c in user_pushes) == sorted([str(user_id), str(poc_id)])


async def test_deny_host_who_is_also_poc_gets_one_email_and_one_push(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    staff_lifecycle_email_calls: list[dict],
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _build_invitation(
        db_session, branch.id, status="submitted", host_id=host.id, poc_user_id=host.id
    )
    db_session.add(invitation)
    await db_session.commit()
    host_id, invitation_id = host.id, invitation.id
    _silence_visitor_dispatch(monkeypatch)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/deny",
        json={"reason": "Visitor not on the expected list"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert [c["recipient_user_id"] for c in staff_lifecycle_email_calls] == [str(host_id)]
    assert staff_lifecycle_email_calls[0]["event"] == "denied"
    assert [c["user_id"] for c in user_pushes] == [host_id]


async def test_deny_with_role_poc_pushes_role_and_sends_no_email(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    staff_lifecycle_email_calls: list[dict],
) -> None:
    role = RoleFactory.build(id=uuid.uuid4(), name=f"security-{uuid.uuid4().hex[:6]}")
    db_session.add(role)
    await db_session.flush()
    invitation = _build_invitation(db_session, branch.id, status="submitted", poc_role_id=role.id)
    db_session.add(invitation)
    await db_session.commit()
    role_id, branch_id, invitation_id, user_id = role.id, branch.id, invitation.id, user.id
    _silence_visitor_dispatch(monkeypatch)
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/deny",
        json={"reason": "Not expected"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert staff_lifecycle_email_calls == []
    assert user_pushes == []
    assert len(role_pushes) == 1
    assert role_pushes[0]["role_id"] == role_id
    assert role_pushes[0]["branch_id"] == branch_id
    assert role_pushes[0]["reason"] == "lifecycle_update"
    assert role_pushes[0]["exclude_user_ids"] == {user_id}
    assert role_pushes[0]["data"]["action"] == "denied"


async def test_rejected_revert_sends_no_staff_notification(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    staff_lifecycle_email_calls: list[dict],
) -> None:
    host, poc = await _staff_pair(db_session)
    invitation = _approved_invitation(
        db_session,
        branch.id,
        host_id=host.id,
        poc_user_id=poc.id,
        status="checked_in",
        check_in_status="checked_in",
    )
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    _silence_visitor_dispatch(monkeypatch)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await _revert(client, token, invitation_id, "Mistake")
    assert response.status_code == 409, response.text
    assert staff_lifecycle_email_calls == []
    assert user_pushes == []


async def test_reschedule_archived_emails_the_responsible_staff(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    staff_lifecycle_email_calls: list[dict],
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _archived_invitation(db_session, branch.id, host_id=host.id)
    db_session.add(invitation)
    await db_session.commit()
    host_id, invitation_id = host.id, invitation.id
    _silence_visitor_dispatch(monkeypatch)
    _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await _reschedule(
        client, token, invitation_id, datetime.now(UTC).date() + timedelta(days=3)
    )
    assert response.status_code == 200, response.text
    assert [(c["recipient_user_id"], c["event"]) for c in staff_lifecycle_email_calls] == [
        (str(host_id), "rescheduled")
    ]


# --- staff lifecycle email task (real test DB) -------------------------------


def _record_staff_emails(monkeypatch) -> list[dict]:
    sent: list[dict] = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    return sent


async def test_staff_lifecycle_email_names_actor_and_reason_without_qr(
    tenant: Tenant, branch: Branch, db_session: AsyncSession, user: User, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _approved_invitation(
        db_session,
        branch.id,
        host_id=host.id,
        status="submitted",
        approval_reverted_at=datetime.now(UTC),
        approval_revert_reason="Host on leave that day",
        primary_contact_full_name="Meera Krishnan",
    )
    db_session.add(invitation)
    await db_session.commit()
    sent = _record_staff_emails(monkeypatch)

    await tasks._send_staff_lifecycle_notification(
        tenant.schema_name, str(invitation.id), str(host.id), str(user.id), "approval_reverted"
    )

    assert len(sent) == 1
    email = sent[0]
    assert email["to"] == host.email
    assert email["subject"] == "Approval withdrawn for Meera Krishnan's visit"
    assert "Host on leave that day" in email["body"]
    assert user.full_name in email["body"]
    assert "Reason given" in email["html_body"]
    assert "qr" not in email["html_body"].lower()
    assert "inline_images" not in email


@pytest.mark.parametrize(
    ("event", "stale_overrides"),
    [
        ("denied", {"status": "submitted"}),
        ("approval_reverted", {"status": "approved", "approval_reverted_at": None}),
        ("rescheduled", {"status": "checked_out", "check_in_status": "checked_out"}),
    ],
)
async def test_staff_lifecycle_email_skipped_when_event_no_longer_current(
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    user: User,
    monkeypatch,
    event: str,
    stale_overrides: dict,
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _approved_invitation(db_session, branch.id, host_id=host.id, **stale_overrides)
    db_session.add(invitation)
    await db_session.commit()
    sent = _record_staff_emails(monkeypatch)

    await tasks._send_staff_lifecycle_notification(
        tenant.schema_name, str(invitation.id), str(host.id), str(user.id), event
    )
    assert sent == []


async def test_staff_lifecycle_email_skips_inactive_recipient(
    tenant: Tenant, branch: Branch, db_session: AsyncSession, user: User, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    host.is_active = False
    invitation = _build_invitation(
        db_session, branch.id, status="denied", host_id=host.id, denial_reason="No"
    )
    db_session.add(invitation)
    await db_session.commit()
    sent = _record_staff_emails(monkeypatch)

    with capture_logs() as logs:
        await tasks._send_staff_lifecycle_notification(
            tenant.schema_name, str(invitation.id), str(host.id), str(user.id), "denied"
        )
    assert sent == []
    assert any(log["event"] == "staff_lifecycle_notification_recipient_not_found" for log in logs)


async def test_staff_lifecycle_email_falls_back_when_actor_deleted(
    tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _build_invitation(
        db_session, branch.id, status="denied", host_id=host.id, denial_reason="No"
    )
    db_session.add(invitation)
    await db_session.commit()
    sent = _record_staff_emails(monkeypatch)

    await tasks._send_staff_lifecycle_notification(
        tenant.schema_name, str(invitation.id), str(host.id), str(uuid.uuid4()), "denied"
    )
    assert len(sent) == 1
    assert "A staff member denied" in sent[0]["body"]


# --- extend pushes the host ----------------------------------------------------


async def test_extend_invitation_pushes_host_with_new_expiry(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    now = datetime.now(UTC)
    invitation = _approved_invitation(
        db_session, branch.id, host_id=host.id, expires_at=now + timedelta(days=1)
    )
    db_session.add(invitation)
    await db_session.commit()
    host_id, invitation_id = host.id, invitation.id
    new_expiry = now + timedelta(days=7)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/extend",
        json={"expiresAt": new_expiry.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert len(user_pushes) == 1
    assert user_pushes[0]["user_id"] == host_id
    assert user_pushes[0]["title"] == "Visit pass extended"
    assert user_pushes[0]["data"]["action"] == "extended"
    assert datetime.fromisoformat(user_pushes[0]["data"]["expiresAt"]) == new_expiry
    assert "valid until" in user_pushes[0]["body"]


async def test_extend_invitation_rejected_sends_no_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    now = datetime.now(UTC)
    invitation = _approved_invitation(
        db_session, branch.id, host_id=host.id, expires_at=now + timedelta(days=2)
    )
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/extend",
        json={"expiresAt": (now + timedelta(days=1)).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422, response.text
    assert user_pushes == []


async def test_extend_invitation_without_host_sends_no_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    now = datetime.now(UTC)
    invitation = _approved_invitation(db_session, branch.id, expires_at=now + timedelta(days=1))
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/extend",
        json={"expiresAt": (now + timedelta(days=3)).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert user_pushes == []


# --- complete-staff-push-coverage --------------------------------------------
# invitations spec "Approval, Check-In, Check-Out, Extension, and Edit Push
# the Point of Contact". Reuses `_capture_pushes`/`_staff_pair` above; ids are
# read into locals before any request (gotcha: get_tenant's rollback).


def _pushed_user_ids(user_pushes: list[dict]) -> list[str]:
    return sorted(str(c["user_id"]) for c in user_pushes)


async def test_tracking_id_check_in_pushes_poc_and_host(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, poc = await _staff_pair(db_session)
    invitation = _approved_invitation(db_session, branch.id, host_id=host.id, poc_user_id=poc.id)
    db_session.add(invitation)
    await db_session.commit()
    host_id, poc_id, tracking_id = host.id, poc.id, invitation.tracking_id
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    response = await client.patch(f"/api/v2/invitations/{tracking_id}/check-in")
    assert response.status_code == 200, response.text

    assert _pushed_user_ids(user_pushes) == sorted([str(host_id), str(poc_id)])
    assert all(c["data"]["action"] == "checked_in" for c in user_pushes)
    assert role_pushes == []


async def test_qr_check_out_pushes_role_poc_excluding_host(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    role = RoleFactory.build(id=uuid.uuid4(), name=f"security-{uuid.uuid4().hex[:6]}")
    db_session.add(role)
    await db_session.flush()
    invitation = _approved_invitation(
        db_session,
        branch.id,
        status="checked_in",
        check_in_status="checked_in",
        checked_in_at=datetime.now(UTC),
        host_id=host.id,
        poc_role_id=role.id,
    )
    db_session.add(invitation)
    await db_session.commit()
    host_id, role_id, branch_id = host.id, role.id, branch.id
    qr = qr_token.encrypt_invitation_token(invitation.id)
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-out")
    assert response.status_code == 200, response.text

    assert [c["user_id"] for c in user_pushes] == [host_id]
    assert len(role_pushes) == 1
    assert role_pushes[0]["role_id"] == role_id
    assert role_pushes[0]["branch_id"] == branch_id
    assert role_pushes[0]["reason"] == "lifecycle_update"
    assert role_pushes[0]["exclude_user_ids"] == {host_id}
    assert role_pushes[0]["data"]["action"] == "checked_out"


async def test_approve_pushes_poc(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, poc = await _staff_pair(db_session)
    invitation = _build_invitation(
        db_session, branch.id, status="submitted", host_id=host.id, poc_user_id=poc.id
    )
    db_session.add(invitation)
    await db_session.commit()
    host_id, poc_id, invitation_id = host.id, poc.id, invitation.id
    monkeypatch.setattr(tasks.send_approval_notification, "delay", lambda **kw: None)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert _pushed_user_ids(user_pushes) == sorted([str(host_id), str(poc_id)])
    assert all(c["data"]["action"] == "approved" for c in user_pushes)


async def test_extend_pushes_poc_with_new_expiry(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, poc = await _staff_pair(db_session)
    now = datetime.now(UTC)
    invitation = _approved_invitation(
        db_session,
        branch.id,
        host_id=host.id,
        poc_user_id=poc.id,
        expires_at=now + timedelta(days=1),
    )
    db_session.add(invitation)
    await db_session.commit()
    poc_id, invitation_id = poc.id, invitation.id
    new_expiry = now + timedelta(days=7)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/extend",
        json={"expiresAt": new_expiry.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    poc_pushes = [c for c in user_pushes if c["user_id"] == poc_id]
    assert len(poc_pushes) == 1
    assert poc_pushes[0]["data"]["action"] == "extended"
    assert datetime.fromisoformat(poc_pushes[0]["data"]["expiresAt"]) == new_expiry


async def test_rejected_extend_sends_no_poc_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    _, poc = await _staff_pair(db_session)
    now = datetime.now(UTC)
    invitation = _approved_invitation(
        db_session, branch.id, poc_user_id=poc.id, expires_at=now + timedelta(days=2)
    )
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/extend",
        json={"expiresAt": (now + timedelta(days=1)).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422, response.text
    assert user_pushes == []
    assert role_pushes == []


def _silence_edit_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: None)
    monkeypatch.setattr(tasks.send_poc_creation_notification, "delay", lambda **kw: None)


async def test_edit_without_poc_change_pushes_existing_poc(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    _, poc = await _staff_pair(db_session)
    invitation = _approved_invitation(
        db_session, branch.id, poc_user_id=poc.id, visitor_category_id=None
    )
    db_session.add(invitation)
    await db_session.commit()
    poc_id, invitation_id = poc.id, invitation.id
    _silence_edit_dispatch(monkeypatch)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await _edit(client, token, invitation_id, {"additionalNotes": "Call ahead"})
    assert response.status_code == 200, response.text

    assert [c["user_id"] for c in user_pushes] == [poc_id]
    assert user_pushes[0]["data"]["action"] == "edited"


async def test_edit_changing_poc_pushes_only_poc_assigned_to_new_poc(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, old_poc = await _staff_pair(db_session)
    new_poc = UserFactory.build(
        id=uuid.uuid4(), email=f"poc-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Q"
    )
    db_session.add(new_poc)
    invitation = _approved_invitation(
        db_session, branch.id, poc_user_id=old_poc.id, visitor_category_id=None
    )
    db_session.add(invitation)
    await db_session.commit()
    new_poc_id, invitation_id = new_poc.id, invitation.id
    _silence_edit_dispatch(monkeypatch)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await _edit(client, token, invitation_id, {"pocUserId": str(new_poc_id)})
    assert response.status_code == 200, response.text

    assert [c["user_id"] for c in user_pushes] == [new_poc_id]
    assert user_pushes[0]["data"]["action"] == "poc_assigned"


async def test_poc_who_checks_the_visitor_out_is_not_pushed(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _approved_invitation(
        db_session,
        branch.id,
        status="checked_in",
        check_in_status="checked_in",
        checked_in_at=datetime.now(UTC),
        host_id=host.id,
        poc_user_id=user.id,
    )
    db_session.add(invitation)
    await db_session.commit()
    host_id, invitation_id = host.id, invitation.id
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/check-out",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert [c["user_id"] for c in user_pushes] == [host_id]


async def test_host_who_is_also_poc_is_pushed_once_on_check_in(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _approved_invitation(db_session, branch.id, host_id=host.id, poc_user_id=host.id)
    db_session.add(invitation)
    await db_session.commit()
    host_id, tracking_id = host.id, invitation.tracking_id
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    response = await client.patch(f"/api/v2/invitations/{tracking_id}/check-in")
    assert response.status_code == 200, response.text

    assert [c["user_id"] for c in user_pushes] == [host_id]
    assert role_pushes == []


async def test_approve_without_poc_pushes_only_the_host(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _build_invitation(
        db_session, branch.id, status="submitted", host_id=host.id, poc_user_id=None
    )
    db_session.add(invitation)
    await db_session.commit()
    host_id, invitation_id = host.id, invitation.id
    monkeypatch.setattr(tasks.send_approval_notification, "delay", lambda **kw: None)
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert [c["user_id"] for c in user_pushes] == [host_id]
    assert role_pushes == []


async def test_rejected_qr_check_in_sends_no_poc_push(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    _, poc = await _staff_pair(db_session)
    invitation = _approved_invitation(
        db_session,
        branch.id,
        poc_user_id=poc.id,
        expires_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    db_session.add(invitation)
    await db_session.commit()
    qr = qr_token.encrypt_invitation_token(invitation.id)
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-in")
    assert response.status_code == 410, response.text
    assert user_pushes == []
    assert role_pushes == []


# --- reception-phone-prefill-lookup ------------------------------------------


async def _lookup_by_phone(client: AsyncClient, token: str, phone: str, **headers: str) -> Response:
    return await client.get(
        "/api/v1/invitations/lookup-by-phone",
        params={"phone": phone},
        headers={"Authorization": f"Bearer {token}", **headers},
    )


async def test_lookup_by_phone_returns_most_recent_invitations_prefill_data(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    older = _build_invitation(
        db_session,
        branch.id,
        primary_contact_phone="9544232271",
        primary_contact_email="old@example.com",
        primary_contact_full_name="J Doe",
        tracking_id="INV-PHONE-OLD1",
    )
    newer = _build_invitation(
        db_session,
        branch.id,
        primary_contact_phone="9544232271",
        primary_contact_email="jane@example.com",
        primary_contact_full_name="Jane Doe",
        primary_contact_id_proof_type="passport",
        tracking_id="INV-PHONE-NEW1",
    )
    db_session.add_all([older, newer])
    await db_session.commit()
    now = datetime.now(UTC)
    newer.created_at = now
    older.created_at = now - timedelta(days=1)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    response = await _lookup_by_phone(client, issue_token(creator), "9544232271")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["fullName"] == "Jane Doe"
    assert data["email"] == "jane@example.com"
    assert data["idProofType"] == "passport"


async def test_lookup_by_phone_ignores_formatting_differences(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    db_session.add(
        _build_invitation(db_session, branch.id, primary_contact_phone="+91 95442-32271")
    )
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    response = await _lookup_by_phone(client, issue_token(creator), "919544232271")
    assert response.status_code == 200
    assert response.json()["data"] is not None


async def test_lookup_by_phone_without_email_returns_null_email(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    db_session.add(
        _build_invitation(
            db_session, branch.id, primary_contact_phone="9876543210", primary_contact_email=None
        )
    )
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    response = await _lookup_by_phone(client, issue_token(creator), "9876543210")
    assert response.status_code == 200
    assert response.json()["data"]["email"] is None


async def test_lookup_by_phone_no_match_returns_null_data(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    response = await _lookup_by_phone(client, issue_token(creator), "5550001111")
    assert response.status_code == 200
    assert response.json()["data"] is None


async def test_lookup_by_phone_too_few_digits_is_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    response = await _lookup_by_phone(client, issue_token(creator), "12-3")
    assert response.status_code == 422


async def test_lookup_by_phone_match_at_unauthorized_branch_returns_null(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-PHONE-1")
    db_session.add(other_branch)
    await db_session.flush()
    db_session.add(
        _build_invitation(db_session, other_branch.id, primary_contact_phone="4445556667")
    )
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    response = await _lookup_by_phone(client, issue_token(creator), "4445556667")
    assert response.status_code == 200
    assert response.json()["data"] is None


async def test_lookup_by_phone_branch_header_excludes_matching_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-PHONE-2")
    db_session.add(other_branch)
    await db_session.flush()
    db_session.add(
        _build_invitation(db_session, other_branch.id, primary_contact_phone="3334445556")
    )
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    branch_role = UserBranchRole(
        id=uuid.uuid4(), role=creator.branch_roles[0].role, branch_id=other_branch.id
    )
    creator.branch_roles.append(branch_role)
    db_session.add(branch_role)
    await db_session.commit()

    response = await _lookup_by_phone(
        client, issue_token(creator), "3334445556", **{"X-Branch-ID": str(branch.id)}
    )
    assert response.status_code == 200
    assert response.json()["data"] is None


async def test_lookup_by_phone_requires_invitations_create_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    response = await _lookup_by_phone(client, issue_token(viewer), "9544232271")
    assert response.status_code == 403


async def test_lookup_by_phone_id_proof_url_gated_on_documents_view(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    db_session.add(
        _build_invitation(
            db_session,
            branch.id,
            primary_contact_phone="7778889990",
            primary_contact_id_proof_storage_key="docs/id.jpg",
            primary_contact_photo_storage_key="docs/photo.jpg",
        )
    )
    await db_session.commit()

    plain = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    data = (await _lookup_by_phone(client, issue_token(plain), "7778889990")).json()["data"]
    assert data["photoUrl"] is not None
    assert data["idProofUrl"] is None

    with_docs = await _branch_scoped_invitation_creator_with_documents(
        db_session, tenant, branch.id
    )
    data = (await _lookup_by_phone(client, issue_token(with_docs), "7778889990")).json()["data"]
    assert data["idProofUrl"] is not None
