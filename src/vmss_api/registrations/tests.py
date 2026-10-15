import io
import json
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
import starlette.datastructures as starlette_datastructures
import structlog
from httpx import AsyncClient, Response
from PIL import Image
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from factories import (
    BranchFactory,
    BuildingFactory,
    CompanyFactory,
    RoleFactory,
    VisitorCategoryFactory,
)
from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.auth.models import AuditLog, User
from vmss_api.auth.repository import RoleRepository
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.core.security import hash_password
from vmss_api.form_builder.defaults import _stable_id as _form_builder_stable_id
from vmss_api.invitations import tasks
from vmss_api.invitations.models import Invitation, InvitationVehicle, InvitationVisitor
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.org_structure.models import Branch
from vmss_api.registrations.models import RegistrationDeviceKey
from vmss_api.tenant.models import Tenant

# Same fixed-id/autouse-fixture pattern as `invitations/tests.py` — walk-in
# registration shares `InvitationCreate` (aliased `WalkInRegistrationCreate`)
# verbatim, so it now needs a valid `visitorCategoryId` too.
_DEFAULT_VISITOR_CATEGORY_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest_asyncio.fixture(autouse=True)
async def _default_visitor_category(db_session: AsyncSession) -> None:
    db_session.add(
        VisitorCategoryFactory.build(
            id=_DEFAULT_VISITOR_CATEGORY_ID, name="Default Walk-in Category", code="WALKIN-DEFAULT"
        )
    )
    await db_session.commit()


@pytest_asyncio.fixture(autouse=True)
async def _default_host_role(db_session: AsyncSession) -> None:
    """`create_invitation` (shared verbatim by walk-in registration) now
    always resolves the tenant's default host role
    (role-based-invitation-workflow) — same rationale as
    `invitations/tests.py::_default_host_role`.
    """
    db_session.add(RoleFactory.build(id=uuid.uuid4(), name="reception", permissions=[]))
    await db_session.commit()


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


@pytest_asyncio.fixture(autouse=True)
def _reset_live_consent_field_ids():
    """See `invitations/tests.py`'s fixture of the same name — resets the
    module-level cache `_record_live_consent_field_ids` populates before
    every test."""
    global _live_consent_field_ids
    _live_consent_field_ids = None
    yield


_live_consent_field_ids: dict[str, str] | None = None


def _record_live_consent_field_ids(steps: list[dict]) -> None:
    """See `invitations/tests.py::_record_live_consent_field_ids` — called
    by admin-side setup helpers right after publishing, since that seeds
    the branch's default Consent Agreement fields as real (random-id)
    database rows, no longer matching `_default_consent_field_id`'s
    deterministic fallback (restructure-walkin-payload-by-field-id)."""
    global _live_consent_field_ids
    step = next((s for s in steps if s["key"] == "consent_agreement"), None)
    if step is None:
        return
    _live_consent_field_ids = {f["key"]: f["id"] for f in step["fields"]}


def _default_consent_field_id(key: str) -> str:
    """See `invitations/tests.py::_default_consent_field_id` — the
    branch's own real id if a test has published anything for it
    (`_live_consent_field_ids`), otherwise the deterministic default-form
    id, since walk-in registration falls back to the same unpublished
    `DEFAULT_EFFECTIVE_FORM` (restructure-walkin-payload-by-field-id)."""
    if _live_consent_field_ids is not None and key in _live_consent_field_ids:
        return _live_consent_field_ids[key]
    return str(_form_builder_stable_id("field", "consent_agreement", key))


def _individual_payload() -> dict:
    return {
        "registrationType": "individual",
        "visitorCategoryId": str(_DEFAULT_VISITOR_CATEGORY_ID),
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
        # Referenced by fieldId, never key/label — see
        # invitations/schemas.py's `InvitationCreate.consents` docstring.
        "consents": [
            {"fieldId": _default_consent_field_id("terms_accepted"), "accepted": True},
            {"fieldId": _default_consent_field_id("data_processing_accepted"), "accepted": True},
            {"fieldId": _default_consent_field_id("safety_guidelines_accepted"), "accepted": True},
        ],
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
    files = [
        ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
        ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
    ]
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
    device_key: str | None,
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


async def _login(client: AsyncClient, email: str, password: str = "correct-password") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["data"]["accessToken"]


async def _create_and_publish_custom_field(
    client: AsyncClient,
    admin_token: str,
    branch: Branch,
    *,
    step_key: str,
    key: str,
    field_type: str = "text",
    is_required: bool = False,
    help_text: str | None = None,
) -> str:
    """Admin-side setup shared by the custom-field tests below — same
    pattern as `invitations/tests.py::_create_and_publish_custom_field`,
    duplicated here since walk-in registration has no staff bearer token of
    its own to reuse an imported helper's auth with. Returns the created
    field's id (restructure-walkin-payload-by-field-id) — the caller must
    reference it, never its `key`, in any `customFields`/`consents`/
    `groups` entry it submits."""
    headers = {"Authorization": f"Bearer {admin_token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == step_key)

    body: dict = {"key": key, "label": key.replace("_", " ").title(), "fieldType": field_type}
    if is_required:
        body["isRequired"] = True
    if help_text is not None:
        body["helpText"] = help_text
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields", json=body, headers=headers
    )
    assert create_response.status_code == 201, create_response.text
    field_id = create_response.json()["data"]["id"]

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])
    return field_id


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


async def test_walk_in_registration_expires_at_end_of_visit_day(
    client: AsyncClient, registration_device_raw_key: str, db_session: AsyncSession, branch: Branch
) -> None:
    """expire-invitation-at-end-of-visit-day — a walk-in's pass runs to the
    end of its visit day in the company's timezone, not a fixed TTL from
    submission.
    """
    building = BuildingFactory.build(id=uuid.uuid4(), branch_id=branch.id)
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), default_timezone="Asia/Kolkata"))
    db_session.add(building)
    await db_session.commit()

    payload = _individual_payload()
    payload["visitDetails"]["branchId"] = str(branch.id)
    payload["visitDetails"]["buildingId"] = str(building.id)
    data = await _create_walk_in_success(client, registration_device_raw_key, payload=payload)
    # `_individual_payload()` schedules 2026-08-19 → 23:59:59 IST.
    assert datetime.fromisoformat(data["expiresAt"]) == datetime(
        2026, 8, 19, 18, 29, 59, tzinfo=UTC
    )


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


# --- dedupe-repeat-visitor-registrations: returning primary contact --------
# Walk-in registration shares `invitations/service.py::create_invitation`
# verbatim, so the returning-primary-contact name lock
# (`invitations/tests.py`'s own coverage) must hold here too — see
# `specs/invitations/spec.md` (delta) "Walk-in registration applies the
# same lock".


async def test_walk_in_registration_returning_email_locks_full_name(
    client: AsyncClient, registration_device_raw_key: str, db_session: AsyncSession
) -> None:
    email = "walkin.returning@example.com"

    first_payload = _individual_payload()
    first_payload["primaryContact"]["email"] = email
    first_payload["primaryContact"]["fullName"] = "Original Walk-in Name"
    await _create_walk_in_success(client, registration_device_raw_key, payload=first_payload)

    second_payload = _individual_payload()
    second_payload["primaryContact"]["email"] = email
    second_payload["primaryContact"]["fullName"] = "Different Submitted Name"
    second_data = await _create_walk_in_success(
        client, registration_device_raw_key, payload=second_payload
    )

    invitation = await InvitationRepository(db_session).get_by_tracking_id(
        second_data["trackingId"]
    )
    assert invitation is not None
    assert invitation.primary_contact_full_name == "Original Walk-in Name"


async def test_walk_in_registration_phone_fallback_locks_name_and_email(
    client: AsyncClient, registration_device_raw_key: str, db_session: AsyncSession
) -> None:
    phone = "+91 98765 00011"

    first_payload = _individual_payload()
    first_payload["primaryContact"]["email"] = "walkin.phone.fallback@example.com"
    first_payload["primaryContact"]["fullName"] = "Phone Fallback Walk-in"
    first_payload["primaryContact"]["phone"] = phone
    await _create_walk_in_success(client, registration_device_raw_key, payload=first_payload)

    second_payload = _individual_payload()
    second_payload["primaryContact"] = {
        "fullName": "Different Submitted Name",
        "phone": phone,
        "preferredContactMethod": "sms",
        "idProofType": "Passport",
    }
    second_data = await _create_walk_in_success(
        client, registration_device_raw_key, payload=second_payload
    )

    invitation = await InvitationRepository(db_session).get_by_tracking_id(
        second_data["trackingId"]
    )
    assert invitation is not None
    assert invitation.primary_contact_full_name == "Phone Fallback Walk-in"
    assert invitation.primary_contact_email == "walkin.phone.fallback@example.com"


async def test_walk_in_registration_writes_audit_log_with_no_actor(
    client: AsyncClient, registration_device_raw_key: str, db_session: AsyncSession
) -> None:
    """spec.md "Walk-in registration is audited" / "Audit entry recorded
    with no actor" — no test previously asserted this, even though the
    write itself (`record_audit_log`, dispatched via `BackgroundTasks` in
    `router.py`) is real and already runs on every walk-in creation.
    """
    data = await _create_walk_in_success(
        client, registration_device_raw_key, payload=_individual_payload()
    )

    entry = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "walk_in_registration_created",
                AuditLog.entity_id == uuid.UUID(data["id"]),
            )
        )
    ).scalar_one()
    assert entry.actor_user_id is None
    assert entry.entity_type == "Invitation"


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
        "visitorCategoryId",
        "hostId",
        "pocUserId",
        "pocRoleId",
        "pocName",
        "expiresAt",
        "submittedAt",
        "approvedAt",
        "currentApprovalStep",
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
        files=[
            (
                "primary_contact_id_proof_file",
                ("id.jpg", b"this is not actually an image, just plain text bytes", "image/jpeg"),
            ),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
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


async def test_walk_in_registration_oversized_file_read_is_bounded(
    client: AsyncClient, registration_device_raw_key: str, monkeypatch
) -> None:
    """Sibling of `invitations/tests.py::test_create_invitation_oversized_file_read_is_bounded`
    — `POST /registrations/walk-in` accepts the identical multipart contract
    and must bound each `UploadFile.read()` call the same way
    (file-upload-handling.md §1), not just eventually reject an oversized
    upload after buffering it in full.
    """
    monkeypatch.setattr(settings, "invitation_max_upload_size_bytes", 10)
    read_sizes: list[int] = []
    original_read = starlette_datastructures.UploadFile.read

    async def _spy_read(self, size: int = -1) -> bytes:
        read_sizes.append(size)
        return await original_read(self, size)

    monkeypatch.setattr(starlette_datastructures.UploadFile, "read", _spy_read)

    response = await _create_walk_in(
        client, registration_device_raw_key, payload=_individual_payload()
    )

    assert response.status_code == 422
    assert read_sizes == [11, settings.invitation_max_photo_size_bytes + 1]


# --- Optional profile photo (checkin-approval-workflow-improvements) --------
# spec.md "Walk-in registration inherits the same optional photo capture" —
# `POST /registrations/walk-in` accepts the identical file-part contract
# `POST /invitations` does; validation itself is covered exhaustively by
# `invitations/tests.py`, so this only confirms the pass-through works.


async def test_walk_in_registration_with_primary_contact_photo_succeeds(
    client: AsyncClient, registration_device_raw_key: str
) -> None:
    files = [
        ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
        ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
    ]
    response = await client.post(
        "/api/v1/registrations/walk-in",
        data={"payload": json.dumps(_individual_payload())},
        files=files,
        headers={"X-Device-Key": registration_device_raw_key},
    )
    assert response.status_code == 201, response.text


async def test_walk_in_registration_without_primary_contact_photo_rejected(
    client: AsyncClient, registration_device_raw_key: str
) -> None:
    """require-primary-contact-photo spec.md "Missing primary contact photo
    is rejected", inherited via the identical file-part contract
    `POST /invitations` uses.
    """
    response = await client.post(
        "/api/v1/registrations/walk-in",
        data={"payload": json.dumps(_individual_payload())},
        files=[("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg"))],
        headers={"X-Device-Key": registration_device_raw_key},
    )
    assert response.status_code == 422


async def test_walk_in_registration_disguised_photo_rejected(
    client: AsyncClient, registration_device_raw_key: str
) -> None:
    files = [
        ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
        (
            "primary_contact_photo_file",
            ("selfie.jpg", b"this is not actually an image, just plain text bytes", "image/jpeg"),
        ),
    ]
    response = await client.post(
        "/api/v1/registrations/walk-in",
        data={"payload": json.dumps(_individual_payload())},
        files=files,
        headers={"X-Device-Key": registration_device_raw_key},
    )
    assert response.status_code == 422


# --- Role-based invitation ownership (role-based-invitation-workflow) --------
# Walk-in registration shares `create_invitation` verbatim with `POST
# /invitations` (see `invitations/tests.py`'s equivalent coverage), but as a
# separate, unauthenticated caller it gets its own explicit test evidence
# rather than relying on the shared service function alone.


async def test_walk_in_registration_snapshots_role_owned_ownership_step(
    client: AsyncClient, registration_device_raw_key: str, db_session: AsyncSession
) -> None:
    """role-based-invitation-workflow spec.md "Every New Invitation Is Owned
    by the Tenant's Default Host Role at Creation" — the walk-in channel must
    snapshot the same unconditional, role-identified `stepOrder` 0 ownership
    step as `POST /invitations` does, not a host-identified one.
    """
    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None

    data = await _create_walk_in_success(
        client, registration_device_raw_key, payload=_individual_payload()
    )
    steps = await InvitationApprovalStepRepository(db_session).list_for_invitation(
        uuid.UUID(data["id"])
    )
    step_zero = next(s for s in steps if s.step_order == 0)
    assert step_zero.approver_role_id == reception_role.id
    assert step_zero.approver_user_id is None


async def test_walk_in_registration_ignores_supplied_host_fields(
    client: AsyncClient, registration_device_raw_key: str, db_session: AsyncSession
) -> None:
    """role-based-invitation-workflow spec.md "A supplied hostId or
    hostNameOrEmail is silently ignored" — `_individual_payload()` still
    carries a `hostNameOrEmail` (an un-updated kiosk client's habit); it must
    not resolve a host on the created invitation.
    """
    data = await _create_walk_in_success(
        client, registration_device_raw_key, payload=_individual_payload()
    )
    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert invitation.host_id is None
    assert invitation.host_name_or_email is None


async def test_walk_in_registration_dispatches_tracking_notification(
    client: AsyncClient, registration_device_raw_key: str, monkeypatch
) -> None:
    """Confirms the branded tracking/creation email dispatch (template
    content itself is covered generically by
    `invitations/tests.py::test_every_notification_template_renders_without_error`)
    actually fires for the walk-in channel, exactly as it does for the other
    two invitation-creation callers.
    """
    calls: list[dict] = []
    monkeypatch.setattr(tasks.send_tracking_notification, "delay", lambda **kw: calls.append(kw))

    data = await _create_walk_in_success(
        client, registration_device_raw_key, payload=_individual_payload()
    )

    assert len(calls) == 1
    assert calls[0]["invitation_id"] == data["id"]


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
    to nothing. This is a server misconfiguration (no client credential was
    even sent), distinct from a bad device key, so it gets its own message
    and is logged at ERROR, not WARNING.
    """
    with capture_logs() as captured:
        response = await _create_walk_in(client, None, payload=_individual_payload())

    assert response.status_code == 401
    assert (
        response.json()["message"] == "Registration service is not configured for this environment"
    )

    [entry] = [e for e in captured if e["event"] == "registration_default_tenant_unconfigured"]
    assert entry["log_level"] == "error"
    assert entry["reason"] == "not_found"


async def test_walk_in_registration_missing_device_key_default_tenant_inactive_rejected(
    client: AsyncClient, tenant: Tenant, db_session: AsyncSession, monkeypatch
) -> None:
    """The default tenant slug matches, but the tenant row is inactive — a
    distinct cause from "no such tenant" (spec.md's misconfiguration
    scenario), so it must be logged with `reason="inactive"` while keeping
    the same client-facing 401 message and ERROR log level.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", tenant.slug)
    await db_session.execute(update(Tenant).where(Tenant.id == tenant.id).values(is_active=False))
    await db_session.commit()

    with capture_logs() as captured:
        response = await _create_walk_in(client, None, payload=_individual_payload())

    assert response.status_code == 401
    assert (
        response.json()["message"] == "Registration service is not configured for this environment"
    )

    [entry] = [e for e in captured if e["event"] == "registration_default_tenant_unconfigured"]
    assert entry["log_level"] == "error"
    assert entry["reason"] == "inactive"


async def test_walk_in_registration_missing_device_key_no_default_branch_rejected(
    client: AsyncClient, tenant: Tenant, branch: Branch, monkeypatch
) -> None:
    """The default tenant resolves, but no branch matches
    `registration_default_branch_code` — must still reject, not fall through
    to an unscoped branch. Same server-misconfiguration message/log level as
    the no-default-tenant case above.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")
    monkeypatch.setattr(settings, "registration_default_branch_code", "NO-SUCH-BRANCH")

    with capture_logs() as captured:
        response = await _create_walk_in(client, None, payload=_individual_payload())

    assert response.status_code == 401
    assert (
        response.json()["message"] == "Registration service is not configured for this environment"
    )

    [entry] = [e for e in captured if e["event"] == "registration_default_branch_unconfigured"]
    assert entry["log_level"] == "error"
    assert entry["branch_code"] == "NO-SUCH-BRANCH"
    assert entry["reason"] == "not_found"


async def test_walk_in_registration_missing_device_key_default_branch_inactive_rejected(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
) -> None:
    """The default tenant and default branch code both resolve, but the
    branch row is inactive — a distinct cause from "no such branch", so it
    must be logged with `reason="inactive"` while keeping the same
    client-facing 401 message and ERROR log level.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", tenant.slug)
    monkeypatch.setattr(settings, "registration_default_branch_code", branch.code)
    await db_session.execute(update(Branch).where(Branch.id == branch.id).values(is_active=False))
    await db_session.commit()

    with capture_logs() as captured:
        response = await _create_walk_in(client, None, payload=_individual_payload())

    assert response.status_code == 401
    assert (
        response.json()["message"] == "Registration service is not configured for this environment"
    )

    [entry] = [e for e in captured if e["event"] == "registration_default_branch_unconfigured"]
    assert entry["log_level"] == "error"
    assert entry["reason"] == "inactive"


async def test_walk_in_registration_invalid_device_key_rejected(
    client: AsyncClient, registration_device_raw_key: str
) -> None:
    """spec.md "Invalid device credential is reported and logged as a
    client-side anomaly" — distinct message/log level from the
    unconfigured-default-tenant/branch case above.
    """
    with capture_logs() as captured:
        response = await _create_walk_in(
            client, "definitely-not-a-provisioned-key", payload=_individual_payload()
        )

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid device credential"

    [entry] = [e for e in captured if e["event"] == "registration_device_key_invalid"]
    assert entry["log_level"] == "warning"


async def test_walk_in_registration_inactive_device_key_rejected(
    client: AsyncClient, registration_device_raw_key: str, db_session: AsyncSession
) -> None:
    await db_session.execute(update(RegistrationDeviceKey).values(is_active=False))
    await db_session.commit()

    response = await _create_walk_in(
        client, registration_device_raw_key, payload=_individual_payload()
    )
    assert response.status_code == 401


async def test_walk_in_registration_soft_deleted_branch_device_key_rejected(
    client: AsyncClient,
    registration_device_raw_key: str,
    db_session: AsyncSession,
    branch: Branch,
) -> None:
    """Regression test for the reported bug: an already-provisioned device
    key whose branch has since been soft-deleted must fail cleanly (401,
    same as an inactive branch) rather than raising an unhandled error.
    `org_structure/service.py::delete_branch` now blocks this from
    happening via the API going forward (its own branch-deletion guard
    tests cover that) — this covers the case of data that predates the
    guard, or a branch removed by any other path.
    """
    await db_session.execute(
        update(Branch).where(Branch.id == branch.id).values(deleted_at=datetime.now(UTC))
    )
    await db_session.commit()

    response = await _create_walk_in(
        client, registration_device_raw_key, payload=_individual_payload()
    )
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid device credential"


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
    # No `Company` profile is configured for this test tenant, so creation
    # resolves to `submitted` (awaiting approval), not `approved`.
    monkeypatch.setattr(tasks.send_tracking_notification, "delay", lambda **kw: calls.append(kw))

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


# --- visit-info-lookup-api: walk-in inherits the optional catalog id fields ---
# (the resolve/validate/overwrite behavior itself is `invitations.service`'s —
# already covered in `invitations/tests.py` — this only confirms the walk-in
# endpoint, which shares the identical `VisitDetailsSubmit` schema, actually
# wires it through the same way. spec.md "Walk-in registration inherits the
# same optional fields".)


async def test_walk_in_registration_with_department_id_overwrites_free_text(
    client: AsyncClient,
    registration_device_raw_key: str,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    from factories import DepartmentFactory

    department = DepartmentFactory.build(
        id=uuid.uuid4(), branch_id=branch.id, floor_id=None, code="RECEP-VI"
    )
    db_session.add(department)
    await db_session.commit()

    payload = _individual_payload()
    payload["visitDetails"]["departmentToVisit"] = "does not match the catalog row"
    payload["visitDetails"]["departmentId"] = str(department.id)

    data = await _create_walk_in_success(client, registration_device_raw_key, payload=payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert invitation.department_to_visit == department.name
    assert invitation.department_id == department.id


async def test_walk_in_registration_with_no_department_succeeds_and_leaves_it_unset(
    client: AsyncClient,
    registration_device_raw_key: str,
    db_session: AsyncSession,
) -> None:
    """allow-optional-department-at-creation spec.md "Submission with no
    department succeeds and leaves it unset" — same behavior as
    `invitations/tests.py`'s equivalent, confirmed through the walk-in
    endpoint since it shares the identical `VisitDetailsSubmit` schema.
    """
    payload = _individual_payload()
    del payload["visitDetails"]["departmentToVisit"]

    data = await _create_walk_in_success(client, registration_device_raw_key, payload=payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert invitation.department_to_visit is None
    assert invitation.department_id is None


# --- add-generic-custom-field-support: admin-authored custom fields --------
#
# specs/registrations/spec.md (delta) "Walk-in registration accepts the
# same visit-record contract as staff pre-registration" — walk-in shares
# `InvitationCreate` verbatim, so its custom-field capture is exercised
# through the same `create_invitation` path invitations/tests.py covers
# directly; these confirm that sharing actually holds through the walk-in
# endpoint too.


async def test_walk_in_registration_captures_invitation_level_custom_field(
    client: AsyncClient,
    user: User,
    registration_device_raw_key: str,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    admin_token = await _login(client, user.email)
    field_id = await _create_and_publish_custom_field(
        client, admin_token, branch, step_key="visit_details", key="cost_center"
    )

    payload = _individual_payload()
    payload["customFields"] = [{"fieldId": field_id, "value": "CC-42"}]
    data = await _create_walk_in_success(client, registration_device_raw_key, payload=payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert invitation.custom_field_values == {field_id: "CC-42"}


async def test_walk_in_registration_captures_primary_contact_custom_field(
    client: AsyncClient,
    user: User,
    registration_device_raw_key: str,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    admin_token = await _login(client, user.email)
    field_id = await _create_and_publish_custom_field(
        client, admin_token, branch, step_key="visitor_info", key="employee_id"
    )

    payload = _individual_payload()
    # The primary contact's Visitor Info-step answers are sourced from the
    # invitation-level `customFields` array — see
    # `InvitationPrimaryContactCreate`'s docstring in `invitations/schemas.py`.
    payload["customFields"] = [{"fieldId": field_id, "value": "E-1001"}]
    data = await _create_walk_in_success(client, registration_device_raw_key, payload=payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert invitation.primary_contact_custom_field_values == {field_id: "E-1001"}


async def test_walk_in_registration_custom_field_unresolvable_id_rejected(
    client: AsyncClient, registration_device_raw_key: str
) -> None:
    payload = _individual_payload()
    payload["customFields"] = [{"fieldId": str(uuid.uuid4()), "value": "x"}]
    response = await _create_walk_in(client, registration_device_raw_key, payload=payload)
    assert response.status_code == 422


async def test_walk_in_registration_static_text_field_needs_no_submitted_value(
    client: AsyncClient,
    user: User,
    registration_device_raw_key: str,
    branch: Branch,
) -> None:
    """add-static-text-field-and-unlock-toggle: confirms the walk-in path
    resolves the exact same effective form `create_invitation` does (both
    call the identical `resolve_effective_form`) — a `static_text` field
    collects no answer, so a walk-in submission with no value for its key
    still succeeds, same as `invitations/tests.py::
    test_create_invitation_static_text_field_needs_no_submitted_value`."""
    admin_token = await _login(client, user.email)
    await _create_and_publish_custom_field(
        client,
        admin_token,
        branch,
        step_key="visit_details",
        key="visit_notice",
        field_type="static_text",
        help_text="Please arrive 10 minutes early.",
    )

    data = await _create_walk_in_success(
        client, registration_device_raw_key, payload=_individual_payload()
    )
    assert data["trackingId"].startswith("INV-")


# --- fix-registration-host-role-crash: default-host-role failure mode ------


async def test_walk_in_registration_missing_default_host_role_fails_as_server_misconfiguration(
    client: AsyncClient,
    registration_device_raw_key: str,
    tenant: Tenant,
    db_session: AsyncSession,
) -> None:
    """Confirms the shared `create_invitation` path
    (org_structure/service.py::get_default_host_role) fails identically for
    the walk-in entry point as it does for staff pre-registration — see
    `invitations/tests.py::test_create_invitation_missing_default_host_role_fails_as_server_misconfiguration`.
    Bypasses `auth/service.py`'s rename/delete protection for the standard
    "reception" role directly at the repository layer (this state isn't
    reachable via the walk-in registration API itself — see design.md).
    """
    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None
    await RoleRepository(db_session).soft_delete(reception_role)
    await db_session.commit()

    # `capture_logs()` disables every configured processor by default
    # (including `structlog.contextvars.merge_contextvars`), so a field
    # bound only via contextvars (`tenant_id`, here) has to have that
    # processor passed back in explicitly to show up in a captured entry.
    with capture_logs(processors=(structlog.contextvars.merge_contextvars,)) as captured:
        response = await _create_walk_in(
            client, registration_device_raw_key, payload=_individual_payload()
        )

    assert response.status_code == 500

    [entry] = [e for e in captured if e["event"] == "default_host_role_not_seeded"]
    assert entry["log_level"] == "error"
    assert entry["tenant_id"] == str(tenant.id)

    # Same rollback-on-exit stand-in as `invitations/tests.py`'s counterpart
    # test and `org_structure/tests.py`'s
    # `test_provision_branch_rolls_back_partial_tree_on_mid_transaction_conflict`
    # — the test client's `get_tenant_db` override hands every request the
    # same bare `db_session`, with no `async with` around it to roll back
    # automatically the way production's `tenant_session_scope` would.
    await db_session.rollback()
    for model in (Invitation, InvitationVisitor, InvitationVehicle, InvitationApprovalStep):
        count = await db_session.scalar(select(func.count()).select_from(model))
        assert count == 0, f"{model.__name__} row(s) leaked from a failed default-host-role lookup"


# --- fix-registration-host-role-crash: branch/form-config divergence -------


async def test_walk_in_registration_branch_config_mismatch_logs_enforced_branch(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    user: User,
    registration_device_raw_key: str,
    db_session: AsyncSession,
) -> None:
    """specs/registrations/spec.md (delta) "A Configuration Mismatch Is
    Logged With the Enforced Branch" — `branch` (the device credential's
    own branch) publishes a required consent that a second branch
    (`other_branch`) never gets configured. Submitting the default payload
    (whose consents only satisfy `other_branch`'s unconfigured form) against
    the device-credential-resolved branch must be rejected, and the
    rejection's log must identify `branch`'s id — the server-resolved
    branch actually enforced — regardless of what any client separately
    assumed or rendered (there is no branch field on the wire to compare
    against, per design.md).
    """
    other_branch = BranchFactory.build(id=uuid.uuid4(), name="Other Branch", code="OTHER")
    db_session.add(other_branch)
    await db_session.commit()

    admin_token = await _login(client, user.email)
    await _create_and_publish_custom_field(
        client,
        admin_token,
        branch,
        step_key="consent_agreement",
        key="confidentiality_agreement",
        field_type="toggle_switch",
        is_required=True,
    )

    with capture_logs() as captured:
        response = await _create_walk_in(
            client, registration_device_raw_key, payload=_individual_payload()
        )

    assert response.status_code == 422

    matching_entries = [
        e for e in captured if e["event"] == "registration_form_config_validation_failed"
    ]
    assert matching_entries, "expected a form-config-validation-failed log entry"
    entry = matching_entries[-1]
    assert entry["log_level"] == "warning"
    assert entry["branch_id"] == str(branch.id)
    assert entry["branch_id"] != str(other_branch.id)
    assert entry["check"] == "consent_key"


# --- add-repeatable-field-groups: group instance-count enforcement ----------


async def _update_and_publish_group_range(
    client: AsyncClient,
    admin_token: str,
    branch: Branch,
    *,
    step_key: str,
    group_key: str,
    min_instances: int | None = None,
    max_instances: int | None = None,
) -> None:
    """Same pattern as `invitations/tests.py`'s helper of the same name,
    duplicated here for the reason `_create_and_publish_custom_field` above
    already documents."""
    headers = {"Authorization": f"Bearer {admin_token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == step_key)
    group = next(g for g in step["groups"] if g["key"] == group_key)

    body: dict = {}
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


async def test_walk_in_vehicle_count_below_configured_minimum_rejected(
    client: AsyncClient,
    branch: Branch,
    user: User,
    registration_device_raw_key: str,
) -> None:
    admin_token = await _login(client, user.email)
    await _update_and_publish_group_range(
        client, admin_token, branch, step_key="vehicle_info", group_key="vehicles", min_instances=1
    )
    payload = _individual_payload()
    payload["vehicles"] = []
    response = await _create_walk_in(client, registration_device_raw_key, payload=payload)
    assert response.status_code == 422


async def test_walk_in_group_instance_count_mismatch_is_logged_with_enforced_branch(
    client: AsyncClient,
    branch: Branch,
    user: User,
    registration_device_raw_key: str,
    db_session: AsyncSession,
) -> None:
    """specs/registrations/spec.md (delta) "A Configuration Mismatch Is
    Logged With the Enforced Branch" (add-repeatable-field-groups) — a
    group instance-count rejection is logged the same way a required-field/
    custom-field/consent-key mismatch already is, identifying the
    server-resolved branch.
    """
    admin_token = await _login(client, user.email)
    await _update_and_publish_group_range(
        client, admin_token, branch, step_key="vehicle_info", group_key="vehicles", max_instances=1
    )
    payload = _individual_payload()
    payload["vehicles"] = [
        {"vehicleType": "2_wheeler", "licensePlate": "KA-01-AB-1234"},
        {"vehicleType": "4_wheeler", "licensePlate": "KA-05-CD-5678"},
    ]

    with capture_logs() as captured:
        response = await _create_walk_in(client, registration_device_raw_key, payload=payload)

    assert response.status_code == 422
    matching_entries = [
        e for e in captured if e["event"] == "registration_form_config_validation_failed"
    ]
    assert matching_entries, "expected a form-config-validation-failed log entry"
    entry = matching_entries[-1]
    assert entry["log_level"] == "warning"
    assert entry["branch_id"] == str(branch.id)
    assert entry["check"] == "group_instance_count"


# --- add-group-field-file-upload: a custom group's own file_upload field ----


async def _create_and_publish_additional_visitors_group(
    client: AsyncClient, admin_token: str, branch: Branch
) -> tuple[str, str, str]:
    """Same pattern as `invitations/tests.py::_create_and_publish_additional_visitors_group`,
    duplicated here for the reason `_create_and_publish_custom_field` above
    already documents: a repeatable "Additional Visitors" group on Visitor
    Info with a required `name` field and its own `file_upload`-typed field
    (`id_upload`). Returns `(group_id, name_field_id, id_upload_field_id)`
    (restructure-walkin-payload-by-field-id) — the caller must reference
    these, never the group's/fields' `key`, in `payload.groups` and the
    `groupFieldFiles[...]` multipart part name.
    """
    headers = {"Authorization": f"Bearer {admin_token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == "visitor_info")

    group_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/groups",
        json={"key": "additional_visitors", "name": "Additional Visitors", "isRepeatable": True},
        headers=headers,
    )
    assert group_response.status_code == 201, group_response.text
    group_id = group_response.json()["data"]["id"]

    field_ids: dict[str, str] = {}
    for field_key, field_type, is_required in (
        ("name", "text", True),
        ("id_upload", "file_upload", False),
    ):
        field_response = await client.post(
            f"/api/v1/form-builder/steps/{step['id']}/fields",
            json={
                "key": field_key,
                "label": field_key.replace("_", " ").title(),
                "fieldType": field_type,
                "isRequired": is_required,
                "groupId": group_id,
            },
            headers=headers,
        )
        assert field_response.status_code == 201, field_response.text
        field_ids[field_key] = field_response.json()["data"]["id"]

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])
    return group_id, field_ids["name"], field_ids["id_upload"]


async def test_walk_in_registration_group_file_upload_stored_and_surfaced_on_read(
    client: AsyncClient, user: User, branch: Branch, registration_device_raw_key: str
) -> None:
    """A custom Visitor Info group's own `file_upload`-typed field is
    accepted on `POST /registrations/walk-in` via the same
    `groupFieldFiles[<groupKey>]` multipart convention `POST /invitations`
    documents (order-matched to `groupValues[<groupKey>]` instances) —
    closing the gap where walk-in registration declared the same repeatable
    -group contract but never parsed or forwarded the multipart part.
    """
    admin_token = await _login(client, user.email)
    (
        group_id,
        name_field_id,
        _id_upload_field_id,
    ) = await _create_and_publish_additional_visitors_group(client, admin_token, branch)

    payload = _individual_payload()
    payload["groups"] = [
        {
            "groupId": group_id,
            "instances": [
                [{"fieldId": name_field_id, "value": "Extra One"}],
                [{"fieldId": name_field_id, "value": "Extra Two"}],
            ],
        }
    ]
    response = await client.post(
        "/api/v1/registrations/walk-in",
        data={"payload": json.dumps(payload)},
        files=[
            ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
            ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
            (f"groupFieldFiles[{group_id}]", ("extra1.jpg", _jpeg_bytes(), "image/jpeg")),
            (f"groupFieldFiles[{group_id}]", ("extra2.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
        headers={"X-Device-Key": registration_device_raw_key},
    )
    assert response.status_code == 201, response.text
    invitation_id = response.json()["data"]["id"]

    admin_headers = {"Authorization": f"Bearer {admin_token}", "X-Branch-ID": str(branch.id)}
    detail_response = await client.get(
        f"/api/v1/invitations/{invitation_id}", headers=admin_headers
    )
    assert detail_response.status_code == 200, detail_response.text
    visitors = sorted(detail_response.json()["data"]["visitors"], key=lambda v: v["fullName"])
    assert [v["fullName"] for v in visitors] == ["Extra One", "Extra Two"]
    for visitor_out in visitors:
        assert visitor_out["idProofUrl"] is not None
