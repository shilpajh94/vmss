"""Creating invitations: payload validation, groups, uploads, returning contacts."""

import json
import uuid
from collections.abc import Callable

import pytest
import starlette.datastructures as starlette_datastructures
from httpx import AsyncClient
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    CompanyFactory,
    RoleFactory,
    UserFactory,
    VisitorCategoryFactory,
    ensure_default_location,
    with_default_location,
)
from vmss_api.auth.models import Permission, User, UserBranchRole
from vmss_api.core.config import settings
from vmss_api.core.security import hash_password
from vmss_api.invitations import creation as invitations_creation
from vmss_api.invitations import qr_token, tasks
from vmss_api.invitations.models import (
    InvitationQRCode,
)
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.invitations.tests.helpers import (
    _DEFAULT_VISITOR_CATEGORY_ID,
    _add_consent,
    _answers,
    _build_invitation,
    _create_and_publish_additional_visitors_group,
    _create_and_publish_custom_field,
    _create_and_publish_custom_group,
    _create_invitation,
    _create_invitation_success,
    _custom_field_value,
    _default_consent_field_id,
    _group_entry,
    _group_payload,
    _individual_payload,
    _jpeg_bytes,
    _login,
    _phone_only_primary_contact,
    _record_live_consent_field_ids,
    _set_consent_accepted,
    _update_and_publish_field_options,
    _update_and_publish_group_range,
)
from vmss_api.org_structure.models import Branch
from vmss_api.platform.models import TenantUserIndex
from vmss_api.tenant.models import Tenant

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
    """Neither the `X-Branch-ID` header nor any `branchId` in the payload is
    supplied. Since `8ec5b06` made `visitDetails.branchId` mandatory, the
    payload's own validation rejects this (422) before the router's
    no-branch-context 400 can run.
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
    assert response.status_code == 422
    assert "branchId" in response.json()["message"]


async def test_create_invitation_branch_id_in_payload_used_when_header_omitted(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """`branchId` in the payload resolves the branch when `X-Branch-ID` is
    omitted entirely — the header is not the only way to identify one.
    """
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["branchId"] = str(branch.id)
    location = await ensure_default_location(branch.id)
    assert location is not None
    payload["visitDetails"]["buildingId"] = location[1]
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
    original_save = invitations_creation.storage_save

    async def _spy_save(tenant_id, category, content, content_type):
        storage_calls.append(content_type)
        return await original_save(tenant_id, category, content, content_type)

    monkeypatch.setattr(invitations_creation, "storage_save", _spy_save)

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
        data={"payload": json.dumps(await with_default_location(_individual_payload(), branch.id))},
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
        data={"payload": json.dumps(await with_default_location(_group_payload(), branch.id))},
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


async def test_create_group_invitation_with_empty_visitor_list_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _group_payload()
    payload["visitors"] = []
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422
    assert "at least one visitor" in response.json()["message"]


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


async def test_create_invitation_unknown_building_stores_no_files(
    client: AsyncClient, user: User, branch: Branch, monkeypatch
) -> None:
    """A 422 for a bad building must not leave orphaned uploads behind:
    location checks run before the first storage write."""
    saved: list[tuple] = []

    async def _recording_save(*args, **kwargs):
        saved.append(args)
        return "never-used"

    monkeypatch.setattr(invitations_creation, "storage_save", _recording_save)
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["branchId"] = str(branch.id)
    payload["visitDetails"]["buildingId"] = str(uuid.uuid4())

    response = await _create_invitation(client, token, branch, payload=payload)

    assert response.status_code == 422, response.text
    assert "building" in response.json()["message"].lower()
    assert saved == []


async def test_create_invitation_oversized_body_rejected_before_processing(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """api-compliance-hardening "Multipart Uploads Are Bounded in Total Size
    and File Count": an oversized body is a 413, and nothing is created."""
    monkeypatch.setattr(settings, "max_request_body_bytes", 1024)
    token = await _login(client, user.email)
    response = await _create_invitation(client, token, branch, payload=_individual_payload())
    assert response.status_code == 413, response.text
    assert response.json()["success"] is False
    assert await InvitationRepository(db_session).list() == []


async def test_create_invitation_too_many_file_parts_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "max_upload_files", 2)
    token = await _login(client, user.email)
    response = await _create_invitation(
        client, token, branch, payload=_group_payload(), visitor_file_count=2
    )
    assert response.status_code == 413, response.text
    assert await InvitationRepository(db_session).list() == []


async def test_create_invitation_within_upload_limits_unaffected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    await _create_invitation_success(client, token, branch, payload=_individual_payload())


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
    assert _answers(body["groups"]) == [
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
        data={"payload": json.dumps(await with_default_location(payload, branch.id))},
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
        data={"payload": json.dumps(await with_default_location(payload, branch.id))},
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
        data={"payload": json.dumps(await with_default_location(payload, branch.id))},
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
        data={"payload": json.dumps(await with_default_location(payload, branch.id))},
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
        data={"payload": json.dumps(await with_default_location(payload, branch.id))},
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
