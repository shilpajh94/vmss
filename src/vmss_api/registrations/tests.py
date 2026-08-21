import io
import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, Response
from PIL import Image
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.core.security import hash_password
from vmss_api.invitations import tasks
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.org_structure.models import Branch
from vmss_api.registrations.models import RegistrationDeviceKey
from vmss_api.tenant.models import Tenant


@pytest_asyncio.fixture
async def registration_device_raw_key(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> str:
    """A provisioned walk-in kiosk credential for `branch` (API-13). Only the
    raw key is ever handed back — same "shown once, never stored" pattern as
    a real device provisioning flow (`registrations/models.py::RegistrationDeviceKey`).
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


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="JPEG")
    return buffer.getvalue()


def _individual_payload() -> dict:
    return {
        "registrationType": "individual",
        "primaryContact": {
            "fullName": "Walk In Visitor",
            "email": "walkin.visitor@example.com",
            "preferredContactMethod": "email",
            "idProofType": "Passport",
        },
        "visitors": [],
        "visitDetails": {
            "purposeOfVisit": "Delivery",
            "hostNameOrEmail": "reception@enterprise-ugo.co",
            "preferredVisitDate": "2026-08-19",
            "preferredVisitTime": "10:00:00",
            "expectedDuration": "< 1 hour",
            "departmentToVisit": "Reception",
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
    payload = _individual_payload()
    payload["registrationType"] = "group"
    payload["visitors"] = [
        {"fullName": "Co Visitor One", "email": "co1@example.com", "idProofType": "Aadhaar Card"},
        {"fullName": "Co Visitor Two", "phone": "+91 90000 22233", "idProofType": "Passport"},
    ]
    return payload


async def _create_walk_in(
    client: AsyncClient,
    device_key: str | None,
    *,
    payload: dict,
    visitor_file_count: int = 0,
    idempotency_key: str | None = None,
) -> Response:
    headers = {}
    if device_key is not None:
        headers["X-Device-Key"] = device_key
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    files = [("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg"))]
    files += [
        ("visitor_id_proof_files", (f"v{i}.jpg", _jpeg_bytes(), "image/jpeg"))
        for i in range(visitor_file_count)
    ]
    return await client.post(
        "/api/v1/registrations/walk-in",
        data={"payload": json.dumps(payload)},
        files=files,
        headers=headers,
    )


async def _create_walk_in_success(
    client: AsyncClient,
    device_key: str,
    *,
    payload: dict,
    visitor_file_count: int = 0,
    idempotency_key: str | None = None,
) -> dict:
    response = await _create_walk_in(
        client,
        device_key,
        payload=payload,
        visitor_file_count=visitor_file_count,
        idempotency_key=idempotency_key,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


# --- API-13: happy paths ------------------------------------------------------


async def test_create_individual_walk_in_registration_success(
    client: AsyncClient, registration_device_raw_key: str
) -> None:
    data = await _create_walk_in_success(
        client, registration_device_raw_key, payload=_individual_payload()
    )
    assert data["registrationType"] == "individual"
    assert data["source"] == "visitor_walk_in"
    assert data["status"] == "submitted"
    assert data["trackingId"].startswith("INV-")


async def test_create_group_walk_in_registration_success(
    client: AsyncClient, registration_device_raw_key: str, db_session: AsyncSession
) -> None:
    data = await _create_walk_in_success(
        client,
        registration_device_raw_key,
        payload=_group_payload(),
        visitor_file_count=2,
    )
    assert data["source"] == "visitor_walk_in"

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert len(invitation.visitors) == 2
    assert invitation.created_by_user_id is None
    assert invitation.source == "visitor_walk_in"


async def test_walk_in_registration_response_has_no_check_in_state(
    client: AsyncClient, registration_device_raw_key: str
) -> None:
    """spec.md "Walk-in registration creates a record only, not a check-in"."""
    data = await _create_walk_in_success(
        client, registration_device_raw_key, payload=_individual_payload()
    )
    assert set(data.keys()) == {
        "id",
        "trackingId",
        "registrationType",
        "source",
        "status",
        "expiresAt",
        "submittedAt",
    }


async def test_walk_in_registration_visitor_list_mismatch_rejected(
    client: AsyncClient, registration_device_raw_key: str
) -> None:
    payload = _individual_payload()
    payload["visitors"] = [
        {"fullName": "Extra Person", "email": "extra@example.com", "idProofType": "Passport"}
    ]
    response = await _create_walk_in(client, registration_device_raw_key, payload=payload)
    assert response.status_code == 422


# --- File validation at this router's own HTTP boundary ----------------------
# (the validation logic itself is shared with `invitations.service` and is
# already tested there — this is a smoke test that the check is actually wired
# up on this endpoint too, not a re-test of the validation rules themselves.)


async def test_walk_in_registration_disguised_file_rejected(
    client: AsyncClient, registration_device_raw_key: str
) -> None:
    response = await client.post(
        "/api/v1/registrations/walk-in",
        data={"payload": json.dumps(_individual_payload())},
        files={
            "primary_contact_id_proof_file": (
                "id.jpg",
                b"this is not actually an image, just plain text bytes",
                "image/jpeg",
            )
        },
        headers={"X-Device-Key": registration_device_raw_key},
    )
    assert response.status_code == 422


async def test_walk_in_registration_oversized_file_rejected(
    client: AsyncClient, registration_device_raw_key: str, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "invitation_max_upload_size_bytes", 10)
    response = await _create_walk_in(
        client, registration_device_raw_key, payload=_individual_payload()
    )
    assert response.status_code == 422


# --- Device-auth-denied (testing-standards.md §2's permission-denied case) ---


async def test_walk_in_registration_missing_device_key_falls_back_to_default_tenant_success(
    client: AsyncClient, tenant: Tenant, branch: Branch, monkeypatch
) -> None:
    """`X-Device-Key` is optional (`registrations/deps.py::_resolve_default_device_context`)
    — omitting it resolves tenant/branch from server config instead of
    rejecting outright, the same `default_tenant_slug` pattern
    `identity_verification`/`invitations.track` already use for their public
    endpoints.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")
    monkeypatch.setattr(settings, "registration_default_branch_code", branch.code)

    data = await _create_walk_in_success(client, None, payload=_individual_payload())
    assert data["source"] == "visitor_walk_in"
    assert data["status"] == "submitted"


async def test_walk_in_registration_missing_device_key_no_default_tenant_rejected(
    client: AsyncClient,
) -> None:
    """No `X-Device-Key` and no `default_tenant_slug` match in this schema
    (the test tenant's slug is `acme-test`, not `settings.default_tenant_slug`'s
    unmodified default) — the fallback must still reject rather than resolve
    to nothing.
    """
    response = await _create_walk_in(client, None, payload=_individual_payload())
    assert response.status_code == 401


async def test_walk_in_registration_missing_device_key_no_default_branch_rejected(
    client: AsyncClient, tenant: Tenant, branch: Branch, monkeypatch
) -> None:
    """The default tenant resolves, but no branch matches
    `registration_default_branch_code` — must still reject, not fall through
    to an unscoped branch.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")
    monkeypatch.setattr(settings, "registration_default_branch_code", "NO-SUCH-BRANCH")

    response = await _create_walk_in(client, None, payload=_individual_payload())
    assert response.status_code == 401


async def test_walk_in_registration_invalid_device_key_rejected(
    client: AsyncClient, registration_device_raw_key: str
) -> None:
    response = await _create_walk_in(
        client, "definitely-not-a-provisioned-key", payload=_individual_payload()
    )
    assert response.status_code == 401


async def test_walk_in_registration_inactive_device_key_rejected(
    client: AsyncClient, registration_device_raw_key: str, db_session: AsyncSession
) -> None:
    await db_session.execute(update(RegistrationDeviceKey).values(is_active=False))
    await db_session.commit()

    response = await _create_walk_in(
        client, registration_device_raw_key, payload=_individual_payload()
    )
    assert response.status_code == 401


# --- Rate limiting -------------------------------------------------------------


async def test_walk_in_registration_rate_limit_trips(
    client: AsyncClient, registration_device_raw_key: str, monkeypatch
) -> None:
    """`slowapi`'s `Limiter` is disabled outright in the test environment
    (`core/rate_limit.py`), flipped on here for just this test — same
    approach `invitations/tests.py::test_track_rate_limit_trips` uses.
    """
    monkeypatch.setattr(limiter, "enabled", True)
    responses = [
        await _create_walk_in(client, registration_device_raw_key, payload=_individual_payload())
        for _ in range(25)
    ]
    assert any(r.status_code == 429 for r in responses)


# --- Idempotency ---------------------------------------------------------------


async def test_walk_in_registration_idempotency_key_replay(
    client: AsyncClient, registration_device_raw_key: str, db_session: AsyncSession, monkeypatch
) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(tasks.send_visit_confirmation, "delay", lambda **kw: calls.append(kw))

    idempotency_key = "walk-in-retry-key-1"
    first = await _create_walk_in_success(
        client,
        registration_device_raw_key,
        payload=_group_payload(),
        visitor_file_count=2,
        idempotency_key=idempotency_key,
    )
    second = await _create_walk_in_success(
        client,
        registration_device_raw_key,
        payload=_group_payload(),
        visitor_file_count=2,
        idempotency_key=idempotency_key,
    )
    assert first == second

    invitations = await InvitationRepository(db_session).list()
    assert len(invitations) == 1
    assert len(calls) == 1


# --- Tenant isolation ------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload_factory", "visitor_file_count"),
    [(_individual_payload, 0), (_group_payload, 2)],
    ids=["individual", "group"],
)
async def test_walk_in_registration_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    registration_device_raw_key: str,
    client: AsyncClient,
    payload_factory,
    visitor_file_count: int,
) -> None:
    data = await _create_walk_in_success(
        client,
        registration_device_raw_key,
        payload=payload_factory(),
        visitor_file_count=visitor_file_count,
    )

    other_schema = "tenant_other_test_registrations"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await InvitationRepository(other_session).get_by_tracking_id(data["trackingId"])
        assert found is None
