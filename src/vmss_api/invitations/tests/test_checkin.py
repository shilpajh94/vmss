"""Check-in/out by tracking ID, QR and SMS code; badges; watchlist override."""

import asyncio
import io
import json
import re
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    BuildingFactory,
    CompanyFactory,
    DepartmentFactory,
    FloorFactory,
    InvitationVehicleFactory,
    InvitationVisitorFactory,
    RoleFactory,
    UserFactory,
)
from vmss_api.auth.models import AuditLog, User
from vmss_api.auth.rbac_catalog import seed_default_roles
from vmss_api.auth.repository import RoleRepository
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.core.sms import SmsTemplate
from vmss_api.core.timezones import display_name as display_tz_name
from vmss_api.invitations import checkin as invitations_checkin
from vmss_api.invitations import common as invitations_common
from vmss_api.invitations import notifications, qr_token, tasks
from vmss_api.invitations import service as invitations_service
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.invitations.tests.helpers import (
    _KOLKATA,
    _approved_invitation,
    _branch_scoped_invitation_approver,
    _branch_scoped_invitation_viewer,
    _build_invitation,
    _checked_in_invitation,
    _code_device,
    _create_and_publish_custom_field,
    _create_invitation_success,
    _custom_field_value,
    _fake_tenant_session_scope,
    _FakeInvitation,
    _individual_payload,
    _login,
    _make_role_holder,
    _reception_holder,
    _sms_invitation,
)
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant

# --- add-public-checkin-endpoint: PATCH /api/v2/invitations/{trackingId}/check-in --


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


# --- add-sms-numeric-checkin-code ---------------------------------------------


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
    monkeypatch.setattr(invitations_common.secrets, "randbelow", lambda _n: next(draws))
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
        # Legacy web-saved offset labels resolve to the offset, not UTC.
        (SimpleNamespace(default_timezone="GMT+05:30"), "UTC", "+05:30"),
        (SimpleNamespace(default_timezone="bogus"), "UTC-04:00", "-04:00"),
    ],
)
def test_visit_timezone_precedence(company: Any, tenant_tz: str, expected: str) -> None:
    tz = invitations_service._visit_timezone(company, SimpleNamespace(timezone=tenant_tz))  # type: ignore[arg-type]
    assert display_tz_name(tz) == expected


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

    monkeypatch.setattr(invitations_checkin, "datetime", _FrozenDatetime)
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
        httpx,  # the module `core/whatsapp.py` calls through
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
    assert display_tz_name(
        await invitations_service.resolve_visit_timezone(db_session, tenant)
    ) == (_KOLKATA)

    other_schema = "tenant_other_test_visit_timezone"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        tz = await invitations_service.resolve_visit_timezone(other_session, tenant)
    assert display_tz_name(tz) == "UTC"


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


# --- ID verification at check-in (optional-id-verification-for-badge-print) ------


async def _id_gate_tenant(db_session: AsyncSession, tenant: Tenant, *, requires: bool) -> None:
    tenant.badge_print_flow_enabled = True
    tenant.badge_print_requires_id_verification = requires
    await db_session.commit()


async def test_qr_check_in_requires_verified_id_when_toggle_on(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    await _id_gate_tenant(db_session, tenant, requires=True)
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)

    blocked = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert blocked.status_code == 409
    assert "ID not verified" in blocked.json()["message"]

    invitation.id_verified_at = datetime.now(UTC)
    await db_session.commit()
    allowed = await client.patch(f"/api/v2/invitations/qr/{token}/check-in")
    assert allowed.status_code == 200


async def test_code_check_in_requires_verified_id_when_toggle_on(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    fake_lockout_redis,
) -> None:
    await _id_gate_tenant(db_session, tenant, requires=True)
    invitation = _sms_invitation(db_session, branch.id, "33334444")
    db_session.add(invitation)
    await db_session.commit()
    body = {"code": "33334444"}

    blocked = await client.patch("/api/v2/invitations/code/check-in", json=body)
    assert blocked.status_code == 409
    assert "ID not verified" in blocked.json()["message"]

    invitation.id_verified_at = datetime.now(UTC)
    await db_session.commit()
    assert (await client.patch("/api/v2/invitations/code/check-in", json=body)).status_code == 200


async def test_qr_check_in_has_no_id_gate_when_toggle_off(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    await _id_gate_tenant(db_session, tenant, requires=False)
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    token = qr_token.encrypt_invitation_token(invitation.id)
    assert (await client.patch(f"/api/v2/invitations/qr/{token}/check-in")).status_code == 200
