import asyncio
import io
import json
import uuid
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import AsyncClient, Response
from PIL import Image
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.invitations import notifications, tasks
from vmss_api.invitations import service as invitations_service
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="JPEG")
    return buffer.getvalue()


def _individual_payload() -> dict:
    return {
        "registrationType": "individual",
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
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await _create_invitation(
        client,
        token,
        branch,
        payload=payload_factory(),
        visitor_file_count=visitor_file_count,
    )
    assert response.status_code == 403


async def test_create_invitation_without_branch_header_rejected(
    client: AsyncClient, user: User
) -> None:
    """`InvitationCreate` carries no branch-identifying field of its own, so
    unlike other creation endpoints, `X-Branch-ID` is still the only signal
    that can resolve one — omitting it is a handled 400, not FastAPI's
    generic required-header 422.
    """
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(_individual_payload())},
        files=[("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg"))],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


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
    monkeypatch.setattr(tasks.send_visit_confirmation, "delay", lambda **kw: calls.append(kw))

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


async def test_send_visit_confirmation_skips_when_invitation_missing(monkeypatch) -> None:
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(None))

    result = await asyncio.to_thread(
        tasks.send_visit_confirmation.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)
    assert sent == []  # invitation no longer exists — nothing to notify about


async def test_send_visit_confirmation_exhausted_retries_logs_error(monkeypatch) -> None:
    class _FailingEmailSender:
        async def send(self, **kwargs):
            raise RuntimeError("SMTP is down")

    monkeypatch.setattr(notifications, "email_sender", _FailingEmailSender())
    fake_invitation = _FakeInvitation(
        status="submitted",
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
    monkeypatch.setattr(tasks.send_visit_confirmation, "max_retries", 0)

    result = await asyncio.to_thread(
        tasks.send_visit_confirmation.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
        },
    )
    assert result.failed()
    assert logged and logged[0][0] == "visit_confirmation_dispatch_exhausted"


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


async def test_send_visit_confirmation_delivers_email_with_qr_via_mailpit(monkeypatch) -> None:
    tracking_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    recipient = f"mailpit-check-{uuid.uuid4().hex[:8]}@example.com"
    fake_invitation = _FakeInvitation(
        status="submitted",
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
        tasks.send_visit_confirmation.apply,
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
