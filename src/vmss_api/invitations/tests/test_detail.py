"""GET /invitations/{id}."""

import uuid
from collections.abc import Callable

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    BuildingFactory,
    DepartmentFactory,
    DeviceFactory,
    FloorFactory,
    InvitationVisitorFactory,
    UserFactory,
)
from vmss_api.auth.models import User
from vmss_api.core import storage
from vmss_api.invitations.tests.helpers import (
    _branch_scoped_invitation_and_documents_viewer,
    _branch_scoped_invitation_viewer,
    _build_invitation,
    _jpeg_bytes,
    _login,
)
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant

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


async def test_get_invitation_detail_surfaces_check_in_and_out_devices(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """invitations delta "Invitation Detail Surfaces the Check-In and
    Check-Out Devices"."""
    device = DeviceFactory.build(id=uuid.uuid4(), branch_id=branch.id, name="Lobby Kiosk")
    db_session.add(device)
    await db_session.flush()
    checked_in = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        check_in_status="checked_in",
        check_in_device_id=device.id,
    )
    not_yet = _build_invitation(db_session, branch.id, status="approved")
    db_session.add_all([checked_in, not_yet])
    await db_session.commit()
    device_id, checked_in_id, not_yet_id = device.device_id, checked_in.id, not_yet.id

    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    body = (await client.get(f"/api/v1/invitations/{checked_in_id}", headers=headers)).json()
    assert body["data"]["checkInDevice"]["deviceId"] == device_id
    assert body["data"]["checkOutDevice"] is None

    body = (await client.get(f"/api/v1/invitations/{not_yet_id}", headers=headers)).json()
    assert body["data"]["checkInDevice"] is None
    assert body["data"]["checkOutDevice"] is None


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
    # Free text with no catalog id is surfaced by name only (0659cda).
    assert data["department"] == {"id": None, "name": "Finance", "code": None}
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
    co_visitor = InvitationVisitorFactory.build(
        id=uuid.uuid4(), id_proof_storage_key="vmss:tenant:invitations/id_proofs:visitor.jpg"
    )
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
    co_visitor = InvitationVisitorFactory.build(
        id=uuid.uuid4(), id_proof_storage_key="vmss:tenant:invitations/id_proofs:visitor.jpg"
    )
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
