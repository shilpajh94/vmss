"""Celery notification tasks, email templates, push and staff emails."""

import asyncio
import io
import uuid
from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace

import aiosmtplib
import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from factories import (
    ApprovalWorkflowRuleFactory,
    CompanyFactory,
    RoleFactory,
    UserFactory,
    VisitorCategoryFactory,
)
from vmss_api.auth.models import User
from vmss_api.auth.repository import RoleRepository
from vmss_api.core.config import settings
from vmss_api.invitations import notifications, qr_token, tasks
from vmss_api.invitations.models import (
    InvitationQRCode,
)
from vmss_api.invitations.qr import generate_qr_png
from vmss_api.invitations.tests.helpers import (
    _BRANCH_CONTACT_ID,
    _EMAIL_TEMPLATE_NAMES,
    _HOST_ID,
    _MAILPIT_API_URL,
    _MAILPIT_ASSET_BASE,
    _MAILPIT_BASE_URL,
    _PEOPLE,
    _approved_invitation,
    _archived_invitation,
    _assert_url_images_and_fetch_qr,
    _build_invitation,
    _capture_pushes,
    _chain_branch,
    _contact_for,
    _create_invitation_success,
    _edit,
    _fake_tenant_session_scope,
    _FakeInvitation,
    _FakeSession,
    _find_mailpit_message,
    _individual_payload,
    _login,
    _make_host,
    _persisted_approved_invitation,
    _person,
    _pushed_user_ids,
    _realistic_email_fakes,
    _record_staff_emails,
    _reschedulable_invitation,
    _reschedule,
    _revert,
    _run_reschedule_task,
    _silence_edit_dispatch,
    _silence_visitor_dispatch,
    _staff_pair,
    _UsersById,
)
from vmss_api.notifications import service as notifications_service
from vmss_api.org_structure.models import Branch, Department
from vmss_api.tenant.models import Tenant

# --- Celery task idempotency ---------------------------------------------------


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
            "qr_token": "fake-qr-token",
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
            "qr_token": "fake-qr-token",
        },
    )
    assert result.failed()
    assert logged and logged[0][0] == "approval_notification_dispatch_exhausted"


async def test_send_host_creation_notification_dispatches_email(monkeypatch) -> None:
    """qr-checkin-scheduling-photo-email spec.md "Creation with a resolved
    host sends the host an email" — exercised directly against the task
    (testing-standards.md §3's "unit-style" tier), same fake session/
    invitation pattern the other task tests above use.
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        tracking_id="INV-TEST0003",
        primary_contact_full_name="Meera Krishnan",
        purpose_of_visit="Interview",
    )
    fake_host = UserFactory.build(id=uuid.uuid4(), email="host@acme-test.example", is_active=True)
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, user=fake_host)
    )

    result = await asyncio.to_thread(
        tasks.send_host_creation_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "host_id": str(fake_host.id),
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert sent[0]["to"] == "host@acme-test.example"
    assert "INV-TEST0003" in sent[0]["body"]


async def test_send_host_creation_notification_skips_when_invitation_missing(monkeypatch) -> None:
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(None))

    result = await asyncio.to_thread(
        tasks.send_host_creation_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "host_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)
    assert sent == []


async def test_send_host_creation_notification_skips_when_host_missing(monkeypatch) -> None:
    """Host deactivated/deleted between enqueue and task execution — no
    email, no error (background-jobs.md §2 idempotency).
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(tracking_id="INV-TEST0004")
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, user=None)
    )

    result = await asyncio.to_thread(
        tasks.send_host_creation_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "host_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)
    assert sent == []


async def test_send_edit_notification_includes_point_of_contact_when_set(monkeypatch) -> None:
    """`edit.html`'s Point-of-Contact row, and the plain-text fallback body,
    both reflect whichever POC is currently resolved on the invitation
    (add-invitation-point-of-contact) — not just whichever visit-detail
    field actually changed in this particular edit.
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        tracking_id="INV-TEST0010",
        purpose_of_visit="Interview",
        preferred_visit_date=date(2026, 9, 15),
        preferred_visit_time=time(17, 46),
        expected_duration="1-hour",
        poc_name="Priya POC",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

    result = await asyncio.to_thread(
        tasks.send_edit_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert "YOUR POINT OF CONTACT" in sent[0]["body"]
    assert "Name: Priya POC" in sent[0]["body"]
    assert sent[0]["html_body"] is not None
    assert "Priya POC" in sent[0]["html_body"]


async def test_send_edit_notification_omits_point_of_contact_when_unset(monkeypatch) -> None:
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        tracking_id="INV-TEST0011",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

    result = await asyncio.to_thread(
        tasks.send_edit_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert "Point of contact" not in sent[0]["body"]
    assert sent[0]["html_body"] is None or "Point of contact" not in sent[0]["html_body"]


async def test_send_poc_creation_notification_includes_visit_details(monkeypatch) -> None:
    """add-invitation-point-of-contact: the newly-named point of contact
    gets the same level of visit detail (duration, department) the
    visitor's own edit-notification email already carries — not just
    tracking id/visitor/purpose — plus the visitor's own contact details
    (phone/email), so the POC can actually reach them about the visit.
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        tracking_id="INV-TEST0012",
        primary_contact_full_name="Meera Krishnan",
        primary_contact_phone="+91 90000 44455",
        primary_contact_email="meera@example.com",
        purpose_of_visit="Interview",
        preferred_visit_date=date(2026, 9, 15),
        preferred_visit_time=time(17, 46),
        expected_duration="1-hour",
        department_to_visit="Engineering",
    )
    fake_poc = UserFactory.build(id=uuid.uuid4(), email="poc@acme-test.example", is_active=True)
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, user=fake_poc)
    )

    result = await asyncio.to_thread(
        tasks.send_poc_creation_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "poc_id": str(fake_poc.id),
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert sent[0]["to"] == "poc@acme-test.example"
    assert "Expected duration: 1-hour" in sent[0]["body"]
    assert "Department: Engineering" in sent[0]["body"]
    assert "Visitor phone: +91 90000 44455" in sent[0]["body"]
    assert "Visitor email: meera@example.com" in sent[0]["body"]
    assert sent[0]["html_body"] is not None
    assert "1-hour" in sent[0]["html_body"]
    assert "Engineering" in sent[0]["html_body"]
    assert "+91 90000 44455" in sent[0]["html_body"]
    assert "meera@example.com" in sent[0]["html_body"]


async def test_send_host_creation_notification_exhausted_retries_logs_error(monkeypatch) -> None:
    class _FailingEmailSender:
        async def send(self, **kwargs):
            raise RuntimeError("SMTP is down")

    monkeypatch.setattr(notifications, "email_sender", _FailingEmailSender())
    fake_invitation = _FakeInvitation(tracking_id="INV-TEST0005")
    fake_host = UserFactory.build(id=uuid.uuid4(), email="host@acme-test.example", is_active=True)
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, user=fake_host)
    )
    logged = []
    monkeypatch.setattr(tasks.logger, "error", lambda event, **kw: logged.append((event, kw)))
    monkeypatch.setattr(tasks.send_host_creation_notification, "max_retries", 0)

    result = await asyncio.to_thread(
        tasks.send_host_creation_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "host_id": str(fake_host.id),
        },
    )
    assert result.failed()
    assert logged and logged[0][0] == "host_creation_notification_dispatch_exhausted"
    assert logged[0][1]["host_id"] == str(fake_host.id)


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


async def test_send_approval_notification_delivers_email_with_qr_via_mailpit(
    monkeypatch,
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    user: User,
) -> None:
    monkeypatch.setattr(settings, "email_asset_base_url", _MAILPIT_ASSET_BASE)
    real = await _persisted_approved_invitation(
        db_session, branch, user, qr_token_value="mailpit-qr-token"
    )
    tracking_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    recipient = f"mailpit-check-{uuid.uuid4().hex[:8]}@example.com"
    fake_invitation = _FakeInvitation(
        id=real.id,
        expires_at=real.expires_at,
        branch_id=branch.id,
        status="approved",
        tracking_id=tracking_id,
        primary_contact_full_name="Meera Krishnan",
        purpose_of_visit="Interview",
        preferred_visit_date=date(2026, 10, 14),
        preferred_visit_time=time(10, 30),
        expected_duration="1 hour",
        poc_name="Priya Nair",
        primary_contact_preferred_contact_method="email",
        primary_contact_email=recipient,
        primary_contact_phone=None,
    )
    # `notifications.email_sender` is deliberately left as the real
    # `SmtpEmailSender` here (unlike every other task test above) so a real
    # SMTP send goes out for Mailpit to actually capture.
    monkeypatch.setattr(
        tasks,
        "tenant_session_scope",
        _fake_tenant_session_scope(fake_invitation, tenant=tenant, **_realistic_email_fakes()),
    )

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": tenant.schema_name,
            "invitation_id": str(real.id),
            "qr_token": "mailpit-qr-token",
        },
    )
    result.get(propagate=True)

    async with AsyncClient() as mailpit:
        detail = await _find_mailpit_message(mailpit, tracking_id, recipient)
    assert detail["Subject"] == "Your visit is confirmed"
    assert detail["From"]["Name"] == "Visimio"
    assert "Your check-in pass" in detail["HTML"]
    for expected in ("Your point of contact", "Priya Nair", "Tower A", "Engineering"):
        assert expected in detail["HTML"], expected
    await _assert_url_images_and_fetch_qr(detail, client, "mailpit-qr-token")


async def test_send_approval_notification_without_asset_base_embeds_only_the_qr(
    monkeypatch,
) -> None:
    """The unconfigured fallback: a text wordmark header (no logo part) and
    the QR as the one inline part, still never an attachment."""
    tracking_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    recipient = f"mailpit-check-{uuid.uuid4().hex[:8]}@example.com"
    fake_invitation = _FakeInvitation(
        id=uuid.uuid4(),
        status="approved",
        tracking_id=tracking_id,
        primary_contact_preferred_contact_method="email",
        primary_contact_email=recipient,
        primary_contact_phone=None,
    )
    monkeypatch.setattr(
        tasks,
        "tenant_session_scope",
        _fake_tenant_session_scope(fake_invitation, **_realistic_email_fakes()),
    )

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

    async with AsyncClient() as mailpit:
        detail = await _find_mailpit_message(mailpit, tracking_id, recipient)
        assert detail["Attachments"] == []
        assert [part["ContentID"] for part in detail["Inline"]] == ["visit-qr@vmss"]
        assert "visimio-logo@vmss" not in detail["HTML"]
        assert 'src="cid:visit-qr@vmss"' in detail["HTML"]
        inline_response = await mailpit.get(
            f"{_MAILPIT_BASE_URL}/message/{detail['ID']}/part/{detail['Inline'][0]['PartID']}"
        )
        qr_image = Image.open(io.BytesIO(inline_response.content))
        qr_image.verify()
        assert inline_response.content == await generate_qr_png("fake-qr-token")


async def test_send_tracking_notification_delivers_email_via_mailpit(monkeypatch) -> None:
    """Same real-SMTP-round-trip bar as
    `test_send_approval_notification_delivers_email_with_qr_via_mailpit`
    above, extended to the submission tracking notification (task 9.1) — the
    "your registration is received" email sent when creation leaves an
    invitation `submitted` rather than immediately `approved`. Unlike the
    approval email, this one carries no QR attachment.
    """
    tracking_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    recipient = f"mailpit-check-{uuid.uuid4().hex[:8]}@example.com"
    fake_invitation = _FakeInvitation(
        status="submitted",
        tracking_id=tracking_id,
        primary_contact_preferred_contact_method="email",
        primary_contact_email=recipient,
        primary_contact_phone=None,
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

    result = await asyncio.to_thread(
        tasks.send_tracking_notification.apply,
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
        assert detail["Subject"] == "We've received your visit request"
        assert detail["Attachments"] == []
        assert tracking_id in detail["Text"]


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
        assert detail_response.json()["Subject"] == "Your visit request wasn't approved"


async def test_send_reschedule_notification_delivers_email_via_mailpit(
    monkeypatch,
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    user: User,
) -> None:
    """Same real-SMTP-round-trip bar, extended to the reschedule
    notification: an approved visit's existing QR (the persisted token) is
    shown again, by signed URL, with nothing attached or inline.
    """
    monkeypatch.setattr(settings, "email_asset_base_url", _MAILPIT_ASSET_BASE)
    real = await _persisted_approved_invitation(
        db_session, branch, user, qr_token_value="persisted-qr-token"
    )
    tracking_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    recipient = f"mailpit-check-{uuid.uuid4().hex[:8]}@example.com"
    fake_invitation = _FakeInvitation(
        id=real.id,
        expires_at=real.expires_at,
        branch_id=branch.id,
        status="approved",
        tracking_id=tracking_id,
        primary_contact_full_name="Meera Krishnan",
        preferred_visit_date=date(2026, 12, 1),
        preferred_visit_time=time(15, 30),
        previous_preferred_visit_date=date(2026, 11, 28),
        previous_preferred_visit_time=time(10, 0),
        poc_name="Priya Nair",
        primary_contact_preferred_contact_method="email",
        primary_contact_email=recipient,
        primary_contact_phone=None,
    )
    fake_qr = InvitationQRCode(
        id=uuid.uuid4(),
        invitation_id=real.id,
        qr_token="persisted-qr-token",
        image_storage_key="k",
    )
    monkeypatch.setattr(
        tasks,
        "tenant_session_scope",
        _fake_tenant_session_scope(
            fake_invitation, qr_code=fake_qr, tenant=tenant, **_realistic_email_fakes()
        ),
    )

    result = await asyncio.to_thread(
        tasks.send_reschedule_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": tenant.schema_name,
            "invitation_id": str(real.id),
        },
    )
    result.get(propagate=True)

    async with AsyncClient() as mailpit:
        detail = await _find_mailpit_message(mailpit, tracking_id, recipient)
    assert detail["Subject"] == "Your visit has been rescheduled"
    assert "Tue, 1 Dec 2026 · 3:30 PM" in detail["Text"]
    assert "Sat, 28 Nov 2026 · 10:00 AM" in detail["Text"]
    assert "Priya Nair" in detail["HTML"]
    await _assert_url_images_and_fetch_qr(detail, client, "persisted-qr-token")


async def test_send_host_creation_notification_delivers_email_via_mailpit(monkeypatch) -> None:
    """Same real-SMTP-round-trip bar, extended to the new host-creation
    email (qr-checkin-scheduling-photo-email/design.md Decision 5) —
    `notifications.email_sender` is deliberately left as the real
    `SmtpEmailSender` so a genuine `aiosmtplib.send` goes out for Mailpit to
    actually capture.
    """
    tracking_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    recipient = f"mailpit-check-{uuid.uuid4().hex[:8]}@example.com"
    fake_invitation = _FakeInvitation(
        tracking_id=tracking_id,
        primary_contact_full_name="Meera Krishnan",
        purpose_of_visit="Interview",
    )
    fake_host = UserFactory.build(id=uuid.uuid4(), email=recipient, is_active=True)
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, user=fake_host)
    )

    result = await asyncio.to_thread(
        tasks.send_host_creation_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "host_id": str(fake_host.id),
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
        assert detail_response.json()["Subject"] == "You've been named host for a visit"


# --- Push notifications (add-invitation-push-notifications) -----------------


async def test_create_invitation_submission_notifies_owning_role(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    visit_host: User,
    monkeypatch,
) -> None:
    """specs/invitations/spec.md "Submission Notifies the Owning Role via
    Push" (role-based-invitation-workflow) — every submitted invitation's
    `stepOrder` 0 ownership step is role-identified for the tenant's default
    host role (`reception`), pushed at submission regardless of any
    `hostId` a client still supplies (now ignored — see
    `test_create_invitation_ignores_supplied_host_fields`).
    """
    calls: list[dict] = []
    email_calls: list[dict] = []

    async def _fake_notify_step_approver(tenant_db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_step_approver", _fake_notify_step_approver)
    monkeypatch.setattr(
        tasks.send_tracking_notification, "delay", lambda **kw: email_calls.append(kw)
    )

    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["hostId"] = str(visit_host.id)
    created = await _create_invitation_success(client, token, branch, payload=payload)

    # Push to the ownership step's role, not the (ignored) supplied host ...
    assert len(calls) == 1
    assert calls[0]["approver_role_id"] == reception_role.id
    assert calls[0]["approver_user_id"] is None
    assert calls[0]["branch_id"] == branch.id
    # ... and, for the same submission, the visitor's own tracking email/SMS
    # (proposal.md finding #1 — both channels must fire for the same request,
    # not just whichever one this test happened to check).
    assert len(email_calls) == 1
    assert email_calls[0]["invitation_id"] == created["id"]


async def test_create_invitation_configured_chain_determines_submission_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """A category's own configured `ApprovalWorkflowRule` chain now
    determines which step (and therefore which role) gets pushed at
    submission — its first configured step is the invitation's current
    step, so the submission push goes to that step's role, not
    unconditionally to the tenant's default host role
    (`docs/features/approvals.md` "The host-nomination step").
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


async def test_create_invitation_admin_owning_role_sends_no_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """specs/invitations/spec.md "Submission with an Admin-role owning role
    sends no push" — a tenant that has reconfigured its default host role to
    the standard `admin` role gets no push on submission, via the same
    admin-exclusion rule `notify_step_approver` already applies generically.
    """
    admin_role = await RoleRepository(db_session).get_by_name("admin")
    assert admin_role is not None  # seeded by the `user` fixture
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), default_host_role_id=admin_role.id))
    await db_session.commit()

    role_calls: list[dict] = []

    async def _fake_notify_role_at_branch(tenant_db, **kwargs):
        role_calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_role_at_branch", _fake_notify_role_at_branch)

    token = await _login(client, user.email)
    await _create_invitation_success(client, token, branch, payload=_individual_payload())

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


async def test_create_invitation_notifies_owning_role_even_with_no_configured_rules(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """Replaces the old "hostless, no rules -> nothing to push" behavior —
    the default test category (`_default_visitor_category`) has no
    configured workflow rules, but every submitted invitation now gets an
    unconditional `stepOrder` 0 ownership step for the tenant's default host
    role (role-based-invitation-workflow), so there is always someone to
    push to.
    """
    calls: list[dict] = []

    async def _fake_notify_step_approver(tenant_db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_step_approver", _fake_notify_step_approver)

    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None

    token = await _login(client, user.email)
    await _create_invitation_success(client, token, branch, payload=_individual_payload())

    assert len(calls) == 1
    assert calls[0]["approver_role_id"] == reception_role.id
    assert calls[0]["approver_user_id"] is None


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
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """No dual-channel assertion here (unlike submit/approve/deny/reschedule,
    proposal.md finding #1): the check-in transition dispatches only the
    host push, no visitor-facing email/SMS task — there is nothing on the
    other channel to assert. Check-in now happens through the canonical,
    public v2 endpoint (checkin-approval-workflow-improvements).
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

    response = await client.patch(f"/api/v2/invitations/{invitation.tracking_id}/check-in")
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


# --- Email templates (email-notifications capability) -----------------------


async def test_every_notification_template_renders_without_error() -> None:
    """spec.md "Every Notification Email Is Rendered From a Branded HTML
    Template" — each template renders given a representative context,
    without raising, into both an HTML and a plain-text part.
    """
    from vmss_api.core.email_rendering import render_email

    representative_context = {
        "company_name": "Acme Test Co",
        "logo_url": None,
        "recipient_name": "Meera Krishnan",
        "recipient_email": "meera@example.com",
        "tracking_id": "INV-TEST0001",
        "visitor_name": "Meera Krishnan",
        "purpose": "Interview",
        "visit_date": date(2026, 10, 1),
        "visit_time": time(10, 0),
        "duration": "1 hour",
        "department": "Engineering",
        "denial_reason": "Not expected",
        "host_name": "Rahul Nair",
        "host_contact": "rahul@example.com",
        "front_desk_contact": None,
        "qr_cid": "visit-qr@vmss",
        "is_approved": True,
    }
    for template_name in _EMAIL_TEMPLATE_NAMES:
        rendered = render_email(template_name, representative_context)
        assert rendered.subject
        assert "<html" in rendered.html
        assert "INV-TEST0001" in rendered.html
        assert "INV-TEST0001" in rendered.text


async def test_template_rendering_failure_falls_back_to_plain_text(monkeypatch) -> None:
    """spec.md "Template Rendering Failure Falls Back to a Minimal
    Plain-Text Email" — a forced rendering failure still results in a
    deliverable (plain-text-only) email, logged at `ERROR`.
    """
    from vmss_api.core.email_rendering import TemplateRenderError

    def _raise(*args, **kwargs):
        raise TemplateRenderError("forced failure")

    monkeypatch.setattr(tasks, "render_email", _raise)
    logged: list[tuple[str, dict]] = []
    monkeypatch.setattr(tasks.logger, "error", lambda event, **kw: logged.append((event, kw)))

    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        tracking_id="INV-TEST0006",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
        primary_contact_phone=None,
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

    result = await asyncio.to_thread(
        tasks.send_tracking_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert sent[0]["html_body"] is None
    assert "INV-TEST0006" in sent[0]["body"]
    assert logged and logged[0][0] == "email_template_render_failed"


async def test_approval_email_includes_resolved_host_contact(monkeypatch) -> None:
    """spec.md "Approval email with a resolved host includes their contact
    details".
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        status="approved",
        tracking_id="INV-TEST0007",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
        primary_contact_phone=None,
        host_id=uuid.uuid4(),
    )
    fake_host = UserFactory.build(
        id=fake_invitation.host_id,
        full_name="Rahul Nair",
        phone_number="+91 90000 11122",
        is_active=True,
    )
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, user=fake_host)
    )

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "qr_token": "fake-qr-token",
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert sent[0]["html_body"] is not None
    assert "Rahul Nair" in sent[0]["html_body"]
    assert "+91 90000 11122" in sent[0]["html_body"]


async def test_approval_email_falls_back_to_front_desk_contact_when_no_host(monkeypatch) -> None:
    """spec.md "Approval email with no resolved host falls back to the
    front-desk contact".
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        status="approved",
        tracking_id="INV-TEST0008",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
        primary_contact_phone=None,
    )
    fake_company = CompanyFactory.build(
        id=uuid.uuid4(), phone="+91 80000 22233", email="frontdesk@acme-test.example"
    )
    monkeypatch.setattr(
        tasks,
        "tenant_session_scope",
        _fake_tenant_session_scope(fake_invitation, company=fake_company),
    )

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "qr_token": "fake-qr-token",
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert sent[0]["html_body"] is not None
    assert "+91 80000 22233" in sent[0]["html_body"]


async def test_approval_email_prefers_point_of_contact_over_host(monkeypatch) -> None:
    """add-invitation-point-of-contact: when both a host and a point of
    contact are resolved, the "Your point of contact" box shows the POC —
    a deliberate override of who to reach about the visit's logistics —
    not the workflow-resolved host.

    `_FakeSession.execute` returns the single configured `user=` for *any*
    `UserRepository.get_active(...)` call regardless of which id it was
    given (host_id or poc_user_id alike), so this test can't give the host
    and POC two independently-resolved live identities. It instead relies
    on `poc_name` being read straight off `invitation.poc_name` rather than
    re-resolved from the session — distinct from `host_name`, which *is*
    session-resolved — so asserting the invitation's own `poc_name`
    ("Priya POC") appears while the session-resolved name ("Rahul Nair",
    standing in for whichever party a real host lookup would return) does
    not is still a valid, if narrow, check that the POC branch fired
    instead of the host branch.
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        status="approved",
        tracking_id="INV-TEST0013",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
        primary_contact_phone=None,
        host_id=uuid.uuid4(),
        poc_user_id=uuid.uuid4(),
        poc_name="Priya POC",
    )
    fake_resolved_user = UserFactory.build(
        id=uuid.uuid4(), full_name="Rahul Nair", phone_number="+91 90000 33344", is_active=True
    )
    monkeypatch.setattr(
        tasks,
        "tenant_session_scope",
        _fake_tenant_session_scope(fake_invitation, user=fake_resolved_user),
    )

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "qr_token": "fake-qr-token",
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert sent[0]["html_body"] is not None
    assert "Priya POC" in sent[0]["html_body"]
    assert "Rahul Nair" not in sent[0]["html_body"]


async def test_approval_email_shows_role_based_point_of_contact_without_live_contact(
    monkeypatch,
) -> None:
    """A role-identified point of contact has no single person's phone/email
    to resolve — the box shows just the role's snapshotted name, still in
    preference to the host.
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        status="approved",
        tracking_id="INV-TEST0014",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
        primary_contact_phone=None,
        host_id=uuid.uuid4(),
        poc_role_id=uuid.uuid4(),
        poc_name="Front Desk",
    )
    fake_host = UserFactory.build(
        id=fake_invitation.host_id, full_name="Rahul Nair", is_active=True
    )
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, user=fake_host)
    )

    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "qr_token": "fake-qr-token",
        },
    )
    result.get(propagate=True)

    assert len(sent) == 1
    assert sent[0]["html_body"] is not None
    assert "Front Desk" in sent[0]["html_body"]
    assert "Rahul Nair" not in sent[0]["html_body"]


async def test_create_invitation_enqueues_owning_role_email_notification(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """spec.md "Submission emails every holder of the owning role" — the
    submission enqueues the role-fan-out email task with the ownership
    step's role and the invitation's branch. `.delay()` only enqueues to a
    real Celery/Redis broker — it does not run the task body inline — so
    this test asserts what the request itself is responsible for (the
    enqueue), the same way every other task-dispatch test in this module
    does; `test_send_submission_role_email_notification_emails_every_role_
    holder_with_usable_email` below exercises the task body itself.
    """
    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None

    calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_submission_role_email_notification, "delay", lambda **kw: calls.append(kw)
    )

    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=_individual_payload())

    assert len(calls) == 1
    assert calls[0]["invitation_id"] == data["id"]
    assert calls[0]["role_id"] == str(reception_role.id)
    assert calls[0]["branch_id"] == str(branch.id)


async def test_send_submission_role_email_notification_emails_every_role_holder_with_usable_email(
    monkeypatch,
) -> None:
    """spec.md "Submission emails every holder of the owning role" —
    exercised directly against the task body (testing-standards.md §3's
    "unit-style" tier), since `.delay()` itself only enqueues.
    """
    sent = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        tracking_id="INV-TEST0009",
        primary_contact_full_name="Meera Krishnan",
        purpose_of_visit="Interview",
    )
    role_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    first_user = UserFactory.build(id=uuid.uuid4(), email="reception1@acme-test.example")
    second_user = UserFactory.build(id=uuid.uuid4(), email="reception2@acme-test.example")

    class _FakeUserRepository:
        def __init__(self, session):
            pass

        async def list_users_holding_role_at_branch(self, role_id_arg, branch_id_arg):
            assert role_id_arg == role_id
            assert branch_id_arg == branch_id
            return [first_user, second_user]

    monkeypatch.setattr(tasks, "UserRepository", _FakeUserRepository)
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))

    result = await asyncio.to_thread(
        tasks.send_submission_role_email_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "role_id": str(role_id),
            "branch_id": str(branch_id),
        },
    )
    result.get(propagate=True)

    recipients = {call["to"] for call in sent}
    assert recipients == {"reception1@acme-test.example", "reception2@acme-test.example"}
    assert all("INV-TEST0009" in call["body"] for call in sent)


# --- QR inline-only + reschedule QR (refine-email-templates-and-visimio-brand)


async def test_reschedule_of_approved_visit_embeds_the_persisted_qr(monkeypatch) -> None:
    fake_qr = InvitationQRCode(
        id=uuid.uuid4(),
        invitation_id=uuid.uuid4(),
        qr_token="persisted-token",
        image_storage_key="k",
    )
    sent = await _run_reschedule_task(
        monkeypatch, _reschedulable_invitation("approved"), qr_code=fake_qr
    )

    assert len(sent) == 1
    assert "attachment" not in sent[0]
    [inline] = sent[0]["inline_images"]
    assert inline.cid == "visit-qr@vmss"
    assert inline.content == await generate_qr_png("persisted-token")
    assert 'src="cid:visit-qr@vmss"' in sent[0]["html_body"]


async def test_reschedule_of_pending_visit_has_no_qr(monkeypatch) -> None:
    sent = await _run_reschedule_task(monkeypatch, _reschedulable_invitation("submitted"))

    assert sent[0]["inline_images"] == []
    assert "cid:visit-qr@vmss" not in sent[0]["html_body"]
    assert "as soon as it's approved" in sent[0]["body"]


async def test_reschedule_of_approved_visit_without_qr_row_warns_and_falls_back(
    monkeypatch,
) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(tasks.logger, "warning", lambda event, **kw: warnings.append(event))

    sent = await _run_reschedule_task(
        monkeypatch, _reschedulable_invitation("approved"), qr_code=None
    )

    assert warnings == ["reschedule_notification_qr_missing"]
    assert sent[0]["inline_images"] == []
    assert "as soon as it's approved" in sent[0]["body"]


async def test_approval_email_sends_qr_inline_only(monkeypatch) -> None:
    sent: list[dict] = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fake_invitation = _FakeInvitation(
        status="approved",
        tracking_id="INV-INLINE01",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation))
    result = await asyncio.to_thread(
        tasks.send_approval_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
            "qr_token": "tok",
        },
    )
    result.get(propagate=True)

    assert "attachment" not in sent[0]
    assert [image.cid for image in sent[0]["inline_images"]] == ["visit-qr@vmss"]


async def test_email_context_resolves_place_department_and_front_desk_from_org_chart(
    monkeypatch,
) -> None:
    """email-notifications "Confirmation email shows when, where and who"
    and "Branch contact preferred over company contact"."""
    branch = Branch(
        id=uuid.uuid4(),
        name="Technopark Campus",
        code="TPK",
        address="Phase 1",
        city="Trivandrum",
        contact_phone="+91 80000 22233",
    )
    department = Department(id=uuid.uuid4(), name="Engineering")
    building = SimpleNamespace(name="Tower A")
    company = CompanyFactory.build(id=uuid.uuid4(), phone="+91 11111 11111")
    fake_invitation = _FakeInvitation(
        status="approved",
        tracking_id="INV-PLACE001",
        branch_id=branch.id,
        department_id=department.id,
        department_to_visit="free text dept",
        poc_name="Priya Nair",
    )
    session = _FakeSession(
        fake_invitation, company=company, location=(branch, department, building)
    )

    context = await tasks._invitation_email_context(
        session,  # type: ignore[arg-type]  # fakes stand in for the ORM objects
        fake_invitation,  # type: ignore[arg-type]
        recipient_name=None,
        recipient_email=None,
    )

    assert context["place"] == "Tower A · Technopark Campus · Phase 1, Trivandrum"
    assert context["department"] == "Engineering"
    assert context["front_desk_contact"] == "+91 80000 22233"
    assert context["contact_name"] == "Priya Nair"


async def test_contact_chain_prefers_the_invitation_poc(monkeypatch) -> None:
    contact = await _contact_for(
        monkeypatch, poc_name="Priya Nair", host_id=_HOST_ID, branch=_chain_branch(), people=_PEOPLE
    )
    assert contact["contact_name"] == "Priya Nair"
    assert contact["contact_title"] == "Your point of contact"


async def test_contact_chain_falls_back_to_the_host(monkeypatch) -> None:
    contact = await _contact_for(
        monkeypatch, host_id=_HOST_ID, branch=_chain_branch(), people=_PEOPLE
    )
    assert (contact["contact_name"], contact["contact_detail"]) == (
        "Rahul Verma",
        "+91 90000 33344",
    )


async def test_contact_chain_falls_back_to_the_branch_contact_person(monkeypatch) -> None:
    contact = await _contact_for(monkeypatch, branch=_chain_branch(), people=_PEOPLE)
    assert (contact["contact_name"], contact["contact_detail"]) == (
        "Anil Menon",
        "+91 90000 55566",
    )
    assert contact["contact_title"] == "Your point of contact"


async def test_contact_chain_falls_back_to_the_front_desk(monkeypatch) -> None:
    contact = await _contact_for(
        monkeypatch, branch=_chain_branch(contact_person_user_id=None), people=_PEOPLE
    )
    assert (contact["contact_name"], contact["contact_detail"]) == ("Front desk", "+91 80000 22233")


async def test_contact_chain_ends_at_reception_when_nothing_is_configured(monkeypatch) -> None:
    contact = await _contact_for(
        monkeypatch, branch=_chain_branch(contact_person_user_id=None), front_desk=None
    )
    assert contact == {
        "contact_title": "Your point of contact",
        "contact_name": "Reception at Main Branch",
        "contact_detail": None,
    }


async def test_contact_chain_reception_without_a_branch(monkeypatch) -> None:
    contact = await _contact_for(monkeypatch, branch=None, front_desk=None)
    assert contact["contact_name"] == "Reception"


async def test_contact_chain_skips_untrustworthy_names(monkeypatch) -> None:
    """An opaque IdP subject as the host's name, and a branch contact whose
    "name" is just their email, are both skipped — the front desk wins."""
    people = {
        _HOST_ID: _person("ccbb9a1e304730e0512d912e18f6ce65", phone="+91 1"),
        _BRANCH_CONTACT_ID: _person("anil@example.com", email="anil@example.com"),
    }
    contact = await _contact_for(
        monkeypatch,
        poc_name="  ",
        host_id=_HOST_ID,
        branch=_chain_branch(),
        people=people,
    )
    assert contact["contact_name"] == "Front desk"


async def test_confirmation_without_poc_or_host_names_the_branch_contact_person(
    monkeypatch,
) -> None:
    """email-notifications "No POC or host falls back to the branch contact
    person", end to end through the task's rendering."""
    sent: list[dict] = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    fakes = _realistic_email_fakes()
    branch, department, building = fakes["location"]
    branch.contact_person_user_id = _BRANCH_CONTACT_ID
    monkeypatch.setattr(tasks, "UserRepository", _UsersById(_PEOPLE))
    fake_invitation = _FakeInvitation(
        id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        status="approved",
        tracking_id="INV-CONTACT1",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
    )
    monkeypatch.setattr(
        tasks,
        "tenant_session_scope",
        _fake_tenant_session_scope(
            fake_invitation, company=fakes["company"], location=(branch, department, building)
        ),
    )

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

    [email] = sent
    assert "Your point of contact" in email["html_body"]
    assert "Anil Menon" in email["html_body"]
    assert "+91 90000 55566" in email["html_body"]


# --- staff-lifecycle-emails-and-dashboard-landing ----------------------------


async def test_revert_emails_host_and_poc_and_pushes_poc(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    staff_lifecycle_email_calls: list[dict],
) -> None:
    host, poc = await _staff_pair(db_session)
    invitation = _approved_invitation(db_session, branch.id, host_id=host.id, poc_user_id=poc.id)
    db_session.add(invitation)
    await db_session.commit()
    host_id, poc_id, invitation_id, user_id = host.id, poc.id, invitation.id, user.id
    _silence_visitor_dispatch(monkeypatch)
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await _revert(client, token, invitation_id, "Host on leave that day")
    assert response.status_code == 200, response.text

    assert sorted(c["recipient_user_id"] for c in staff_lifecycle_email_calls) == sorted(
        [str(host_id), str(poc_id)]
    )
    for call in staff_lifecycle_email_calls:
        assert call["event"] == "approval_reverted"
        assert call["actor_user_id"] == str(user_id)
        assert call["invitation_id"] == str(invitation_id)
    assert sorted(str(c["user_id"]) for c in user_pushes) == sorted([str(host_id), str(poc_id)])
    assert all(c["data"]["action"] == "approval_reverted" for c in user_pushes)
    assert role_pushes == []


async def test_reschedule_by_host_does_not_email_the_actor(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    staff_lifecycle_email_calls: list[dict],
) -> None:
    _, poc = await _staff_pair(db_session)
    invitation = _build_invitation(
        db_session, branch.id, status="submitted", host_id=user.id, poc_user_id=poc.id
    )
    db_session.add(invitation)
    await db_session.commit()
    poc_id, invitation_id, user_id = poc.id, invitation.id, user.id
    _silence_visitor_dispatch(monkeypatch)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await _reschedule(
        client, token, invitation_id, datetime.now(UTC).date() + timedelta(days=5)
    )
    assert response.status_code == 200, response.text

    assert [c["recipient_user_id"] for c in staff_lifecycle_email_calls] == [str(poc_id)]
    assert staff_lifecycle_email_calls[0]["event"] == "rescheduled"
    # Host push is unchanged (still sent to the acting host); POC pushed once.
    assert sorted(str(c["user_id"]) for c in user_pushes) == sorted([str(user_id), str(poc_id)])


async def test_deny_host_who_is_also_poc_gets_one_email_and_one_push(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    staff_lifecycle_email_calls: list[dict],
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _build_invitation(
        db_session, branch.id, status="submitted", host_id=host.id, poc_user_id=host.id
    )
    db_session.add(invitation)
    await db_session.commit()
    host_id, invitation_id = host.id, invitation.id
    _silence_visitor_dispatch(monkeypatch)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/deny",
        json={"reason": "Visitor not on the expected list"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert [c["recipient_user_id"] for c in staff_lifecycle_email_calls] == [str(host_id)]
    assert staff_lifecycle_email_calls[0]["event"] == "denied"
    assert [c["user_id"] for c in user_pushes] == [host_id]


async def test_deny_with_role_poc_pushes_role_and_sends_no_email(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    staff_lifecycle_email_calls: list[dict],
) -> None:
    role = RoleFactory.build(id=uuid.uuid4(), name=f"security-{uuid.uuid4().hex[:6]}")
    db_session.add(role)
    await db_session.flush()
    invitation = _build_invitation(db_session, branch.id, status="submitted", poc_role_id=role.id)
    db_session.add(invitation)
    await db_session.commit()
    role_id, branch_id, invitation_id, user_id = role.id, branch.id, invitation.id, user.id
    _silence_visitor_dispatch(monkeypatch)
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/deny",
        json={"reason": "Not expected"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert staff_lifecycle_email_calls == []
    assert user_pushes == []
    assert len(role_pushes) == 1
    assert role_pushes[0]["role_id"] == role_id
    assert role_pushes[0]["branch_id"] == branch_id
    assert role_pushes[0]["reason"] == "lifecycle_update"
    assert role_pushes[0]["exclude_user_ids"] == {user_id}
    assert role_pushes[0]["data"]["action"] == "denied"


async def test_rejected_revert_sends_no_staff_notification(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    staff_lifecycle_email_calls: list[dict],
) -> None:
    host, poc = await _staff_pair(db_session)
    invitation = _approved_invitation(
        db_session,
        branch.id,
        host_id=host.id,
        poc_user_id=poc.id,
        status="checked_in",
        check_in_status="checked_in",
    )
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    _silence_visitor_dispatch(monkeypatch)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await _revert(client, token, invitation_id, "Mistake")
    assert response.status_code == 409, response.text
    assert staff_lifecycle_email_calls == []
    assert user_pushes == []


async def test_reschedule_archived_emails_the_responsible_staff(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    staff_lifecycle_email_calls: list[dict],
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _archived_invitation(db_session, branch.id, host_id=host.id)
    db_session.add(invitation)
    await db_session.commit()
    host_id, invitation_id = host.id, invitation.id
    _silence_visitor_dispatch(monkeypatch)
    _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await _reschedule(
        client, token, invitation_id, datetime.now(UTC).date() + timedelta(days=3)
    )
    assert response.status_code == 200, response.text
    assert [(c["recipient_user_id"], c["event"]) for c in staff_lifecycle_email_calls] == [
        (str(host_id), "rescheduled")
    ]


async def test_staff_lifecycle_email_names_actor_and_reason_without_qr(
    tenant: Tenant, branch: Branch, db_session: AsyncSession, user: User, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _approved_invitation(
        db_session,
        branch.id,
        host_id=host.id,
        status="submitted",
        approval_reverted_at=datetime.now(UTC),
        approval_revert_reason="Host on leave that day",
        primary_contact_full_name="Meera Krishnan",
    )
    db_session.add(invitation)
    await db_session.commit()
    sent = _record_staff_emails(monkeypatch)

    await tasks._send_staff_lifecycle_notification(
        tenant.schema_name, str(invitation.id), str(host.id), str(user.id), "approval_reverted"
    )

    assert len(sent) == 1
    email = sent[0]
    assert email["to"] == host.email
    assert email["subject"] == "Approval withdrawn for Meera Krishnan's visit"
    assert "Host on leave that day" in email["body"]
    assert user.full_name in email["body"]
    assert "Reason given" in email["html_body"]
    assert "qr" not in email["html_body"].lower()
    assert "inline_images" not in email


@pytest.mark.parametrize(
    ("event", "stale_overrides"),
    [
        ("denied", {"status": "submitted"}),
        ("approval_reverted", {"status": "approved", "approval_reverted_at": None}),
        ("rescheduled", {"status": "checked_out", "check_in_status": "checked_out"}),
    ],
)
async def test_staff_lifecycle_email_skipped_when_event_no_longer_current(
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    user: User,
    monkeypatch,
    event: str,
    stale_overrides: dict,
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _approved_invitation(db_session, branch.id, host_id=host.id, **stale_overrides)
    db_session.add(invitation)
    await db_session.commit()
    sent = _record_staff_emails(monkeypatch)

    await tasks._send_staff_lifecycle_notification(
        tenant.schema_name,
        str(invitation.id),
        str(host.id),
        str(user.id),
        event,  # type: ignore[arg-type]
    )
    assert sent == []


async def test_staff_lifecycle_email_skips_inactive_recipient(
    tenant: Tenant, branch: Branch, db_session: AsyncSession, user: User, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    host.is_active = False
    invitation = _build_invitation(
        db_session, branch.id, status="denied", host_id=host.id, denial_reason="No"
    )
    db_session.add(invitation)
    await db_session.commit()
    sent = _record_staff_emails(monkeypatch)

    with capture_logs() as logs:
        await tasks._send_staff_lifecycle_notification(
            tenant.schema_name, str(invitation.id), str(host.id), str(user.id), "denied"
        )
    assert sent == []
    assert any(log["event"] == "staff_lifecycle_notification_recipient_not_found" for log in logs)


async def test_staff_lifecycle_email_falls_back_when_actor_deleted(
    tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _build_invitation(
        db_session, branch.id, status="denied", host_id=host.id, denial_reason="No"
    )
    db_session.add(invitation)
    await db_session.commit()
    sent = _record_staff_emails(monkeypatch)

    await tasks._send_staff_lifecycle_notification(
        tenant.schema_name, str(invitation.id), str(host.id), str(uuid.uuid4()), "denied"
    )
    assert len(sent) == 1
    assert "A staff member denied" in sent[0]["body"]


async def test_extend_invitation_pushes_host_with_new_expiry(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    now = datetime.now(UTC)
    invitation = _approved_invitation(
        db_session, branch.id, host_id=host.id, expires_at=now + timedelta(days=1)
    )
    db_session.add(invitation)
    await db_session.commit()
    host_id, invitation_id = host.id, invitation.id
    new_expiry = now + timedelta(days=7)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/extend",
        json={"expiresAt": new_expiry.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert len(user_pushes) == 1
    assert user_pushes[0]["user_id"] == host_id
    assert user_pushes[0]["title"] == "Visit pass extended"
    assert user_pushes[0]["data"]["action"] == "extended"
    assert datetime.fromisoformat(user_pushes[0]["data"]["expiresAt"]) == new_expiry
    assert "valid until" in user_pushes[0]["body"]


async def test_extend_invitation_rejected_sends_no_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    now = datetime.now(UTC)
    invitation = _approved_invitation(
        db_session, branch.id, host_id=host.id, expires_at=now + timedelta(days=2)
    )
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/extend",
        json={"expiresAt": (now + timedelta(days=1)).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422, response.text
    assert user_pushes == []


async def test_extend_invitation_without_host_sends_no_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    now = datetime.now(UTC)
    invitation = _approved_invitation(db_session, branch.id, expires_at=now + timedelta(days=1))
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/extend",
        json={"expiresAt": (now + timedelta(days=3)).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert user_pushes == []


async def test_tracking_id_check_in_pushes_poc_and_host(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, poc = await _staff_pair(db_session)
    invitation = _approved_invitation(db_session, branch.id, host_id=host.id, poc_user_id=poc.id)
    db_session.add(invitation)
    await db_session.commit()
    host_id, poc_id, tracking_id = host.id, poc.id, invitation.tracking_id
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    response = await client.patch(f"/api/v2/invitations/{tracking_id}/check-in")
    assert response.status_code == 200, response.text

    assert _pushed_user_ids(user_pushes) == sorted([str(host_id), str(poc_id)])
    assert all(c["data"]["action"] == "checked_in" for c in user_pushes)
    assert role_pushes == []


async def test_qr_check_out_pushes_role_poc_excluding_host(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    role = RoleFactory.build(id=uuid.uuid4(), name=f"security-{uuid.uuid4().hex[:6]}")
    db_session.add(role)
    await db_session.flush()
    invitation = _approved_invitation(
        db_session,
        branch.id,
        status="checked_in",
        check_in_status="checked_in",
        checked_in_at=datetime.now(UTC),
        host_id=host.id,
        poc_role_id=role.id,
    )
    db_session.add(invitation)
    await db_session.commit()
    host_id, role_id, branch_id = host.id, role.id, branch.id
    qr = qr_token.encrypt_invitation_token(invitation.id)
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-out")
    assert response.status_code == 200, response.text

    assert [c["user_id"] for c in user_pushes] == [host_id]
    assert len(role_pushes) == 1
    assert role_pushes[0]["role_id"] == role_id
    assert role_pushes[0]["branch_id"] == branch_id
    assert role_pushes[0]["reason"] == "lifecycle_update"
    assert role_pushes[0]["exclude_user_ids"] == {host_id}
    assert role_pushes[0]["data"]["action"] == "checked_out"


async def test_approve_pushes_poc(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, poc = await _staff_pair(db_session)
    invitation = _build_invitation(
        db_session, branch.id, status="submitted", host_id=host.id, poc_user_id=poc.id
    )
    db_session.add(invitation)
    await db_session.commit()
    host_id, poc_id, invitation_id = host.id, poc.id, invitation.id
    monkeypatch.setattr(tasks.send_approval_notification, "delay", lambda **kw: None)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert _pushed_user_ids(user_pushes) == sorted([str(host_id), str(poc_id)])
    assert all(c["data"]["action"] == "approved" for c in user_pushes)


async def test_extend_pushes_poc_with_new_expiry(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, poc = await _staff_pair(db_session)
    now = datetime.now(UTC)
    invitation = _approved_invitation(
        db_session,
        branch.id,
        host_id=host.id,
        poc_user_id=poc.id,
        expires_at=now + timedelta(days=1),
    )
    db_session.add(invitation)
    await db_session.commit()
    poc_id, invitation_id = poc.id, invitation.id
    new_expiry = now + timedelta(days=7)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/extend",
        json={"expiresAt": new_expiry.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    poc_pushes = [c for c in user_pushes if c["user_id"] == poc_id]
    assert len(poc_pushes) == 1
    assert poc_pushes[0]["data"]["action"] == "extended"
    assert datetime.fromisoformat(poc_pushes[0]["data"]["expiresAt"]) == new_expiry


async def test_rejected_extend_sends_no_poc_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    _, poc = await _staff_pair(db_session)
    now = datetime.now(UTC)
    invitation = _approved_invitation(
        db_session, branch.id, poc_user_id=poc.id, expires_at=now + timedelta(days=2)
    )
    db_session.add(invitation)
    await db_session.commit()
    invitation_id = invitation.id
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/extend",
        json={"expiresAt": (now + timedelta(days=1)).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422, response.text
    assert user_pushes == []
    assert role_pushes == []


async def test_edit_without_poc_change_pushes_existing_poc(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    _, poc = await _staff_pair(db_session)
    invitation = _approved_invitation(
        db_session, branch.id, poc_user_id=poc.id, visitor_category_id=None
    )
    db_session.add(invitation)
    await db_session.commit()
    poc_id, invitation_id = poc.id, invitation.id
    _silence_edit_dispatch(monkeypatch)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await _edit(client, token, invitation_id, {"additionalNotes": "Call ahead"})
    assert response.status_code == 200, response.text

    assert [c["user_id"] for c in user_pushes] == [poc_id]
    assert user_pushes[0]["data"]["action"] == "edited"


async def test_edit_changing_poc_pushes_only_poc_assigned_to_new_poc(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, old_poc = await _staff_pair(db_session)
    new_poc = UserFactory.build(
        id=uuid.uuid4(), email=f"poc-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Q"
    )
    db_session.add(new_poc)
    invitation = _approved_invitation(
        db_session, branch.id, poc_user_id=old_poc.id, visitor_category_id=None
    )
    db_session.add(invitation)
    await db_session.commit()
    new_poc_id, invitation_id = new_poc.id, invitation.id
    _silence_edit_dispatch(monkeypatch)
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await _edit(client, token, invitation_id, {"pocUserId": str(new_poc_id)})
    assert response.status_code == 200, response.text

    assert [c["user_id"] for c in user_pushes] == [new_poc_id]
    assert user_pushes[0]["data"]["action"] == "poc_assigned"


async def test_poc_who_checks_the_visitor_out_is_not_pushed(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _approved_invitation(
        db_session,
        branch.id,
        status="checked_in",
        check_in_status="checked_in",
        checked_in_at=datetime.now(UTC),
        host_id=host.id,
        poc_user_id=user.id,
    )
    db_session.add(invitation)
    await db_session.commit()
    host_id, invitation_id = host.id, invitation.id
    user_pushes, _ = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation_id}/check-out",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert [c["user_id"] for c in user_pushes] == [host_id]


async def test_host_who_is_also_poc_is_pushed_once_on_check_in(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _approved_invitation(db_session, branch.id, host_id=host.id, poc_user_id=host.id)
    db_session.add(invitation)
    await db_session.commit()
    host_id, tracking_id = host.id, invitation.tracking_id
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    response = await client.patch(f"/api/v2/invitations/{tracking_id}/check-in")
    assert response.status_code == 200, response.text

    assert [c["user_id"] for c in user_pushes] == [host_id]
    assert role_pushes == []


async def test_approve_without_poc_pushes_only_the_host(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host, _ = await _staff_pair(db_session)
    invitation = _build_invitation(
        db_session, branch.id, status="submitted", host_id=host.id, poc_user_id=None
    )
    db_session.add(invitation)
    await db_session.commit()
    host_id, invitation_id = host.id, invitation.id
    monkeypatch.setattr(tasks.send_approval_notification, "delay", lambda **kw: None)
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert [c["user_id"] for c in user_pushes] == [host_id]
    assert role_pushes == []


async def test_rejected_qr_check_in_sends_no_poc_push(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    _, poc = await _staff_pair(db_session)
    invitation = _approved_invitation(
        db_session,
        branch.id,
        poc_user_id=poc.id,
        expires_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    db_session.add(invitation)
    await db_session.commit()
    qr = qr_token.encrypt_invitation_token(invitation.id)
    user_pushes, role_pushes = _capture_pushes(monkeypatch)

    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-in")
    assert response.status_code == 410, response.text
    assert user_pushes == []
    assert role_pushes == []


# --- add-badge-print-flow: email-only "bring your ID" callout ------------------


async def _approval_email_parts(monkeypatch, *, tenant_flag: bool) -> dict:
    """Runs the approval task body with `_dispatch` captured, returning what it
    would have sent. Only the tenant lookup is stubbed; template rendering is real."""
    from types import SimpleNamespace

    fake_invitation = _FakeInvitation(
        id=uuid.uuid4(),
        status="approved",
        tracking_id="INV-BADGE001",
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
        primary_contact_phone=None,
    )
    monkeypatch.setattr(
        tasks,
        "tenant_session_scope",
        _fake_tenant_session_scope(fake_invitation, **_realistic_email_fakes()),
    )

    class _Tenants:
        def __init__(self, session) -> None:
            pass

        async def get_by_schema_name(self, schema_name):
            return SimpleNamespace(id=uuid.uuid4(), badge_print_flow_enabled=tenant_flag)

    monkeypatch.setattr(tasks, "TenantRepository", _Tenants)
    sent: dict = {}

    async def _capture(invitation, **kwargs) -> None:
        sent.update(kwargs)

    monkeypatch.setattr(tasks, "_dispatch", _capture)
    await tasks._send_approval_notification("tenant_acme_test", str(fake_invitation.id), "qr")
    return sent


async def test_approval_email_has_bring_id_callout_only_when_flow_on(monkeypatch) -> None:
    sent = await _approval_email_parts(monkeypatch, tenant_flag=True)
    assert "Please bring your ID" in sent["html_body"]
    assert "Please bring your ID" in sent["body"]


async def test_approval_email_unchanged_when_flow_off(monkeypatch) -> None:
    sent = await _approval_email_parts(monkeypatch, tenant_flag=False)
    assert "Please bring your ID" not in sent["html_body"]
    assert "Please bring your ID" not in sent["body"]
    # The standing checklist line is still there, as before.
    assert "Bring a valid government-issued photo ID." in sent["body"]
