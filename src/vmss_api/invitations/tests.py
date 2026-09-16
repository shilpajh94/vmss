import asyncio
import io
import json
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time, timedelta

import aiosmtplib
import pytest
import pytest_asyncio
import starlette.datastructures as starlette_datastructures
from fastapi import HTTPException
from httpx import AsyncClient, Response
from PIL import Image
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from factories import (
    ApprovalWorkflowRuleFactory,
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
from vmss_api.auth.repository import RoleRepository
from vmss_api.core import storage
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.core.schemas import SortOrder
from vmss_api.core.security import hash_password
from vmss_api.invitations import notifications, qr_token, tasks
from vmss_api.invitations import service as invitations_service
from vmss_api.invitations.models import Invitation, InvitationQRCode
from vmss_api.invitations.repository import InvitationRepository
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
        # Keys are raw (never camelCased) — whatever the calling branch's
        # published Consent Agreement step declares; these three are the
        # default for a branch that has never customized it.
        "consents": {
            "terms_accepted": True,
            "data_processing_accepted": True,
            "safety_guidelines_accepted": True,
        },
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
        "consents": {
            "terms_accepted": True,
            "data_processing_accepted": True,
            "safety_guidelines_accepted": True,
        },
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
    assert invitation.consents.get("terms_accepted") is True


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
    payload["consents"]["safety_guidelines_accepted"] = False
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


async def test_create_group_invitation_exceeding_max_visitors_rejected(
    client: AsyncClient, user: User, branch: Branch, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "invitation_max_group_visitors", 1)
    token = await _login(client, user.email)
    response = await _create_invitation(
        client, token, branch, payload=_group_payload(), visitor_file_count=2
    )
    assert response.status_code == 422


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


@pytest.mark.parametrize(
    "missing_field", ["registrationType", "primaryContact", "visitDetails", "consents"]
)
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
    Recorded" — a `consents` key outside the calling branch's configured
    Consent Agreement set is rejected, mirroring the carried-items allow-list
    check above.
    """
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["consents"]["not_a_real_consent"] = True
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
    snapshots two steps at submission, behind the unconditional `stepOrder`
    0 ownership step (role-based-invitation-workflow); the tracking lookup
    surfaces that ownership step as current, since it's always the first to
    become pending.
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
    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitorCategoryId"] = str(category.id)
    data = await _create_invitation_success(client, token, branch, payload=payload)
    steps = await InvitationApprovalStepRepository(db_session).list_for_invitation(
        uuid.UUID(data["id"])
    )
    step_zero = next(s for s in steps if s.step_order == 0)
    assert data["currentApprovalStep"] == {
        "id": str(step_zero.id),
        "stepOrder": 0,
        "approverRoleId": str(reception_role.id),
        "approverUserId": None,
        "totalSteps": 3,
        "delegatedToUserId": None,
    }

    response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": data["trackingId"]}
    )
    assert response.status_code == 200
    assert response.json()["data"]["currentApprovalStep"] == {
        "id": str(step_zero.id),
        "stepOrder": 0,
        "approverRoleId": str(reception_role.id),
        "approverUserId": None,
        "totalSteps": 3,
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
    """A caller whose only role grant is `invitations:view` at `branch_id` —
    the branch-scoping counterpart of `org_structure/tests.py`'s
    `_branch_scoped_user`, applied to this feature's own permission.
    """
    permission = PermissionFactory.build(
        id=uuid.uuid4(), code="invitations:view", description="invitations:view"
    )
    role = RoleFactory.build(id=uuid.uuid4(), name="invitations-viewer", permissions=[permission])
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"viewer-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Invitation Viewer",
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
        for code in ("invitations:view", "documents:view")
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
        "primaryContactPhotoUrl",
        "purposeOfVisit",
        "expiresAt",
        "submittedAt",
        "approvedAt",
    }
    assert row["visitorCategoryId"] is None
    assert row["primaryContactPhotoUrl"] is None


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


class _FakeSession:
    def __init__(self, invitation, user=None, company=None) -> None:
        self._invitation = invitation
        self._user = user
        self._company = company

    async def get(self, model, id_):
        return self._invitation

    async def execute(self, stmt):
        # Not a real `Select` evaluation — a canned result keyed off which
        # entity the statement targets, so `UserRepository.get_active`
        # (host-creation-email tests) and `CompanyRepository.get_singleton`
        # (every notification task's new branding-context lookup) each get
        # back the fake row the test actually configured, not each other's.
        entity = stmt.column_descriptions[0]["entity"]
        if entity is Company:
            return _FakeScalarResult(self._company)
        return _FakeScalarResult(self._user)


def _fake_tenant_session_scope(invitation, user=None, company=None):
    @asynccontextmanager
    async def _scope(schema_name: str):
        yield _FakeSession(invitation, user=user, company=company)

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


async def test_send_approval_notification_delivers_email_with_qr_via_mailpit(monkeypatch) -> None:
    tracking_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    recipient = f"mailpit-check-{uuid.uuid4().hex[:8]}@example.com"
    fake_invitation = _FakeInvitation(
        status="approved",
        tracking_id=tracking_id,
        primary_contact_preferred_contact_method="email",
        primary_contact_email=recipient,
        primary_contact_phone=None,
    )
    # `notifications.email_sender` is deliberately left as the real
    # `SmtpEmailSender` here (unlike every other task test above) so a real
    # SMTP send goes out for Mailpit to actually capture.
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

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
        assert detail["Subject"] == "Your visit is confirmed"
        assert len(detail["Attachments"]) == 1
        attachment = detail["Attachments"][0]
        assert attachment["ContentType"] == "image/png"
        assert attachment["FileName"] == "visit-qr.png"

        part_response = await mailpit.get(
            f"{_MAILPIT_BASE_URL}/message/{message_id}/part/{attachment['PartID']}"
        )
        assert part_response.status_code == 200
        qr_image = Image.open(io.BytesIO(part_response.content))
        qr_image.verify()
        assert qr_image.format == "PNG"
    # Deliberately not deleted from Mailpit afterward — left for a human to
    # inspect via the Mailpit web UI (task 5.4), and harmless to accumulate
    # since each run uses a fresh, unique tracking_id/recipient.


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
        assert detail["Subject"] == "Your registration is received"
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
        assert detail_response.json()["Subject"] == "Your visit request was not approved"


async def test_send_reschedule_notification_delivers_email_via_mailpit(monkeypatch) -> None:
    """Same real-SMTP-round-trip bar, extended to the reschedule
    notification per design.md Decision 1.
    """
    tracking_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    recipient = f"mailpit-check-{uuid.uuid4().hex[:8]}@example.com"
    fake_invitation = _FakeInvitation(
        status="approved",
        tracking_id=tracking_id,
        preferred_visit_date="2026-12-01",
        preferred_visit_time="15:30:00",
        primary_contact_preferred_contact_method="email",
        primary_contact_email=recipient,
        primary_contact_phone=None,
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
        assert detail_response.json()["Subject"] == "Your visit has been rescheduled"


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
        assert detail_response.json()["Subject"] == "You've been named host"


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
    Directly") — no resolved `hostId` results from approving it directly,
    since only delegating a step resolves the host.
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
    assert response.json()["data"]["hostId"] is None


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
        preferred_visit_date="2026-12-01",
        preferred_visit_time="15:30:00",
        primary_contact_preferred_contact_method="sms",
        primary_contact_email=None,
        primary_contact_phone="+1 555 0100",
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
    assert sms_sent[0]["to"] == "+1 555 0100"
    assert "INV-TEST0002" in sms_sent[0]["body"]


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


async def test_create_invitation_configured_chain_does_not_preempt_ownership_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """A category's own configured `ApprovalWorkflowRule` chain no longer
    determines which step gets pushed at submission — the unconditional
    `stepOrder` 0 ownership step is always current first, regardless of what
    role a category's own chain configures at `stepOrder` 1+.
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

    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitorCategoryId"] = str(category.id)
    await _create_invitation_success(client, token, branch, payload=payload)

    assert len(role_calls) == 1
    assert role_calls[0]["role_id"] == reception_role.id
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


async def test_every_notification_template_renders_without_error() -> None:
    """spec.md "Every Notification Email Is Rendered From a Branded HTML
    Template" — each template renders given a representative context,
    without raising.
    """
    from vmss_api.core.email_rendering import render_email_html

    representative_context = {
        "company_name": "Acme Test Co",
        "logo_url": None,
        "tracking_id": "INV-TEST0001",
        "visitor_name": "Meera Krishnan",
        "purpose": "Interview",
        "visit_date": "2026-10-01",
        "visit_time": "10:00",
        "duration": "1 hour",
        "department": "Engineering",
        "denial_reason": "Not expected",
        "host_name": "Rahul Nair",
        "host_contact": "rahul@example.com",
        "front_desk_contact": None,
    }
    for template_name in (
        "tracking_only",
        "visit_confirmation",
        "denial",
        "reschedule",
        "edit",
        "submission_role",
        "host_assigned",
    ):
        subject, html = render_email_html(template_name, representative_context)
        assert subject
        assert "<html" in html
        assert "INV-TEST0001" in html


async def test_template_rendering_failure_falls_back_to_plain_text(monkeypatch) -> None:
    """spec.md "Template Rendering Failure Falls Back to a Minimal
    Plain-Text Email" — a forced rendering failure still results in a
    deliverable (plain-text-only) email, logged at `ERROR`.
    """
    from vmss_api.core.email_rendering import TemplateRenderError

    def _raise(*args, **kwargs):
        raise TemplateRenderError("forced failure")

    monkeypatch.setattr(tasks, "render_email_html", _raise)
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
    del payload["consents"]["safety_guidelines_accepted"]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 201, response.text


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
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields", json=body, headers=headers
    )
    assert create_response.status_code == 201, create_response.text

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    return create_response.json()["data"]


async def test_create_invitation_captures_primary_contact_custom_field(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    await _create_and_publish_custom_field(
        client, token, branch, step_key="visitor_info", key="employee_id"
    )

    payload = _individual_payload()
    payload["primaryContact"]["customFieldValues"] = {"employee_id": "E-1001"}
    data = await _create_invitation_success(client, token, branch, payload=payload)

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["data"]["primaryContactCustomFieldValues"] == {
        "employee_id": "E-1001"
    }


async def test_create_invitation_captures_co_visitor_custom_fields_independently(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Two visitors answering the same admin-authored Visitor Info field
    each keep their own independent answer."""
    token = await _login(client, user.email)
    await _create_and_publish_custom_field(
        client, token, branch, step_key="visitor_info", key="employee_id"
    )

    payload = _group_payload()
    payload["primaryContact"]["customFieldValues"] = {"employee_id": "E-1001"}
    payload["visitors"][0]["customFieldValues"] = {"employee_id": "E-2002"}
    data = await _create_invitation_success(
        client, token, branch, payload=payload, visitor_file_count=2
    )

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    body = detail_response.json()["data"]
    assert body["primaryContactCustomFieldValues"] == {"employee_id": "E-1001"}
    visitors_by_name = {v["fullName"]: v for v in body["visitors"]}
    assert visitors_by_name["Alexander Pierce"]["customFieldValues"] == {"employee_id": "E-2002"}
    assert visitors_by_name["Clara Oswald"]["customFieldValues"] == {}


async def test_create_invitation_captures_vehicle_custom_field(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    await _create_and_publish_custom_field(
        client, token, branch, step_key="vehicle_info", key="parking_zone"
    )

    payload = _group_payload()
    payload["vehicles"][0]["customFieldValues"] = {"parking_zone": "B2"}
    data = await _create_invitation_success(
        client, token, branch, payload=payload, visitor_file_count=2
    )

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    vehicles = detail_response.json()["data"]["vehicles"]
    vehicles_by_plate = {v["licensePlate"]: v for v in vehicles}
    assert vehicles_by_plate["KA-01-AB-1234"]["customFieldValues"] == {"parking_zone": "B2"}
    assert vehicles_by_plate["KA-05-CD-5678"]["customFieldValues"] == {}


async def test_create_invitation_captures_invitation_level_custom_field(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A custom field on Visit Details (no per-entity structure of its own)
    is captured once per invitation."""
    token = await _login(client, user.email)
    await _create_and_publish_custom_field(
        client, token, branch, step_key="visit_details", key="cost_center"
    )

    payload = _individual_payload()
    payload["customFieldValues"] = {"cost_center": "CC-42"}
    data = await _create_invitation_success(client, token, branch, payload=payload)

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert detail_response.json()["data"]["customFieldValues"] == {"cost_center": "CC-42"}


async def test_create_invitation_custom_field_unknown_key_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["customFieldValues"] = {"not_a_configured_field": "x"}
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


async def test_create_invitation_seeded_carried_items_field_unaffected_by_custom_field(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Regression: adding an admin-authored field to Carried Items must not
    disturb the seeded `items` field's existing wire shape (`carriedItems.
    items`, mapped to the `carried_items` column) — only the new field's
    answer routes through `customFieldValues`."""
    token = await _login(client, user.email)
    await _create_and_publish_custom_field(
        client,
        token,
        branch,
        step_key="carried_items",
        key="company_badge",
        field_type="toggle_switch",
    )

    payload = _individual_payload()
    payload["carriedItems"] = {"items": ["laptop_tablet"]}
    payload["customFieldValues"] = {"company_badge": True}
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    body = detail_response.json()["data"]
    assert body["carriedItems"] == ["laptop_tablet"]
    assert body["customFieldValues"] == {"company_badge": True}


async def test_create_invitation_custom_consent_field_goes_through_consents(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Regression for design.md Decision 6: a new admin-authored Consent
    Agreement field is already captured by the pre-existing `consents` map
    (every field on that step, system or not) - it must not also be
    required in `customFieldValues`, and supplying it there instead of in
    `consents` must not satisfy the requirement.
    """
    token = await _login(client, user.email)
    await _create_and_publish_custom_field(
        client,
        token,
        branch,
        step_key="consent_agreement",
        key="extra_consent",
        field_type="toggle_switch",
        is_required=True,
    )

    payload = _individual_payload()
    payload["consents"]["extra_consent"] = True
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]

    wrong_scope_payload = _individual_payload()
    wrong_scope_payload["customFieldValues"] = {"extra_consent": True}
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
    await _create_and_publish_custom_field(
        client, token, branch, step_key="visit_details", key="cost_center"
    )
    payload = _individual_payload()
    payload["customFieldValues"] = {"cost_center": "CC-42"}
    data = await _create_invitation_success(client, token, branch, payload=payload)

    other_schema = "tenant_other_custom_field_test"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        result = await other_session.execute(
            select(Invitation).where(Invitation.tracking_id == data["trackingId"])
        )
        assert result.scalar_one_or_none() is None
