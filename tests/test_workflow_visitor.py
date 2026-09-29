"""End-to-end visitor workflow chains (openspec/changes/add-end-to-end-workflow-tests).

Two chains, each carrying the real id/token a prior HTTP response actually
returned into the next call rather than a hardcoded or fixture-shortcut
value:

1. Invitation-created path: an authenticated staff member creates an
   invitation -> the visitor (unauthenticated) completes identity
   verification (OTP request + verify) -> the visitor tracks the real
   invitation via the public tracking endpoint.
2. Walk-in path: a device-key-authenticated kiosk registration replaces the
   staff-created invitation, feeding its own real tracking id into the same
   public tracking lookup.

Per design.md, this chain does not need a freshly provisioned tenant -- it
reuses the shared `client` fixture and the existing `tenant`/`branch`/`user`
conftest fixtures the same way every other feature's tests already do.
"""

import io
import json
import re
import uuid

import pytest_asyncio
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from factories import RoleFactory, VisitorCategoryFactory
from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.identity_verification import senders
from vmss_api.invitations import tasks
from vmss_api.org_structure.models import Branch

# Reused directly as a fixture (design.md task 7.1: "import ... or replicate
# it locally" -- importing avoids a second copy of the device-key seeding
# logic drifting out of sync with the original).
from vmss_api.registrations.tests import registration_device_raw_key  # noqa: F401

# invitation-multi-step-approval: same fixed-id/autouse-fixture pattern as
# `invitations/tests.py`/`registrations/tests.py` -- this file builds its own
# payloads locally rather than importing theirs, so it needs its own category
# fixture too (an autouse fixture defined in another test module doesn't
# apply here just because one of that module's other fixtures is imported).
_DEFAULT_VISITOR_CATEGORY_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


@pytest_asyncio.fixture(autouse=True)
async def _default_visitor_category(db_session: AsyncSession) -> None:
    db_session.add(
        VisitorCategoryFactory.build(
            id=_DEFAULT_VISITOR_CATEGORY_ID,
            name="Default Workflow Test Category",
            code="WORKFLOW-TEST-DEFAULT",
        )
    )
    await db_session.commit()


@pytest_asyncio.fixture(autouse=True)
async def _default_host_role(db_session: AsyncSession) -> None:
    """`create_invitation` now always resolves the tenant's default host
    role (role-based-invitation-workflow) — same rationale as
    `invitations/tests.py::_default_host_role`; this file builds its own
    copy for the same reason `_default_visitor_category` above does.
    """
    db_session.add(RoleFactory.build(id=uuid.uuid4(), name="reception", permissions=[]))
    await db_session.commit()


@pytest_asyncio.fixture(autouse=True)
def _default_tenant_slug_matches_test_tenant(monkeypatch):
    """`GET /invitations/track` and the identity-verification public
    endpoints have no bearer token to resolve a tenant from and fall back to
    `settings.default_tenant_slug`. Mirrors `invitations/tests.py` and
    `identity_verification/tests.py`'s fixture of the same name so this
    default resolves to the same `acme-test` tenant the `tenant` fixture
    creates.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")


@pytest_asyncio.fixture(autouse=True)
def _stub_visit_confirmation_dispatch(monkeypatch):
    """Matches the pattern `invitations/tests.py` already uses: the
    confirmation email is a Celery task dispatch, not something this chain
    needs to actually deliver to assert the workflow composes correctly.
    Stubs both notification tasks — no `Company` profile is configured in
    this chain, so creation resolves to `submitted` (`send_tracking_notification`),
    but stubbing `send_approval_notification` too keeps this fixture correct
    if that ever changes.
    """
    monkeypatch.setattr(tasks.send_tracking_notification, "delay", lambda **kw: None)
    monkeypatch.setattr(tasks.send_approval_notification, "delay", lambda **kw: None)


class _RecordingEmailSender:
    """Mirrors `identity_verification/tests.py::_RecordingSender` -- captures
    the OTP email body so the real code can be extracted and used in the
    verify step, instead of guessing it.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send(self, **kwargs) -> None:
        self.calls.append(kwargs)


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="JPEG")
    return buffer.getvalue()


def _individual_payload(full_name: str) -> dict:
    return {
        "registrationType": "individual",
        "visitorCategoryId": str(_DEFAULT_VISITOR_CATEGORY_ID),
        "primaryContact": {
            "fullName": full_name,
            "email": f"{full_name.lower().replace(' ', '.')}@example.com",
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
            "terms_accepted": True,
            "data_processing_accepted": True,
            "safety_guidelines_accepted": True,
        },
    }


async def _login(client: AsyncClient, email: str, password: str = "correct-password") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["data"]["accessToken"]


def _extract_otp_code(body: str) -> str:
    match = re.search(r"code is (\d+)", body)
    assert match is not None, body
    return match.group(1)


def _unique_email_identifier() -> str:
    return f"otp-{uuid.uuid4().hex[:10]}@example.com"


# --- Chain 1: invitation-created path -----------------------------------------


async def test_invitation_created_visitor_workflow_end_to_end(
    client: AsyncClient, user: User, branch: Branch, monkeypatch
) -> None:
    recorder = _RecordingEmailSender()
    monkeypatch.setattr(senders, "email_sender", recorder)

    # Step 1: an authenticated staff member creates an invitation.
    token = await _login(client, user.email)
    create_response = await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(_individual_payload("Meera Krishnan"))},
        files=[
            ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert create_response.status_code == 201, create_response.text
    invitation_data = create_response.json()["data"]
    tracking_id = invitation_data["trackingId"]
    assert tracking_id.startswith("INV-")

    # Step 2: the visitor (unauthenticated) proves control of their own
    # identifier via OTP request + verify.
    identifier = _unique_email_identifier()
    otp_request_response = await client.post(
        "/api/v1/identity-verification/otp/request",
        json={"identifier": identifier, "channel": "email"},
    )
    assert otp_request_response.status_code == 200, otp_request_response.text
    assert len(recorder.calls) == 1
    code = _extract_otp_code(recorder.calls[0]["body"])

    otp_verify_response = await client.post(
        "/api/v1/identity-verification/otp/verify",
        json={"identifier": identifier, "channel": "email", "code": code},
    )
    assert otp_verify_response.status_code == 200, otp_verify_response.text
    verify_data = otp_verify_response.json()["data"]
    proof_token = verify_data["proofToken"]
    assert proof_token

    # Step 3: the visitor tracks the real invitation using the tracking id
    # step 1 actually returned -- not a hardcoded value.
    track_response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": tracking_id}
    )
    assert track_response.status_code == 200, track_response.text
    tracking_data = track_response.json()["data"]
    assert tracking_data["trackingId"] == tracking_id
    assert tracking_data["status"] == "submitted"
    assert tracking_data["registrationType"] == "individual"
    assert tracking_data["source"] == "staff_pre_registration"
    assert tracking_data["primaryContactFullName"] == "Meera Krishnan"


# --- Chain 2: walk-in path variant ---------------------------------------------


async def test_walk_in_visitor_workflow_end_to_end(
    client: AsyncClient,
    registration_device_raw_key: str,  # noqa: F811 -- reuses the imported fixture
) -> None:
    # Step 1 (variant): a device-key-authenticated kiosk registers the
    # visitor directly, with no staff-created invitation and no bearer token.
    walk_in_response = await client.post(
        "/api/v1/registrations/walk-in",
        data={"payload": json.dumps(_individual_payload("Walk In Visitor"))},
        files=[
            ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
        headers={"X-Device-Key": registration_device_raw_key},
    )
    assert walk_in_response.status_code == 201, walk_in_response.text
    registration_data = walk_in_response.json()["data"]
    tracking_id = registration_data["trackingId"]
    assert tracking_id.startswith("INV-")

    # Step 2: the same public tracking lookup, fed the real tracking id the
    # walk-in registration actually returned.
    track_response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": tracking_id}
    )
    assert track_response.status_code == 200, track_response.text
    tracking_data = track_response.json()["data"]
    assert tracking_data["trackingId"] == tracking_id
    assert tracking_data["status"] == "submitted"
    assert tracking_data["registrationType"] == "individual"
    assert tracking_data["source"] == "visitor_walk_in"
    assert tracking_data["primaryContactFullName"] == "Walk In Visitor"
