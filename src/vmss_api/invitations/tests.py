import asyncio
import io
import json
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosmtplib
import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import AsyncClient, Response
from PIL import Image
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from factories import (
    ApprovalWorkflowRuleFactory,
    CompanyFactory,
    DepartmentFactory,
    InvitationApprovalStepFactory,
    InvitationFactory,
    PermissionFactory,
    RoleFactory,
    UserFactory,
    VisitDurationFactory,
    VisitorCategoryFactory,
    VisitPurposeFactory,
)
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.auth.models import Permission, User, UserBranchRole
from vmss_api.auth.repository import RoleRepository
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.core.schemas import SortOrder
from vmss_api.core.security import hash_password
from vmss_api.invitations import notifications, tasks
from vmss_api.invitations import service as invitations_service
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.notifications import service as notifications_service
from vmss_api.org_structure.models import Branch, Department
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
        "consents": {
            "termsAccepted": True,
            "dataProcessingAccepted": True,
            "safetyGuidelinesAccepted": True,
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
            "termsAccepted": True,
            "dataProcessingAccepted": True,
            "safetyGuidelinesAccepted": True,
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
    files = [("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg"))]
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
    assert invitation.terms_accepted is True


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
        files=[("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg"))],
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
        files=[("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg"))],
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
    payload["consents"]["safetyGuidelinesAccepted"] = False
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_disguised_file_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(_individual_payload())},
        files={
            "primary_contact_id_proof_file": (
                "id.jpg",
                b"this is not actually an image, just plain text bytes",
                "image/jpeg",
            )
        },
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
        ConsentsSubmit,
        InvitationCreate,
        InvitationPrimaryContactCreate,
        VehicleSubmit,
        VisitDetailsSubmit,
        VisitorSubmit,
    )

    description = router._PAYLOAD_DESCRIPTION
    models: list[type[BaseModel]] = [
        InvitationCreate,
        InvitationPrimaryContactCreate,
        VisitorSubmit,
        VisitDetailsSubmit,
        CarriedItemsSubmit,
        VehicleSubmit,
        ConsentsSubmit,
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


async def test_track_by_tracking_id_omits_current_step_for_non_workflow_invitation(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """invitation-multi-step-approval spec.md "Non-workflow invitation omits
    step progress" — the default test category has no configured
    `ApprovalWorkflowRule`s.
    """
    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=_individual_payload())

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
    snapshots two steps at submission; the tracking lookup surfaces the
    first one as current.
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
        "purposeOfVisit",
        "expiresAt",
        "submittedAt",
        "approvedAt",
    }
    assert row["visitorCategoryId"] is None


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


class _FakeSession:
    def __init__(self, invitation) -> None:
        self._invitation = invitation

    async def get(self, model, id_):
        return self._invitation


def _fake_tenant_session_scope(invitation):
    @asynccontextmanager
    async def _scope(schema_name: str):
        yield _FakeSession(invitation)

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
        },
    )
    assert result.failed()
    assert logged and logged[0][0] == "approval_notification_dispatch_exhausted"


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
    visit_host: User,
    visit_duration: VisitDuration,
    visit_department: Department,
) -> None:
    """spec.md "Submission with an id overwrites free text with the catalog
    value" — a mismatched free-text string is discarded in favor of the
    referenced row's canonical name.
    """
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["purposeOfVisit"] = "does not match the catalog row"
    payload["visitDetails"]["hostNameOrEmail"] = "does not match either"
    payload["visitDetails"]["expectedDuration"] = "nor this"
    payload["visitDetails"]["departmentToVisit"] = "nor this either"
    payload["visitDetails"]["purposeId"] = str(visit_purpose.id)
    payload["visitDetails"]["hostId"] = str(visit_host.id)
    payload["visitDetails"]["durationId"] = str(visit_duration.id)
    payload["visitDetails"]["departmentId"] = str(visit_department.id)

    data = await _create_invitation_success(client, token, branch, payload=payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert invitation.purpose_of_visit == visit_purpose.name
    assert invitation.host_name_or_email == visit_host.full_name
    assert invitation.expected_duration == visit_duration.name
    assert invitation.department_to_visit == visit_department.name
    assert invitation.purpose_id == visit_purpose.id
    assert invitation.host_id == visit_host.id
    assert invitation.duration_id == visit_duration.id
    assert invitation.department_id == visit_department.id


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
    steps/{stepId}/approve` expects, with no separate lookup needed. A
    resolved `hostId` with no configured workflow rules snapshots exactly
    one host-identified step, so the host is the current approver.
    """
    # Reuse the existing global `invitations:approve` permission row (the
    # `user` fixture already seeded it — `conftest.py`'s standard admin
    # permission set) rather than inserting a second one with the same
    # unique `code`.
    permission = (
        await db_session.execute(select(Permission).where(Permission.code == "invitations:approve"))
    ).scalar_one()
    role = RoleFactory.build(id=uuid.uuid4(), name="host-approver-role", permissions=[permission])
    db_session.add(role)
    await db_session.flush()
    # Append in-memory too, not just `session.add()` — see
    # `approvals/tests.py::_grant_approve_permission`'s docstring for why
    # the test session's `expire_on_commit=False` makes this necessary.
    branch_role = UserBranchRole(
        id=uuid.uuid4(), user_id=visit_host.id, role=role, branch_id=branch.id
    )
    visit_host.branch_roles.append(branch_role)
    db_session.add(branch_role)
    await db_session.commit()

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["hostId"] = str(visit_host.id)
    data = await _create_invitation_success(client, token, branch, payload=payload)

    assert data["hostId"] == str(visit_host.id)
    assert data["currentApprovalStep"] is not None
    step_id = data["currentApprovalStep"]["id"]
    assert data["currentApprovalStep"]["approverUserId"] == str(visit_host.id)
    assert data["currentApprovalStep"]["approverRoleId"] is None

    host_token = issue_token(visit_host)
    response = await client.post(
        f"/api/v1/invitations/{data['id']}/approval-steps/{step_id}/approve",
        headers={"Authorization": f"Bearer {host_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "approved"


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


# --- PATCH /invitations/{id}/check-in -------------------------------------------


async def test_check_in_invitation_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/check-in",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "checked_in"

    await db_session.refresh(invitation)
    assert invitation.status == "checked_in"
    assert invitation.checked_in_at is not None
    assert invitation.checked_in_by_user_id == user.id


async def test_check_in_invitation_non_approved_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/check-in",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"


async def test_check_in_invitation_watchlist_flagged_blocked(
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
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/check-in",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "approved"


async def test_check_in_invitation_succeeds_after_watchlist_override(
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
    headers = {"Authorization": f"Bearer {token}"}

    override_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/watchlist-override",
        json={"reason": "Confirmed false positive"},
        headers=headers,
    )
    assert override_response.status_code == 200

    check_in_response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/check-in", headers=headers
    )
    assert check_in_response.status_code == 200
    assert check_in_response.json()["data"]["status"] == "checked_in"

    await db_session.refresh(invitation)
    assert invitation.watchlist_flagged is False
    assert invitation.watchlist_override_reason == "Confirmed false positive"
    assert invitation.watchlist_override_by_user_id == user.id
    assert invitation.status == "checked_in"


async def test_check_in_invitation_idempotency_key_replay(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "checkin-key-1"}

    first = await client.patch(f"/api/v1/invitations/{invitation.id}/check-in", headers=headers)
    second = await client.patch(f"/api/v1/invitations/{invitation.id}/check-in", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


async def test_check_in_invitation_requires_permission(
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
        f"/api/v1/invitations/{invitation.id}/check-in",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    await db_session.refresh(invitation)
    assert invitation.status == "approved"


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
    badge_bytes = Path(data["badgeUrl"]).read_bytes()
    assert Image.open(io.BytesIO(badge_bytes)).format == "PNG"


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


async def test_create_invitation_submission_notifies_host_step_approver(
    client: AsyncClient, user: User, branch: Branch, visit_host: User, monkeypatch
) -> None:
    """specs/invitations/spec.md "Invitation Submission Notifies the
    Approval Workflow's First Approver(s) via Push" — a resolved host gets
    an implicit host-identified step 0, which is pushed at submission.
    """
    calls: list[dict] = []
    email_calls: list[dict] = []

    async def _fake_notify_step_approver(tenant_db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_step_approver", _fake_notify_step_approver)
    monkeypatch.setattr(
        tasks.send_tracking_notification, "delay", lambda **kw: email_calls.append(kw)
    )

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["hostId"] = str(visit_host.id)
    created = await _create_invitation_success(client, token, branch, payload=payload)

    # Push to the host-identified step approver ...
    assert len(calls) == 1
    assert calls[0]["approver_user_id"] == visit_host.id
    assert calls[0]["approver_role_id"] is None
    assert calls[0]["branch_id"] == branch.id
    # ... and, for the same submission, the visitor's own tracking email/SMS
    # (proposal.md finding #1 — both channels must fire for the same request,
    # not just whichever one this test happened to check).
    assert len(email_calls) == 1
    assert email_calls[0]["invitation_id"] == created["id"]


async def test_create_invitation_non_admin_role_identified_step_notifies_role(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """specs/invitations/spec.md "Submission with a role-identified first
    step" (exclude-admin-role-only-from-push) — no resolved host, and the
    category's workflow gives it a role-identified step 0 for a role other
    than `admin`. That role's holders still get pushed.
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


async def test_create_invitation_admin_role_identified_step_sends_no_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """specs/invitations/spec.md "Submission with an Admin-role first step
    sends no push" — no resolved host, and the category's workflow gives it
    a role-identified step 0 for the tenant's standard `admin` role
    (already seeded by the `user` fixture). No push is dispatched to anyone.
    """
    admin_role = await RoleRepository(db_session).get_by_name("admin")
    assert admin_role is not None  # seeded by the `user` fixture

    category = VisitorCategoryFactory.build(
        id=uuid.uuid4(), name="Admin Workflow Category", code="ADMIN-WORKFLOW-CAT"
    )
    db_session.add(category)
    await db_session.flush()
    db_session.add(
        ApprovalWorkflowRuleFactory.build(
            id=uuid.uuid4(),
            visitor_category_id=category.id,
            step_order=1,
            approver_role_id=admin_role.id,
        )
    )
    await db_session.commit()

    user_calls: list[dict] = []
    role_calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        user_calls.append(kwargs)

    async def _fake_notify_role_at_branch(tenant_db, **kwargs):
        role_calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)
    monkeypatch.setattr(notifications_service, "notify_role_at_branch", _fake_notify_role_at_branch)

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitorCategoryId"] = str(category.id)
    await _create_invitation_success(client, token, branch, payload=payload)

    assert user_calls == []
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


async def test_create_invitation_hostless_no_rules_skips_push(
    client: AsyncClient, user: User, branch: Branch, monkeypatch
) -> None:
    """No resolved host, and the default test category
    (`_default_visitor_category`) has no active workflow rules — zero
    approval steps, so nothing to push (proposal.md's "no push recipient"
    case).
    """
    calls: list[dict] = []

    async def _fake_notify_step_approver(tenant_db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_step_approver", _fake_notify_step_approver)

    token = await _login(client, user.email)
    await _create_invitation_success(client, token, branch, payload=_individual_payload())

    assert calls == []


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
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """No dual-channel assertion here (unlike submit/approve/deny/reschedule,
    proposal.md finding #1): `invitations/service.py::check_in_invitation`
    dispatches only the host push, no visitor-facing email/SMS task — there
    is nothing on the other channel to assert.
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

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/check-in",
        headers={"Authorization": f"Bearer {token}"},
    )
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
