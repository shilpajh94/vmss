"""Approve, deny, revert approval, and delegated visibility."""

import asyncio
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    InvitationApprovalStepFactory,
    RoleFactory,
    UserFactory,
)
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.auth.models import AuditLog, User
from vmss_api.core.config import settings
from vmss_api.core.sms import SmsTemplate
from vmss_api.invitations import service as invitations_service
from vmss_api.invitations import tasks
from vmss_api.invitations.models import (
    Invitation,
)
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.invitations.tests.helpers import (
    _approved_invitation,
    _branch_scoped_invitation_approver,
    _branch_scoped_invitation_viewer,
    _branch_scoped_user_with,
    _build_invitation,
    _capture_revert_dispatch,
    _fake_tenant_session_scope,
    _get_detail,
    _host_role,
    _invitation_with_host_step,
    _invitation_with_role_step,
    _login,
    _make_host,
    _make_role_holder,
    _reception_holder,
    _reception_to_host_invitation,
    _record_senders,
    _relevant_tracking_ids,
    _revert,
    _reverted_fake_invitation,
)
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant

# --- Manual approval (POST /invitations/{id}/approve) ------------------------


async def test_approve_invitation_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted", approved_at=None)
    db_session.add(invitation)
    await db_session.commit()

    approval_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "approved"
    assert data["approvedAt"] is not None
    assert len(approval_calls) == 1

    await db_session.refresh(invitation)
    assert invitation.status == "approved"
    assert invitation.approved_at is not None


async def test_approve_invitation_soft_deleted_branch_succeeds(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """Regression test: approving a `submitted` invitation no longer 404s
    just because its recorded branch was soft-deleted after submission —
    see harden-referential-integrity-and-rbac-gates. The invitation's own
    `branchId` is already-persisted historical data, not something that
    needs to still exist for the approval to go through.
    """
    invitation = _build_invitation(db_session, branch.id, status="submitted", approved_at=None)
    db_session.add(invitation)
    await db_session.execute(
        update(Branch).where(Branch.id == branch.id).values(deleted_at=datetime.now(UTC))
    )
    await db_session.commit()

    approval_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "approved"
    assert data["approvedAt"] is not None
    assert len(approval_calls) == 1

    await db_session.refresh(invitation)
    assert invitation.status == "approved"
    assert invitation.approved_at is not None


async def test_approve_invitation_already_approved_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()
    original_approved_at = invitation.approved_at

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "approved"
    assert invitation.approved_at == original_approved_at


async def test_approve_invitation_rejected_for_workflow_backed_invitation(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """invitation-multi-step-approval spec.md "Blanket approve rejected for
    a workflow-backed invitation" (design.md Decision 3) — an invitation
    with any snapshotted `InvitationApprovalStep` must be approved through
    the step endpoint, never the blanket one.
    """
    invitation = _build_invitation(db_session, branch.id, status="submitted", approved_at=None)
    db_session.add(invitation)
    await db_session.flush()
    role = RoleFactory.build(id=uuid.uuid4(), name="step-approver", permissions=[])
    db_session.add(role)
    await db_session.flush()
    db_session.add(
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(), invitation_id=invitation.id, step_order=1, approver_role_id=role.id
        )
    )
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"


async def test_approve_invitation_rejected_for_host_only_invitation(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """specs/invitations/spec.md "Blanket approve rejected when only a
    host-approval step is snapshotted" (add-approval-step-id-and-host-
    routing) — zero configured workflow rules, but a resolved host still
    snapshots one host-identified step, which must route through the step
    endpoint, not the blanket one.
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    invitation = _build_invitation(
        db_session, branch.id, status="submitted", approved_at=None, host_id=host.id
    )
    db_session.add(invitation)
    await db_session.flush()
    db_session.add(
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            step_order=0,
            approver_role_id=None,
            approver_user_id=host.id,
        )
    )
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"


async def test_approve_invitation_concurrent_requests_transition_exactly_once(
    branch: Branch, tenant: Tenant, db_session: AsyncSession, monkeypatch
) -> None:
    """Regression test for a check-then-act race:
    `invitations/service.py::approve_invitation` used to read
    `invitation.status`, check it, then mutate and commit — two request
    handlers that each independently fetched the same `submitted`
    invitation before either approved it (the shape a real concurrent pair
    of requests produces) could both pass the check and both dispatch a
    notification. Simulated here by calling the service function twice
    against the same stale, pre-approval `invitation` object — neither call
    has seen the other's transition — and asserting the atomic
    conditional-`UPDATE` fix still only transitions and notifies once. See
    codebase-review-and-e2e-scenario-test/design.md.
    """
    invitation = _build_invitation(db_session, branch.id, status="submitted", approved_at=None)
    db_session.add(invitation)
    await db_session.commit()

    approval_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )

    first = await invitations_service.approve_invitation(db_session, invitation, tenant=tenant)
    assert first.status == "approved"

    with pytest.raises(HTTPException) as exc_info:
        await invitations_service.approve_invitation(db_session, invitation, tenant=tenant)
    assert exc_info.value.status_code == 409

    assert len(approval_calls) == 1


async def test_approve_invitation_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    monkeypatch,
    issue_token: Callable[[User], str],
) -> None:
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    invitation = _build_invitation(db_session, branch.id, status="submitted", approved_at=None)
    db_session.add(invitation)
    await db_session.commit()

    approval_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )

    token = issue_token(viewer)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"
    assert approval_calls == []


async def test_approve_invitation_unknown_id_not_found(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/invitations/{uuid.uuid4()}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_approve_invitation_denied_for_approver_scoped_elsewhere(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """An `invitations:approve` grant at a different branch gets 403, not
    404 — `authorize_branch_id` (the same dependency `POST /invitations`
    uses to resolve a branch id) 403s on no-branch-access, and only 404s
    when the branch itself doesn't exist.
    """
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-APPROVE")
    db_session.add(other_branch)
    await db_session.flush()
    approver = await _branch_scoped_invitation_approver(db_session, tenant, other_branch.id)
    invitation = _build_invitation(db_session, branch.id, status="submitted", approved_at=None)
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(approver)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"


# --- PATCH /invitations/{id}/deny -----------------------------------------------


async def test_deny_invitation_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    denial_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_denial_notification, "delay", lambda **kw: denial_calls.append(kw)
    )

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/deny",
        json={"reason": "Host unavailable"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "denied"
    assert len(denial_calls) == 1

    await db_session.refresh(invitation)
    assert invitation.status == "denied"
    assert invitation.denial_reason == "Host unavailable"
    assert invitation.denied_at is not None


async def test_deny_invitation_missing_reason_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/deny",
        json={"reason": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"


async def test_deny_invitation_non_submitted_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        f"/api/v1/invitations/{invitation.id}/deny",
        json={"reason": "Too late"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "approved"


async def test_deny_invitation_requires_permission(
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
        f"/api/v1/invitations/{invitation.id}/deny",
        json={"reason": "No"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"


# --- restrict-delegated-invitation-visibility ----------------------------------


async def test_relevant_to_me_unassigned_host_step_not_broadcast_to_other_hosts(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "An unassigned host-role step is not broadcast to every host"
    and "The delegate and Reception still see an unassigned host-role step".
    """
    host_role = await _host_role(db_session)
    host_x = _make_role_holder(db_session, host_role, branch.id)
    host_y = _make_role_holder(db_session, host_role, branch.id)
    receptionist = await _reception_holder(db_session, branch.id)
    await db_session.flush()
    invitation, _ = await _reception_to_host_invitation(
        db_session, branch.id, host_role, step0_actor=host_x, resolved_host=host_x
    )

    assert invitation.tracking_id not in await _relevant_tracking_ids(client, issue_token, host_y)
    assert invitation.tracking_id in await _relevant_tracking_ids(client, issue_token, host_x)
    assert invitation.tracking_id in await _relevant_tracking_ids(client, issue_token, receptionist)


async def test_relevant_to_me_approve_then_delegate_never_exposes_host_step_to_other_hosts(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "Approve-and-delegate never exposes the next host step to
    other hosts" — covers the gap between the web's approve and delegate
    calls, and the state after the delegate call.
    """
    host_role = await _host_role(db_session)
    host_x = _make_role_holder(db_session, host_role, branch.id)
    host_y = _make_role_holder(db_session, host_role, branch.id)
    receptionist = await _reception_holder(db_session, branch.id)
    await db_session.flush()
    invitation, step1 = await _reception_to_host_invitation(
        db_session, branch.id, host_role, step0_actor=receptionist
    )

    assert invitation.tracking_id not in await _relevant_tracking_ids(client, issue_token, host_y)
    assert invitation.tracking_id not in await _relevant_tracking_ids(client, issue_token, host_x)

    await InvitationApprovalStepRepository(db_session).delegate_if_eligible(
        step1.id, delegated_to_user_id=host_x.id, delegated_by_user_id=receptionist.id
    )
    await db_session.commit()

    assert invitation.tracking_id in await _relevant_tracking_ids(client, issue_token, host_x)
    assert invitation.tracking_id not in await _relevant_tracking_ids(client, issue_token, host_y)


async def test_list_invitations_branch_listing_rejects_host_without_view_all(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "A host holding only invitations:view cannot use the
    branch-wide listing" — permission-denied case for the narrowed gate.
    """
    host_role = await _host_role(db_session)
    host = _make_role_holder(db_session, host_role, branch.id)
    db_session.add(_build_invitation(db_session, branch.id))
    await db_session.commit()
    token = issue_token(host)

    for headers in (
        {"Authorization": f"Bearer {token}"},
        {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    ):
        response = await client.get("/api/v1/invitations", headers=headers)
        assert response.status_code == 403, response.text


async def test_invitation_detail_visible_to_reception_and_delegate_only(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "Reception opens any invitation at their branch", "The
    assigned user opens the invitation delegated to them", and "An
    uninvolved host cannot open a delegated invitation".
    """
    host_role = await _host_role(db_session)
    host_x = _make_role_holder(db_session, host_role, branch.id)
    host_y = _make_role_holder(db_session, host_role, branch.id)
    receptionist = await _reception_holder(db_session, branch.id)
    await db_session.flush()
    invitation, step1 = await _reception_to_host_invitation(
        db_session, branch.id, host_role, step0_actor=receptionist
    )
    await InvitationApprovalStepRepository(db_session).delegate_if_eligible(
        step1.id, delegated_to_user_id=host_x.id, delegated_by_user_id=receptionist.id
    )
    await db_session.commit()

    for caller in (receptionist, host_x):
        response = await _get_detail(client, issue_token, caller, invitation.id)
        assert response.status_code == 200, response.text
        assert response.json()["data"]["trackingId"] == invitation.tracking_id

    response = await _get_detail(client, issue_token, host_y, invitation.id)
    assert response.status_code == 404, response.text
    assert "data" not in response.json() or response.json()["data"] is None


async def test_invitation_detail_uninvolved_host_gets_404_for_unassigned_host_step(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "An uninvolved host cannot open an unassigned host-role
    step's invitation".
    """
    host_role = await _host_role(db_session)
    host_y = _make_role_holder(db_session, host_role, branch.id)
    receptionist = await _reception_holder(db_session, branch.id)
    await db_session.flush()
    invitation, _ = await _reception_to_host_invitation(
        db_session, branch.id, host_role, step0_actor=receptionist
    )

    response = await _get_detail(client, issue_token, host_y, invitation.id)
    assert response.status_code == 404, response.text


async def test_invitation_detail_delegate_without_any_grant_can_open_it(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "A delegate without invitations:view still opens their
    invitation" — the participant path skips the branch-permission check,
    same as `relevantToMe`.
    """
    host_role = await _host_role(db_session)
    receptionist = await _reception_holder(db_session, branch.id)
    delegate = UserFactory.build(
        id=uuid.uuid4(),
        email=f"delegate-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Delegate",
    )
    db_session.add(delegate)
    await db_session.flush()
    invitation, step1 = await _reception_to_host_invitation(
        db_session, branch.id, host_role, step0_actor=receptionist
    )
    await InvitationApprovalStepRepository(db_session).delegate_if_eligible(
        step1.id, delegated_to_user_id=delegate.id, delegated_by_user_id=receptionist.id
    )
    await db_session.commit()

    response = await _get_detail(client, issue_token, delegate, invitation.id)
    assert response.status_code == 200, response.text


async def test_invitation_detail_branch_wide_viewer_sees_uninvolved_invitation(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "Security and Admin keep branch-wide detail access" — any
    `invitations:view-all` holder at the branch, without participating.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, role)
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)

    response = await _get_detail(client, issue_token, viewer, invitation.id)
    assert response.status_code == 200, response.text


async def test_invitation_detail_caller_without_any_grant_gets_403(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    user_without_permissions: User,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "A caller with no viewing grant is still rejected with 403" —
    unchanged status code for the pre-existing condition.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, role)

    response = await _get_detail(client, issue_token, user_without_permissions, invitation.id)
    assert response.status_code == 403, response.text


async def test_invitation_detail_unknown_id_is_404(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "Detail from another tenant is never reachable" at the API
    level — an id absent from the caller's own tenant schema is 404; the
    schema-level isolation is covered directly below.
    """
    receptionist = await _reception_holder(db_session, branch.id)
    await db_session.commit()

    response = await _get_detail(client, issue_token, receptionist, uuid.uuid4())
    assert response.status_code == 404, response.text


async def test_is_relevant_to_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    """testing-standards.md §2 — the detail endpoint's participant check,
    run against another tenant's schema, never matches this tenant's
    invitation even for the same user and invitation ids.
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    invitation = await _invitation_with_host_step(db_session, branch.id, host)
    default_host_role_id = uuid.uuid4()
    assert await InvitationRepository(db_session).is_relevant_to(
        invitation.id, user_id=host.id, default_host_role_id=default_host_role_id
    )

    other_schema = "tenant_other_test_invitation_is_relevant_to"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        assert not await InvitationRepository(other_session).is_relevant_to(
            invitation.id, user_id=host.id, default_host_role_id=default_host_role_id
        )


# --- add-invitation-approval-revert: PATCH /invitations/{id}/revert-approval --


async def test_revert_approval_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    host = _make_host(db_session)
    db_session.add(host)
    await db_session.flush()
    invitation = _approved_invitation(db_session, branch.id, host_id=host.id)
    db_session.add(invitation)
    await db_session.commit()
    # Plain ids up front: the shared test session's `get_tenant` rollback
    # expires ORM objects mid-request (see `0c4d1c1`).
    host_id, invitation_id, user_id = host.id, invitation.id, user.id
    email_calls, push_calls = _capture_revert_dispatch(monkeypatch)

    token = await _login(client, user.email)
    response = await _revert(client, token, invitation_id, "  Approved the wrong visitor  ")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "submitted"
    assert data["approvedAt"] is None
    assert data["approvalRevertedAt"] is not None
    assert data["approvalRevertedByUserId"] == str(user_id)
    assert data["approvalRevertReason"] == "Approved the wrong visitor"

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"
    assert invitation.approved_at is None
    assert invitation.approval_revert_reason == "Approved the wrong visitor"
    assert [c["invitation_id"] for c in email_calls] == [str(invitation_id)]
    assert len(push_calls) == 1
    assert push_calls[0]["user_id"] == host_id
    assert push_calls[0]["data"]["action"] == "approval_reverted"

    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "invitation_approval_reverted",
                AuditLog.entity_id == invitation_id,
            )
        )
    ).scalar_one()
    assert audit.actor_user_id == user_id


async def test_revert_approval_auto_approved_invitation_can_be_reapproved_or_denied(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """An auto-approved invitation has no steps, so after a revert the
    blanket approve endpoint (and deny) work on it again."""
    approve_target = _approved_invitation(db_session, branch.id)
    deny_target = _approved_invitation(db_session, branch.id)
    db_session.add_all([approve_target, deny_target])
    await db_session.commit()
    _capture_revert_dispatch(monkeypatch)
    monkeypatch.setattr(tasks.send_approval_notification, "delay", lambda **kw: None)
    monkeypatch.setattr(tasks.send_denial_notification, "delay", lambda **kw: None)

    approve_id, deny_id = approve_target.id, deny_target.id

    token = await _login(client, user.email)
    for target_id in (approve_id, deny_id):
        assert (await _revert(client, token, target_id, "Mistake")).status_code == 200

    response = await client.post(
        f"/api/v1/invitations/{approve_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "approved"

    response = await client.patch(
        f"/api/v1/invitations/{deny_id}/deny",
        json={"reason": "Not expected after all"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "denied"


async def test_revert_approval_without_host_skips_push(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    invitation = _approved_invitation(db_session, branch.id, host_id=None)
    db_session.add(invitation)
    await db_session.commit()
    email_calls, push_calls = _capture_revert_dispatch(monkeypatch)

    token = await _login(client, user.email)
    response = await _revert(client, token, invitation.id, "Mistake")
    assert response.status_code == 200, response.text
    assert push_calls == []
    assert len(email_calls) == 1


@pytest.mark.parametrize("reason", [None, "", "   ", "x" * 501])
async def test_revert_approval_invalid_reason_rejected(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    reason: str | None,
) -> None:
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    email_calls, _ = _capture_revert_dispatch(monkeypatch)

    token = await _login(client, user.email)
    response = await _revert(client, token, invitation.id, reason)
    assert response.status_code == 422

    await db_session.refresh(invitation)
    assert invitation.status == "approved"
    assert email_calls == []


@pytest.mark.parametrize(
    ("status_value", "check_in_status"),
    [
        ("submitted", "unused"),
        ("denied", "unused"),
        ("checked_in", "checked_in"),
        ("checked_out", "checked_out"),
        # Approved, but the visitor has already entered at some point.
        ("approved", "checked_out"),
    ],
)
async def test_revert_approval_ineligible_state_conflicts(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
    status_value: str,
    check_in_status: str,
) -> None:
    invitation = _approved_invitation(
        db_session, branch.id, status=status_value, check_in_status=check_in_status
    )
    db_session.add(invitation)
    await db_session.commit()
    email_calls, push_calls = _capture_revert_dispatch(monkeypatch)

    token = await _login(client, user.email)
    response = await _revert(client, token, invitation.id, "Mistake")
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == status_value
    assert invitation.approval_reverted_at is None
    assert email_calls == []
    assert push_calls == []


@pytest.mark.parametrize(
    "codes",
    [
        # Security's default grants: no revert permission.
        ("invitations:view", "invitations:checkin", "invitations:checkout"),
        # Can approve, but approve does not imply revert.
        ("invitations:view", "invitations:approve"),
    ],
)
async def test_revert_approval_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
    monkeypatch,
    codes: tuple[str, ...],
) -> None:
    caller = await _branch_scoped_user_with(db_session, tenant, branch.id, codes)
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    email_calls, _ = _capture_revert_dispatch(monkeypatch)

    response = await _revert(client, issue_token(caller), invitation.id, "Mistake")
    assert response.status_code == 403

    await db_session.refresh(invitation)
    assert invitation.status == "approved"
    assert email_calls == []


async def test_revert_approval_permission_at_other_branch_forbidden(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-REVERT")
    db_session.add(other_branch)
    await db_session.flush()
    caller = await _branch_scoped_user_with(
        db_session, tenant, other_branch.id, ("invitations:view", "invitations:revert-approval")
    )
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    _capture_revert_dispatch(monkeypatch)

    response = await _revert(client, issue_token(caller), invitation.id, "Mistake")
    assert response.status_code == 403

    await db_session.refresh(invitation)
    assert invitation.status == "approved"


async def test_revert_approval_branch_scoped_holder_succeeds(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    caller = await _branch_scoped_user_with(
        db_session, tenant, branch.id, ("invitations:view", "invitations:revert-approval")
    )
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    _capture_revert_dispatch(monkeypatch)

    response = await _revert(client, issue_token(caller), invitation.id, "Mistake")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["approvalRevertedByUserId"] == str(caller.id)


async def test_revert_approval_unknown_invitation_not_found(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await _revert(client, token, uuid.uuid4(), "Mistake")
    assert response.status_code == 404


async def test_revert_approval_concurrent_requests_transition_exactly_once(
    branch: Branch, tenant: Tenant, user: User, db_session: AsyncSession, monkeypatch
) -> None:
    """Same stale-object simulation as
    `test_approve_invitation_concurrent_requests_transition_exactly_once`:
    both calls see the pre-revert `approved` row, and only the atomic
    `UPDATE` decides."""
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    email_calls, _ = _capture_revert_dispatch(monkeypatch)

    first = await invitations_service.revert_invitation_approval(
        db_session, invitation, user=user, reason="Mistake", tenant=tenant
    )
    assert first.status == "submitted"

    with pytest.raises(HTTPException) as exc_info:
        await invitations_service.revert_invitation_approval(
            db_session, invitation, user=user, reason="Mistake", tenant=tenant
        )
    assert exc_info.value.status_code == 409
    assert len(email_calls) == 1


async def test_revert_approval_if_eligible_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _approved_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_revert"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).revert_approval_if_eligible(
            invitation.id, user_id=uuid.uuid4(), reason="Mistake"
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.status == "approved"


async def test_reverted_invitation_pass_is_on_hold_until_reapproved(
    client: AsyncClient,
    tenant: Tenant,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch,
) -> None:
    """The QR issued at the first approval is refused while reverted, and
    re-approval re-sends — and re-validates — the same token."""
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="submitted",
        preferred_visit_date=None,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(invitation)
    await db_session.commit()
    approval_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )
    _capture_revert_dispatch(monkeypatch)
    token = await _login(client, user.email)
    approve_url = f"/api/v1/invitations/{invitation.id}/approve"
    auth = {"Authorization": f"Bearer {token}"}

    assert (await client.post(approve_url, headers=auth)).status_code == 200
    assert (await _revert(client, token, invitation.id, "Mistake")).status_code == 200

    qr = approval_calls[0]["qr_token"]
    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-in")
    # Same rejection any not-yet-approved invitation's scan gets.
    assert response.status_code == 400, response.text
    await db_session.refresh(invitation)
    assert invitation.status == "submitted"
    assert invitation.check_in_status == "unused"

    assert (await client.post(approve_url, headers=auth)).status_code == 200
    assert [c["qr_token"] for c in approval_calls] == [qr, qr]
    response = await client.patch(f"/api/v2/invitations/qr/{qr}/check-in")
    assert response.status_code == 200, response.text


async def test_approval_revert_notification_skipped_once_reapproved(
    tenant: Tenant, branch: Branch, db_session: AsyncSession, monkeypatch
) -> None:
    """A redelivered revert email must not reach a visitor whose request
    has since been re-approved (background-jobs.md §2)."""
    invitation = _approved_invitation(db_session, branch.id, approval_reverted_at=datetime.now(UTC))
    db_session.add(invitation)
    await db_session.commit()
    sent: list[Invitation] = []

    async def _fake_dispatch(inv, **kwargs):
        sent.append(inv)

    monkeypatch.setattr(tasks, "_dispatch", _fake_dispatch)
    await tasks._send_approval_revert_notification(tenant.schema_name, str(invitation.id))
    assert sent == []

    await db_session.execute(
        update(Invitation).where(Invitation.id == invitation.id).values(status="submitted")
    )
    await db_session.commit()
    await tasks._send_approval_revert_notification(tenant.schema_name, str(invitation.id))
    assert [inv.id for inv in sent] == [invitation.id]


async def test_approval_revert_notification_runs_real_dispatch_for_email(monkeypatch) -> None:
    """Regression: the task used to call `_dispatch(sms_body=...)`, which
    raised TypeError on every run — the earlier test faked `_dispatch` away."""
    sent = _record_senders(monkeypatch)
    invitation = _reverted_fake_invitation()
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(invitation))

    await tasks._send_approval_revert_notification("tenant_acme_test", str(invitation.id))

    assert [m["to"] for m in sent["email"]] == ["asha@example.com"]
    assert sent["sms"] == [] and sent["whatsapp"] == []


async def test_approval_revert_notification_sms_falls_back_to_email(monkeypatch) -> None:
    sent = _record_senders(monkeypatch)
    monkeypatch.setattr(settings, "fast2sms_template_approval_reverted", None)
    invitation = _reverted_fake_invitation(primary_contact_preferred_contact_method="sms")
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(invitation))

    await tasks._send_approval_revert_notification("tenant_acme_test", str(invitation.id))

    assert [m["to"] for m in sent["email"]] == ["asha@example.com"]
    assert sent["sms"] == []


async def test_approval_revert_notification_uses_sms_once_template_is_registered(
    monkeypatch,
) -> None:
    sent = _record_senders(monkeypatch)
    monkeypatch.setattr(settings, "fast2sms_template_approval_reverted", "1234567890")
    invitation = _reverted_fake_invitation(
        primary_contact_preferred_contact_method="sms",
        preferred_visit_date=date(2026, 11, 3),
        preferred_visit_time=time(9, 30),
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(invitation))

    await tasks._send_approval_revert_notification("tenant_acme_test", str(invitation.id))

    assert [m["template"] for m in sent["sms"]] == [SmsTemplate.approval_reverted]
    assert sent["sms"][0]["variables"] == ["Asha Rao", "INV-REVERT01", "03 Nov 2026 09:30"]
    assert sent["email"] == []


async def test_approval_revert_notification_skips_without_any_channel(monkeypatch) -> None:
    sent = _record_senders(monkeypatch)
    monkeypatch.setattr(settings, "fast2sms_whatsapp_template_approval_reverted", None)
    invitation = _reverted_fake_invitation(
        primary_contact_preferred_contact_method="whatsapp", primary_contact_email=None
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(invitation))

    await tasks._send_approval_revert_notification("tenant_acme_test", str(invitation.id))

    assert sent == {"email": [], "sms": [], "whatsapp": []}


@pytest.mark.parametrize(
    ("task_name", "method"),
    [
        ("send_approval_revert_notification", "email"),
        ("send_tracking_notification", "email"),
        ("send_tracking_notification", "sms"),
        ("send_denial_notification", "whatsapp"),
    ],
)
async def test_redelivered_visitor_notification_task_sends_once(
    monkeypatch, task_name: str, method: str
) -> None:
    """background-jobs spec "Redelivered task does not duplicate its side
    effect": a broker redelivery re-runs the task under the same task id."""
    sent = _record_senders(monkeypatch)
    monkeypatch.setattr(settings, "fast2sms_template_registration_pending", "t-pending")
    monkeypatch.setattr(settings, "fast2sms_template_registration_denied", "t-denied")
    invitation = _reverted_fake_invitation(
        status="submitted" if task_name != "send_denial_notification" else "denied",
        primary_contact_preferred_contact_method=method,
        primary_contact_phone="+919876543210",
    )
    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope(invitation))
    task = getattr(tasks, task_name)
    task_id = str(uuid.uuid4())
    kwargs = {
        "request_id": "test",
        "tenant_schema": "tenant_acme_test",
        "invitation_id": str(invitation.id),
    }

    for _ in range(2):
        result = await asyncio.to_thread(task.apply, kwargs=kwargs, task_id=task_id)
        result.get(propagate=True)

    assert len(sent[method]) == 1
    # A new logical event (a fresh `.delay()`, so a new task id) still sends.
    result = await asyncio.to_thread(task.apply, kwargs=kwargs, task_id=str(uuid.uuid4()))
    result.get(propagate=True)
    assert len(sent[method]) == 2
