"""Automatic check-out and archived no-shows."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    CompanyFactory,
    InvitationFactory,
)
from vmss_api.auth.models import User
from vmss_api.core.database import AsyncSessionLocal
from vmss_api.invitations import export as invitation_export
from vmss_api.invitations import notifications, qr_token, tasks
from vmss_api.invitations.schemas import (
    InvitationExportDateRange,
)
from vmss_api.invitations.tests.helpers import (
    _approved_invitation,
    _archived_invitation,
    _base_header,
    _branch_scoped_user_with,
    _build_invitation,
    _capture_reschedule_dispatch,
    _checked_in_invitation,
    _csv_headers,
    _csv_rows,
    _edit,
    _expired,
    _later,
    _login,
    _names,
    _noop_async,
    _reschedule,
    _service_export,
    _sweep,
    _sweep_audits,
)
from vmss_api.notifications import service as notifications_service
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant

# --- auto-checkout-and-archive-no-shows: visit-lifecycle sweep ---------------


async def test_sweep_auto_checks_out_expired_check_ins(
    branch: Branch, db_session: AsyncSession
) -> None:
    """visit-lifecycle-sweep "Expired Check-Ins Are Checked Out Automatically"
    — including a legacy row where only `status` says `checked_in`, and an
    extended pass that isn't due yet.
    """
    expired = _checked_in_invitation(db_session, branch.id)
    expired.expires_at = _expired()
    extended = _checked_in_invitation(db_session, branch.id)
    extended.expires_at = _later()
    legacy = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        check_in_status="unused",
        approved_at=datetime.now(UTC),
        checked_in_at=datetime.now(UTC),
        expires_at=_expired(),
    )
    db_session.add(legacy)
    await db_session.commit()

    await _sweep(db_session)

    for invitation in (expired, legacy):
        await db_session.refresh(invitation)
        assert invitation.status == "checked_out"
        assert invitation.check_in_status == "checked_out"
        assert invitation.checked_out_at == invitation.expires_at
        assert invitation.checked_out_by_user_id is None
        assert invitation.checked_out_automatically is True
    await db_session.refresh(extended)
    assert extended.status == "checked_in"
    assert extended.checked_out_automatically is False


async def test_sweep_archives_only_expired_approved_no_shows(
    branch: Branch, db_session: AsyncSession
) -> None:
    """visit-lifecycle-sweep "Approved No-Shows Are Archived the Day After the
    Visit" — pending, upcoming, visited and denied rows are left alone.
    """
    no_show = _approved_invitation(db_session, branch.id, expires_at=_expired())
    upcoming = _approved_invitation(db_session, branch.id, expires_at=_later())
    pending = _build_invitation(db_session, branch.id, status="submitted", expires_at=_expired())
    visited = _build_invitation(
        db_session,
        branch.id,
        status="checked_out",
        check_in_status="checked_out",
        expires_at=_expired(),
    )
    denied = _build_invitation(db_session, branch.id, status="denied", expires_at=_expired())
    db_session.add_all([no_show, upcoming, pending, visited, denied])
    await db_session.commit()

    before = datetime.now(UTC)
    await _sweep(db_session)

    await db_session.refresh(no_show)
    assert no_show.status == "archived"
    assert no_show.archived_at is not None and no_show.archived_at >= before
    assert no_show.check_in_status == "unused"
    for invitation, expected in (
        (upcoming, "approved"),
        (pending, "submitted"),
        (visited, "checked_out"),
        (denied, "denied"),
    ):
        await db_session.refresh(invitation)
        assert invitation.status == expected
        assert invitation.archived_at is None


async def test_sweep_audits_once_and_notifies_nobody(
    branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """visit-lifecycle-sweep "The Sweep Is Silent, Audited, and Safe to Repeat"."""
    checked_in = _checked_in_invitation(db_session, branch.id)
    checked_in.expires_at = _expired()
    no_show = _approved_invitation(db_session, branch.id, expires_at=_expired())
    db_session.add(no_show)
    await db_session.commit()
    checked_in_id, no_show_id = checked_in.id, no_show.id

    pushes: list[dict] = []

    async def _fake_notify_user(**kwargs):
        pushes.append(kwargs)

    sends: list[dict] = []

    async def _fake_send(**kwargs):
        sends.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)
    monkeypatch.setattr(notifications.email_sender, "send", _fake_send)
    monkeypatch.setattr(notifications.sms_sender, "send", _fake_send)

    assert await _sweep(db_session) == (1, 1)
    assert await _sweep(db_session) == (0, 0)

    [checkout_audit] = await _sweep_audits(db_session, checked_in_id)
    assert checkout_audit.action == "invitation_auto_checked_out"
    assert checkout_audit.actor_user_id is None
    assert checkout_audit.entity_type == "invitation"
    [archive_audit] = await _sweep_audits(db_session, no_show_id)
    assert archive_audit.action == "invitation_archived"
    assert archive_audit.actor_user_id is None
    assert pushes == []
    assert sends == []


async def test_sweep_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, branch: Branch, db_session: AsyncSession
) -> None:
    no_show = _approved_invitation(db_session, branch.id, expires_at=_expired())
    db_session.add(no_show)
    await db_session.commit()

    other_schema = "tenant_other_test_visit_lifecycle_sweep"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        assert await _sweep(other_session) == (0, 0)

    await db_session.refresh(no_show)
    assert no_show.status == "approved"


async def test_dispatch_visit_lifecycle_sweep_survives_one_tenant_failing(
    monkeypatch, tenant: Tenant, make_tenant_schema
) -> None:
    """background-jobs "One tenant's failure does not block another"."""
    second_schema = "tenant_other_test_sweep_dispatch"
    await make_tenant_schema(second_schema)
    second_tenant = Tenant(
        id=uuid.uuid4(),
        name="Second Co",
        slug=f"second-{uuid.uuid4().hex[:8]}",
        schema_name=second_schema,
    )
    async with AsyncSessionLocal() as global_session:
        global_session.add(second_tenant)
        await global_session.commit()

    enqueued: list[str] = []

    def _fake_delay(*, tenant_id: str, tenant_schema: str) -> None:
        if tenant_id == str(tenant.id):
            raise RuntimeError("broker hiccup")
        enqueued.append(tenant_id)

    monkeypatch.setattr(tasks.sweep_tenant_visit_lifecycle, "delay", _fake_delay)

    await tasks._dispatch_visit_lifecycle_sweep()

    assert str(second_tenant.id) in enqueued
    assert str(tenant.id) not in enqueued


async def test_manual_check_out_after_auto_check_out_cycle_clears_flag(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """An auto-checked-out visit whose pass is extended can be re-entered,
    and a later manual check-out is not reported as automatic.
    """
    invitation = _approved_invitation(
        db_session,
        branch.id,
        status="checked_out",
        check_in_status="checked_out",
        checked_out_at=_expired(),
        checked_out_automatically=True,
        expires_at=_later(),
    )
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    monkeypatch.setattr(notifications_service, "notify_user", _noop_async)

    qr = qr_token.encrypt_invitation_token(invitation_id)
    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-in")
    assert response.status_code == 200, response.text
    # Production gives each request a fresh session; the test client shares
    # this one, so drop the row check-in updated before the next request.
    db_session.expire(invitation)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/check-out",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["checkedOutAutomatically"] is False

    await db_session.refresh(invitation)
    assert invitation.checked_out_automatically is False


async def test_qr_check_out_after_auto_check_out_is_rejected(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """invitations "Check-out after the sweep already closed the visit is rejected"."""
    invitation = _checked_in_invitation(db_session, branch.id)
    invitation.expires_at = _expired()
    await db_session.commit()
    await _sweep(db_session)
    await db_session.refresh(invitation)
    checked_out_at = invitation.checked_out_at

    qr = qr_token.encrypt_invitation_token(invitation.id)
    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-out")
    assert response.status_code == 409, response.text

    await db_session.refresh(invitation)
    assert invitation.checked_out_at == checked_out_at
    assert invitation.checked_out_automatically is True


async def test_archived_invitation_check_in_rejected_on_every_path(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """invitations "An Archived Invitation Does Not Admit the Visitor"."""
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()

    qr = qr_token.encrypt_invitation_token(invitation.id)
    for url in (
        f"/api/v2/invitations/qr/{qr}/check-in",
        f"/api/v2/invitations/{invitation.tracking_id}/check-in",
    ):
        response = await client.patch(url)
        assert response.status_code == 409, response.text
        assert "archived" in response.text

    await db_session.refresh(invitation)
    assert invitation.status == "archived"
    assert invitation.check_in_status == "unused"


async def test_archived_invitation_expiry_cannot_be_extended(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id, expires_at = invitation.id, invitation.expires_at

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/extend",
        json={"expiresAt": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409, response.text

    await db_session.refresh(invitation)
    assert invitation.expires_at == expires_at


async def test_reschedule_archived_invitation_returns_it_to_approval(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """invitations "An Archived Invitation Is Rescheduled Back Into Approval"."""
    archived_at = datetime.now(UTC) - timedelta(hours=2)
    invitation = _archived_invitation(db_session, branch.id, archived_at=archived_at)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id, old_date = invitation.id, invitation.preferred_visit_date
    email_calls, _ = _capture_reschedule_dispatch(monkeypatch)
    new_date = datetime.now(UTC).date() + timedelta(days=3)

    token = await _login(client, user.email)
    response = await _reschedule(client, token, invitation_id, new_date)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "submitted"
    assert data["approvedAt"] is None
    assert data["archivedAt"] is not None

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"
    assert invitation.approved_at is None
    assert invitation.archived_at == archived_at
    assert invitation.preferred_visit_date == new_date
    assert invitation.previous_preferred_visit_date == old_date
    assert invitation.reschedule_count >= 1
    assert invitation.expires_at == datetime.combine(new_date, time(23, 59, 59), tzinfo=UTC)
    assert [c["invitation_id"] for c in email_calls] == [str(invitation_id)]


async def test_reschedule_archived_stays_submitted_when_company_auto_approves(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    db_session.add(
        CompanyFactory.build(
            id=uuid.uuid4(), auto_approve_pre_registered_visitors=True, default_timezone="UTC"
        )
    )
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    _capture_reschedule_dispatch(monkeypatch)

    token = await _login(client, user.email)
    response = await _reschedule(client, token, invitation_id, datetime.now(UTC).date())
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "submitted"


async def test_reschedule_archived_to_past_date_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    email_calls, push_calls = _capture_reschedule_dispatch(monkeypatch)

    token = await _login(client, user.email)
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    response = await _reschedule(client, token, invitation_id, yesterday)
    assert response.status_code == 422, response.text

    await db_session.refresh(invitation)
    assert invitation.status == "archived"
    assert email_calls == [] and push_calls == []


async def test_reschedule_archived_requires_permission(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    _capture_reschedule_dispatch(monkeypatch)
    viewer = await _branch_scoped_user_with(
        db_session, tenant, branch.id, ("invitations:view", "invitations:view-all")
    )

    token = issue_token(viewer)
    response = await _reschedule(client, token, invitation_id, datetime.now(UTC).date())
    assert response.status_code == 403, response.text

    await db_session.refresh(invitation)
    assert invitation.status == "archived"


async def test_rescheduled_archived_invitation_reapproval_restores_original_pass(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """Approved → never came → archived by the sweep → rescheduled → approved
    again: the approval email carries the original QR token, which now admits.
    """
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="submitted",
        preferred_visit_date=None,
        expires_at=_expired(),
    )
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    approval_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )
    _capture_reschedule_dispatch(monkeypatch)
    token = await _login(client, user.email)
    approve_url = f"/api/v1/invitations/{invitation_id}/approve"
    auth = {"Authorization": f"Bearer {token}"}

    assert (await client.post(approve_url, headers=auth)).status_code == 200
    await _sweep(db_session)
    await db_session.refresh(invitation)
    assert invitation.status == "archived"

    response = await _reschedule(client, token, invitation_id, datetime.now(UTC).date())
    assert response.status_code == 200, response.text
    qr = approval_calls[0]["qr_token"]
    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-in")
    assert response.status_code == 400, response.text  # submitted again: not admitted

    assert (await client.post(approve_url, headers=auth)).status_code == 200
    assert [c["qr_token"] for c in approval_calls] == [qr, qr]
    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-in")
    assert response.status_code == 200, response.text


async def test_edit_archived_invitation_without_date_change_stays_archived(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: None)
    monkeypatch.setattr(notifications_service, "notify_user", _noop_async)

    token = await _login(client, user.email)
    response = await _edit(client, token, invitation_id, {"additionalNotes": "Call ahead"})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "archived"

    await db_session.refresh(invitation)
    assert invitation.status == "archived"
    assert invitation.additional_notes == "Call ahead"


async def test_edit_archived_invitation_date_change_returns_it_to_approval(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: None)
    monkeypatch.setattr(notifications_service, "notify_user", _noop_async)
    new_date = datetime.now(UTC).date() + timedelta(days=1)

    token = await _login(client, user.email)
    response = await _edit(
        client, token, invitation_id, {"preferredVisitDate": new_date.isoformat()}
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "submitted"

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"
    assert invitation.approved_at is None
    assert invitation.preferred_visit_date == new_date
    assert invitation.expires_at == datetime.combine(new_date, time(23, 59, 59), tzinfo=UTC)


async def test_edit_archived_invitation_to_past_date_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    invitation = _archived_invitation(
        db_session, branch.id, preferred_visit_date=datetime.now(UTC).date() - timedelta(days=5)
    )
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    edit_calls: list[dict] = []
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: edit_calls.append(kw))

    token = await _login(client, user.email)
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    response = await _edit(
        client,
        token,
        invitation_id,
        {"preferredVisitDate": yesterday.isoformat(), "additionalNotes": "Too late"},
    )
    assert response.status_code == 422, response.text

    await db_session.refresh(invitation)
    assert invitation.status == "archived"
    assert invitation.additional_notes != "Too late"
    assert edit_calls == []


async def test_edit_archived_invitation_requires_permission(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    invitation = _archived_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    viewer = await _branch_scoped_user_with(
        db_session, tenant, branch.id, ("invitations:view", "invitations:view-all")
    )

    token = issue_token(viewer)
    response = await _edit(client, token, invitation_id, {"additionalNotes": "Nope"})
    assert response.status_code == 403, response.text


async def test_list_invitations_filters_archived(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """invitations "Invitation List Filters and Surfaces Archived and Auto
    Check-Out State".
    """
    archived = _archived_invitation(db_session, branch.id)
    approved = _approved_invitation(db_session, branch.id)
    db_session.add_all([archived, approved])
    await db_session.commit()
    archived_tracking_id = archived.tracking_id

    token = await _login(client, user.email)
    auth = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/v1/invitations?status=archived", headers=auth)
    assert response.status_code == 200, response.text
    rows = response.json()["data"]
    assert [row["trackingId"] for row in rows] == [archived_tracking_id]
    assert rows[0]["archivedAt"] is not None
    assert rows[0]["checkedOutAutomatically"] is False

    response = await client.get("/api/v1/invitations?status=expired", headers=auth)
    assert response.status_code == 422, response.text


def test_export_names_the_sweep_as_check_out_actor() -> None:
    """invitation-export "Automatic check-out is labelled"."""
    invitation = InvitationFactory.build(
        id=uuid.uuid4(),
        registration_type="individual",
        source="staff_pre_registration",
        status="checked_out",
        checked_out_automatically=True,
    )
    invitation.visitors = []
    [row] = invitation_export.build_rows(
        [(invitation, _names(checked_out_by="Someone"))], ZoneInfo("UTC")
    )
    assert row["checked_out_by"] == invitation_export.AUTO_CHECK_OUT
    assert row["status"] == "Checked-out"

    invitation.status = "archived"
    [row] = invitation_export.build_rows([(invitation, _names())], ZoneInfo("UTC"))
    assert row["status"] == "Archived"


async def test_export_archived_date_range_applies_to_archived_at(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> None:
    """invitation-export "Archived export uses the archive date"."""
    today = datetime.now(UTC).date()
    recent = _archived_invitation(db_session, branch.id, archived_at=datetime.now(UTC))
    old = _archived_invitation(
        db_session, branch.id, archived_at=datetime.now(UTC) - timedelta(days=10)
    )
    db_session.add_all([recent, old])
    await db_session.commit()

    exported = await _service_export(
        db_session,
        tenant,
        status="archived",
        date_range=InvitationExportDateRange(date_from=today, date_to=today),
    )
    headers = [_base_header(h) for h in _csv_headers(exported.content)]
    assert headers[headers.index("Requested At") :] == [
        "Requested At",
        "Approved At",
        "Archived At",
    ]
    assert [row["Tracking ID"] for row in _csv_rows(exported.content)] == [recent.tracking_id]
