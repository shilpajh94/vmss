"""Reschedule, extend and edit, including the point of contact."""

import asyncio
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    ApprovalWorkflowRuleFactory,
    RoleFactory,
    UserFactory,
    VisitorCategoryFactory,
)
from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.auth.models import AuditLog, User
from vmss_api.core.sms import SmsTemplate
from vmss_api.core.whatsapp import WhatsAppTemplate
from vmss_api.invitations import notifications, tasks
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.invitations.tests.helpers import (
    _branch_scoped_invitation_editor,
    _branch_scoped_invitation_viewer,
    _build_invitation,
    _create_and_publish_custom_field,
    _create_invitation_success,
    _fake_tenant_session_scope,
    _FakeInvitation,
    _individual_payload,
    _login,
    _make_host,
)
from vmss_api.notifications import service as notifications_service
from vmss_api.org_structure.models import Branch, Department
from vmss_api.tenant.models import Tenant
from vmss_api.visit_info.models import VisitDuration, VisitPurpose

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
