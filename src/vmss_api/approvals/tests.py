import io
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import pytest_asyncio
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    ApprovalWorkflowRuleFactory,
    InvitationApprovalStepFactory,
    InvitationFactory,
    PermissionFactory,
    RoleFactory,
    UserFactory,
    VisitorCategoryFactory,
)
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.auth.models import Permission, Role, User, UserBranchRole
from vmss_api.auth.repository import RoleRepository
from vmss_api.invitations import tasks
from vmss_api.invitations.models import Invitation
from vmss_api.notifications import service as notifications_service
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest_asyncio.fixture(autouse=True)
async def _default_host_role(db_session: AsyncSession) -> None:
    """`create_invitation` now always resolves the tenant's default host
    role (role-based-invitation-workflow) — this module exercises it
    directly (not just through the HTTP layer), same rationale as
    `invitations/tests.py::_default_host_role`.
    """
    db_session.add(RoleFactory.build(id=uuid.uuid4(), name="reception", permissions=[]))
    await db_session.commit()


async def _get_or_create_permission(db_session: AsyncSession, code: str) -> Permission:
    """`Permission` is a global-schema catalog table (`database-architecture
    .md` §2), so its `code` is unique across the whole test run, not scoped
    per role — a test that grants the same code to more than one user (as
    several tests below do, one per approver) must reuse the existing row
    rather than trying to insert a second one.
    """
    existing = (
        await db_session.execute(select(Permission).where(Permission.code == code))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    permission = PermissionFactory.build(id=uuid.uuid4(), code=code, description=code)
    db_session.add(permission)
    await db_session.flush()
    return permission


def _build_invitation(db_session: AsyncSession, branch_id: uuid.UUID, **overrides) -> Invitation:
    """Same shape as `invitations/tests.py::_build_invitation` — a
    workflow-backed invitation's steps are attached separately below, so the
    invitation row itself starts in the same "submitted, nothing has
    happened yet" state that helper already represents.
    """
    overrides.setdefault("created_by_user_id", None)
    overrides.setdefault("registration_type", "individual")
    overrides.setdefault("source", "staff_pre_registration")
    overrides.setdefault("status", "submitted")
    overrides.setdefault("approved_at", None)
    return InvitationFactory.build(id=uuid.uuid4(), branch_id=branch_id, **overrides)


async def _user_with_role(
    db_session: AsyncSession,
    branch_id: uuid.UUID | None,
    *,
    role: Role,
    extra_permission_codes: tuple[str, ...] = (),
) -> User:
    """Grants `role` (plus any `extra_permission_codes`, folded onto the
    same role for simplicity) to a fresh user at `branch_id` — the shared
    setup every role-match/override test below builds on, since the
    interesting variable in each test is *which* role/permissions the user
    ends up with relative to the step's own `approverRoleId`. No
    `TenantUserIndex`/real password needed: every test below mints its
    bearer token directly via the `issue_token` fixture rather than
    `POST /auth/login`, since login is Admin-only
    (`conftest.py::issue_token`'s docstring) and none of these custom-role
    users are Admins.
    """
    if extra_permission_codes:
        extra_permissions = [
            await _get_or_create_permission(db_session, code) for code in extra_permission_codes
        ]
        role.permissions = [*role.permissions, *extra_permissions]
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"step-user-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Step Actor",
        branch_roles=[branch_role],
    )
    db_session.add(test_user)
    await db_session.commit()
    return test_user


def _approve_permission_role(*, name: str) -> Role:
    permission = PermissionFactory.build(
        id=uuid.uuid4(), code="invitations:approve", description="invitations:approve"
    )
    return RoleFactory.build(id=uuid.uuid4(), name=name, permissions=[permission])


async def _two_step_invitation(
    db_session: AsyncSession, branch: Branch
) -> tuple[Invitation, Role, Role]:
    """A `submitted` invitation with two pending steps, each referencing its
    own distinct approver role — used by most of the tests below. Returns
    `(invitation, step_one_role, step_two_role)`. Role names carry a random
    suffix so a test calling this more than once (e.g. for two separate
    invitations) doesn't collide on `Role.name`'s uniqueness.
    """
    suffix = uuid.uuid4().hex[:8]
    step_one_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"step-one-role-{suffix}", permissions=[]
    )
    step_two_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"step-two-role-{suffix}", permissions=[]
    )
    db_session.add_all([step_one_role, step_two_role])
    await db_session.flush()

    invitation = _build_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.flush()
    db_session.add_all(
        [
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                step_order=1,
                approver_role_id=step_one_role.id,
                escalation_minutes=None,
                auto_approve_minutes=None,
            ),
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                step_order=2,
                approver_role_id=step_two_role.id,
                escalation_minutes=30,
                auto_approve_minutes=None,
            ),
        ]
    )
    await db_session.commit()
    return invitation, step_one_role, step_two_role


async def _get_step(db_session: AsyncSession, invitation_id: uuid.UUID, step_order: int):
    steps = await InvitationApprovalStepRepository(db_session).list_for_invitation(invitation_id)
    return next(s for s in steps if s.step_order == step_order)


async def _host_step_invitation(
    db_session: AsyncSession, branch: Branch
) -> tuple[Invitation, User]:
    """A `submitted` invitation with a single host-identified pending step
    at `stepOrder` 0 — used by the host-authorization tests below
    (add-approval-step-id-and-host-routing). Returns `(invitation, host)`.
    """
    host = UserFactory.build(
        id=uuid.uuid4(),
        email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Invitation Host",
    )
    db_session.add(host)
    await db_session.flush()

    invitation = _build_invitation(db_session, branch.id, host_id=host.id)
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
    return invitation, host


async def _grant_approve_permission(
    db_session: AsyncSession, user: User, branch_id: uuid.UUID, *, override: bool = False
) -> None:
    """Grants `invitations:approve` (and, if `override`, also
    `invitations:approve-override`) to an already-existing `user` — unlike
    `_user_with_role`, which always mints a fresh user, the host-match tests
    below need to grant permission to a specific user identity (the
    invitation's own host) without changing who they are.

    Appends to `user.branch_roles` in-memory, not just `session.add()` on
    the join row: `client`'s `expire_on_commit=False` test session
    (`conftest.py::db_session`) never re-queries an already-identity-mapped
    `User`'s relationships after a later commit, so a `UserBranchRole`
    inserted purely via a raw FK (`user_id=...`) is invisible to
    `User.has_branch_access`/`has_permission` — which read the in-memory
    `branch_roles` collection — for the rest of the test, even though the
    row is genuinely in the database.
    """
    codes = (
        ("invitations:approve", "invitations:approve-override")
        if override
        else ("invitations:approve",)
    )
    permissions = [await _get_or_create_permission(db_session, code) for code in codes]
    role = RoleFactory.build(id=uuid.uuid4(), name=f"granted-role-{uuid.uuid4().hex[:8]}")
    role.permissions = permissions
    db_session.add(role)
    await db_session.flush()
    branch_role = UserBranchRole(id=uuid.uuid4(), user_id=user.id, role=role, branch_id=branch_id)
    user.branch_roles.append(branch_role)
    db_session.add(branch_role)
    await db_session.commit()


async def _host_and_role_invitation(
    db_session: AsyncSession,
    branch: Branch,
    *,
    host_step_status: str = "approved",
    step_one_status: str = "pending",
    extra_role_step: bool = False,
) -> tuple[Invitation, User, Role, Role | None]:
    """A `submitted` invitation with a host-identified `stepOrder` 0 step and
    a role-identified `stepOrder` 1 step — the shape the delegation tests
    below need (specs/approvals/spec.md "Host Delegates the Step Following
    Their Own to a Specific Person"). `host_step_status`/`step_one_status`
    let a test set up either step as already-acted-on so it (or the step
    after it) becomes the current pending one; `extra_role_step` adds a
    `stepOrder` 2 role step for the "only the immediate next step is
    delegable" tests. Returns
    `(invitation, host, step_one_role, step_two_role_or_none)`.
    """
    suffix = uuid.uuid4().hex[:8]
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{suffix}@acme-test.example", full_name="Invitation Host"
    )
    db_session.add(host)
    await db_session.flush()

    step_one_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"delegate-step-one-{suffix}", permissions=[]
    )
    db_session.add(step_one_role)
    await db_session.flush()

    invitation = _build_invitation(db_session, branch.id, host_id=host.id)
    db_session.add(invitation)
    await db_session.flush()

    acted_now = datetime.now(UTC)
    steps = [
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            step_order=0,
            approver_role_id=None,
            approver_user_id=host.id,
            status=host_step_status,
            acted_by_user_id=host.id if host_step_status != "pending" else None,
            acted_at=acted_now if host_step_status != "pending" else None,
        ),
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            step_order=1,
            approver_role_id=step_one_role.id,
            status=step_one_status,
            acted_by_user_id=host.id if step_one_status != "pending" else None,
            acted_at=acted_now if step_one_status != "pending" else None,
        ),
    ]

    step_two_role = None
    if extra_role_step:
        step_two_role = RoleFactory.build(
            id=uuid.uuid4(), name=f"delegate-step-two-{suffix}", permissions=[]
        )
        db_session.add(step_two_role)
        await db_session.flush()
        steps.append(
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                step_order=2,
                approver_role_id=step_two_role.id,
            )
        )

    db_session.add_all(steps)
    await db_session.commit()
    return invitation, host, step_one_role, step_two_role


# --- Happy path: approve every step in order ---------------------------------


async def test_approve_step_non_final_unlocks_next_step_and_computes_its_clock(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    invitation, step_one_role, _step_two_role = await _two_step_invitation(db_session, branch)
    approver = await _user_with_role(
        db_session, branch.id, role=step_one_role, extra_permission_codes=("invitations:approve",)
    )

    token = issue_token(approver)
    step_one = await _get_step(db_session, invitation.id, 1)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "submitted"
    step_two_before_assert = await _get_step(db_session, invitation.id, 2)
    assert data["currentApprovalStep"] == {
        "id": str(step_two_before_assert.id),
        "stepOrder": 2,
        "approverRoleId": str(step_two_before_assert.approver_role_id),
        "approverUserId": None,
        "totalSteps": 2,
        "delegatedToUserId": None,
    }

    step_two = await _get_step(db_session, invitation.id, 2)
    assert step_two.status == "pending"
    # specs/approvals/spec.md "A later step's timestamps are set when it
    # becomes current" — step two's rule configured escalation_minutes=30,
    # so its escalates_at is now populated relative to step one's approval,
    # not the invitation's original submission time.
    assert step_two.escalates_at is not None
    assert step_two.auto_approves_at is None


async def test_approve_step_last_step_approves_invitation_and_dispatches_notification(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    invitation, step_one_role, step_two_role = await _two_step_invitation(db_session, branch)
    first_approver = await _user_with_role(
        db_session, branch.id, role=step_one_role, extra_permission_codes=("invitations:approve",)
    )
    second_approver = await _user_with_role(
        db_session, branch.id, role=step_two_role, extra_permission_codes=("invitations:approve",)
    )

    approval_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )

    step_one = await _get_step(db_session, invitation.id, 1)
    token = issue_token(first_approver)
    await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )

    step_two = await _get_step(db_session, invitation.id, 2)
    token = issue_token(second_approver)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_two.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "approved"
    assert data["approvedAt"] is not None
    assert data["currentApprovalStep"] is None
    assert len(approval_calls) == 1


# --- Push notifications (add-invitation-push-notifications) -----------------


async def test_approve_step_non_final_admin_role_identified_step_sends_no_push(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    """specs/approvals/spec.md "Approving a step activates a role-identified
    step, sending no push" (exclude-admin-role-only-from-push) — approving
    step one activates step two, but step two is identified by the tenant's
    standard `admin` role, so no push is dispatched to anyone.
    """
    step_one_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"step-one-role-{uuid.uuid4().hex[:8]}", permissions=[]
    )
    admin_role = RoleFactory.build(id=uuid.uuid4(), name="admin", permissions=[])
    db_session.add_all([step_one_role, admin_role])
    await db_session.flush()

    invitation = _build_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.flush()
    db_session.add_all(
        [
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                step_order=1,
                approver_role_id=step_one_role.id,
                escalation_minutes=None,
                auto_approve_minutes=None,
            ),
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                step_order=2,
                approver_role_id=admin_role.id,
                escalation_minutes=None,
                auto_approve_minutes=None,
            ),
        ]
    )
    await db_session.commit()

    approver = await _user_with_role(
        db_session, branch.id, role=step_one_role, extra_permission_codes=("invitations:approve",)
    )

    user_calls: list[dict] = []
    role_calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        user_calls.append(kwargs)

    async def _fake_notify_role_at_branch(tenant_db, **kwargs):
        role_calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)
    monkeypatch.setattr(notifications_service, "notify_role_at_branch", _fake_notify_role_at_branch)

    token = issue_token(approver)
    step_one = await _get_step(db_session, invitation.id, 1)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert user_calls == []
    assert role_calls == []


async def test_approve_step_non_final_non_admin_role_identified_step_notifies_role(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    """specs/approvals/spec.md "Approving a step activates a non-Admin
    role-identified step" — a role-identified step for any role other than
    `admin` (e.g. this test's `step-two-role-*`) still dispatches a push to
    that role's holders at the invitation's branch.
    """
    invitation, step_one_role, step_two_role = await _two_step_invitation(db_session, branch)
    approver = await _user_with_role(
        db_session, branch.id, role=step_one_role, extra_permission_codes=("invitations:approve",)
    )

    role_calls: list[dict] = []

    async def _fake_notify_role_at_branch(tenant_db, **kwargs):
        role_calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_role_at_branch", _fake_notify_role_at_branch)

    token = issue_token(approver)
    step_one = await _get_step(db_session, invitation.id, 1)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert len(role_calls) == 1
    assert role_calls[0]["role_id"] == step_two_role.id
    assert role_calls[0]["branch_id"] == branch.id


async def test_approve_step_non_final_activates_host_identified_step_notifies_host(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    """specs/approvals/spec.md "Approving a role-identified step activates a
    host-identified step" — the host-only push path still fires when a role
    step's approval activates a *host*-identified next step.
    """
    step_one_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"step-one-role-{uuid.uuid4().hex[:8]}", permissions=[]
    )
    host = UserFactory.build(
        id=uuid.uuid4(),
        email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Step Two Host",
    )
    db_session.add_all([step_one_role, host])
    await db_session.flush()

    invitation = _build_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.flush()
    db_session.add_all(
        [
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                step_order=1,
                approver_role_id=step_one_role.id,
                escalation_minutes=None,
                auto_approve_minutes=None,
            ),
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                step_order=2,
                approver_role_id=None,
                approver_user_id=host.id,
                escalation_minutes=None,
                auto_approve_minutes=None,
            ),
        ]
    )
    await db_session.commit()

    approver = await _user_with_role(
        db_session, branch.id, role=step_one_role, extra_permission_codes=("invitations:approve",)
    )

    calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)

    token = issue_token(approver)
    step_one = await _get_step(db_session, invitation.id, 1)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    assert len(calls) == 1
    assert calls[0]["user_id"] == host.id


async def test_approve_step_last_step_does_not_double_notify(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    """specs/approvals/spec.md "Approving the last step does not double-
    notify via this requirement" — no next step is activated by the last
    step's approval, so `notify_step_approver` never fires for it; the
    invitation's own resolution outcome is instead notified by
    `invitations.service.approve_invitation`'s separate `notify_user` call
    (not under test here, and a no-op anyway since this invitation has no
    resolved host).
    """
    invitation, step_one_role, step_two_role = await _two_step_invitation(db_session, branch)
    first_approver = await _user_with_role(
        db_session, branch.id, role=step_one_role, extra_permission_codes=("invitations:approve",)
    )
    second_approver = await _user_with_role(
        db_session, branch.id, role=step_two_role, extra_permission_codes=("invitations:approve",)
    )

    calls: list[dict] = []

    async def _fake_notify_step_approver(tenant_db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_step_approver", _fake_notify_step_approver)
    monkeypatch.setattr(tasks.send_approval_notification, "delay", lambda **kw: None)

    step_one = await _get_step(db_session, invitation.id, 1)
    token = issue_token(first_approver)
    await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(calls) == 1  # step one's approval activated step two

    calls.clear()
    step_two = await _get_step(db_session, invitation.id, 2)
    token = issue_token(second_approver)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_two.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert calls == []  # last step approved — no next step to activate/notify


# --- Rejection is terminal ----------------------------------------------------


async def test_reject_step_denies_invitation_and_leaves_later_steps_pending(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    """invitation-multi-step-approval spec.md "Rejecting a middle step
    denies the invitation without evaluating later steps" — a 3-step
    workflow, step 2 rejected, step 3 must stay untouched.
    """
    role_one = RoleFactory.build(id=uuid.uuid4(), name="role-one", permissions=[])
    role_two = RoleFactory.build(id=uuid.uuid4(), name="role-two", permissions=[])
    role_three = RoleFactory.build(id=uuid.uuid4(), name="role-three", permissions=[])
    db_session.add_all([role_one, role_two, role_three])
    await db_session.flush()

    invitation = _build_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.flush()
    db_session.add_all(
        [
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                step_order=1,
                approver_role_id=role_one.id,
            ),
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                step_order=2,
                approver_role_id=role_two.id,
            ),
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                step_order=3,
                approver_role_id=role_three.id,
            ),
        ]
    )
    await db_session.commit()

    first_approver = await _user_with_role(
        db_session, branch.id, role=role_one, extra_permission_codes=("invitations:approve",)
    )
    second_approver = await _user_with_role(
        db_session, branch.id, role=role_two, extra_permission_codes=("invitations:approve",)
    )

    denial_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_denial_notification, "delay", lambda **kw: denial_calls.append(kw)
    )

    step_one = await _get_step(db_session, invitation.id, 1)
    token = issue_token(first_approver)
    await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )

    step_two = await _get_step(db_session, invitation.id, 2)
    token = issue_token(second_approver)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_two.id}/reject",
        json={"reason": "Not a valid visit purpose"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "denied"
    assert len(denial_calls) == 1

    step_two_after = await _get_step(db_session, invitation.id, 2)
    step_three_after = await _get_step(db_session, invitation.id, 3)
    assert step_two_after.status == "rejected"
    assert step_three_after.status == "pending"
    assert step_three_after.acted_at is None


async def test_reject_step_missing_reason_rejected(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    invitation, step_one_role, _ = await _two_step_invitation(db_session, branch)
    approver = await _user_with_role(
        db_session, branch.id, role=step_one_role, extra_permission_codes=("invitations:approve",)
    )
    step_one = await _get_step(db_session, invitation.id, 1)

    token = issue_token(approver)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/reject",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


# --- Ordering and identity guards --------------------------------------------


async def test_approve_step_out_of_order_rejected(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    invitation, _step_one_role, step_two_role = await _two_step_invitation(db_session, branch)
    approver = await _user_with_role(
        db_session, branch.id, role=step_two_role, extra_permission_codes=("invitations:approve",)
    )
    step_two = await _get_step(db_session, invitation.id, 2)

    token = issue_token(approver)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_two.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    unchanged = await _get_step(db_session, invitation.id, 2)
    assert unchanged.status == "pending"


async def test_approve_step_override_permission_cannot_skip_pending_earlier_step(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "A Step Cannot Be Delegated or Actioned While
    an Earlier Step Is Still Pending" — mirrors
    `test_approve_step_out_of_order_rejected` for an
    `invitations:approve-override` holder, who otherwise bypasses the
    role/host match entirely but still cannot approve a step ahead of a
    still-pending earlier one.
    """
    invitation, _step_one_role, _step_two_role = await _two_step_invitation(db_session, branch)
    override_role = _approve_permission_role(name=f"override-role-{uuid.uuid4().hex[:8]}")
    db_session.add(override_role)
    await db_session.flush()
    override_permission = await _get_or_create_permission(
        db_session, "invitations:approve-override"
    )
    override_role.permissions = [*override_role.permissions, override_permission]
    approver = await _user_with_role(db_session, branch.id, role=override_role)
    step_two = await _get_step(db_session, invitation.id, 2)

    token = issue_token(approver)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_two.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    unchanged = await _get_step(db_session, invitation.id, 2)
    assert unchanged.status == "pending"


async def test_approve_step_unknown_invitation_id_not_found(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    response = await client.post(
        f"/api/v1/invitations/{uuid.uuid4()}/approval-steps/{uuid.uuid4()}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_approve_step_unknown_step_id_not_found(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    invitation, step_one_role, _ = await _two_step_invitation(db_session, branch)
    approver = await _user_with_role(
        db_session, branch.id, role=step_one_role, extra_permission_codes=("invitations:approve",)
    )

    token = issue_token(approver)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{uuid.uuid4()}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_approve_step_belonging_to_different_invitation_not_found(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    invitation_one, step_one_role, _ = await _two_step_invitation(db_session, branch)
    invitation_two, _, _ = await _two_step_invitation(db_session, branch)
    approver = await _user_with_role(
        db_session, branch.id, role=step_one_role, extra_permission_codes=("invitations:approve",)
    )

    step_of_invitation_two = await _get_step(db_session, invitation_two.id, 1)
    token = issue_token(approver)
    response = await client.post(
        f"/api/v1/invitations/{invitation_one.id}/approval-steps/{step_of_invitation_two.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# --- Authorization: invitations:approve, role match, and override -----------


async def test_approve_step_requires_invitations_approve_permission(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    user_without_permissions: User,
    issue_token: Callable[[User], str],
) -> None:
    invitation, step_one_role, _ = await _two_step_invitation(db_session, branch)
    # `user_without_permissions` holds no role at all, so even if it were
    # somehow granted `step_one_role` it still lacks `invitations:approve`
    # — this asserts the permission dependency chain runs before the
    # role-match check ever gets a chance to grant access on role alone.
    branch_role = UserBranchRole(
        id=uuid.uuid4(),
        user_id=user_without_permissions.id,
        role=step_one_role,
        branch_id=branch.id,
    )
    db_session.add(branch_role)
    await db_session.commit()

    step_one = await _get_step(db_session, invitation.id, 1)
    token = issue_token(user_without_permissions)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    unchanged = await _get_step(db_session, invitation.id, 1)
    assert unchanged.status == "pending"


async def test_reject_step_requires_invitations_approve_permission(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    user_without_permissions: User,
    issue_token: Callable[[User], str],
) -> None:
    invitation, step_one_role, _ = await _two_step_invitation(db_session, branch)
    # `user_without_permissions` holds no role at all, so even if it were
    # somehow granted `step_one_role` it still lacks `invitations:approve`
    # — this asserts the permission dependency chain runs before the
    # role-match check ever gets a chance to grant access on role alone.
    branch_role = UserBranchRole(
        id=uuid.uuid4(),
        user_id=user_without_permissions.id,
        role=step_one_role,
        branch_id=branch.id,
    )
    db_session.add(branch_role)
    await db_session.commit()

    step_one = await _get_step(db_session, invitation.id, 1)
    token = issue_token(user_without_permissions)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/reject",
        json={"reason": "Not a valid visit purpose"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    unchanged = await _get_step(db_session, invitation.id, 1)
    assert unchanged.status == "pending"


async def test_approve_step_role_mismatch_without_override_rejected(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Caller with a non-matching role and no
    override is rejected" — holds `invitations:approve` via a *different*
    role than the one the current step's `approverRoleId` names.
    """
    invitation, step_one_role, _ = await _two_step_invitation(db_session, branch)
    wrong_role = _approve_permission_role(name="wrong-role")
    db_session.add(wrong_role)
    await db_session.flush()
    caller = await _user_with_role(db_session, branch.id, role=wrong_role)

    step_one = await _get_step(db_session, invitation.id, 1)
    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    unchanged = await _get_step(db_session, invitation.id, 1)
    assert unchanged.status == "pending"
    assert step_one_role.id != wrong_role.id


async def test_approve_step_matching_role_without_separate_approve_permission_rejected(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """The step's own `approverRoleId` role granting no permissions at all
    still can't act on it — `invitations:approve` is required independently
    of the role match (design.md Decision 4's two-part check, both halves
    mandatory).
    """
    invitation, step_one_role, _ = await _two_step_invitation(db_session, branch)
    caller = await _user_with_role(db_session, branch.id, role=step_one_role)

    step_one = await _get_step(db_session, invitation.id, 1)
    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_approve_step_override_permission_bypasses_role_mismatch(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Override permission bypasses the role-match
    check" — holds `invitations:approve` and `invitations:approve-override`
    via a role that does *not* match the current step's `approverRoleId`.
    """
    invitation, step_one_role, _ = await _two_step_invitation(db_session, branch)
    override_role = _approve_permission_role(name="override-role")
    db_session.add(override_role)
    await db_session.flush()
    caller = await _user_with_role(
        db_session,
        branch.id,
        role=override_role,
        extra_permission_codes=("invitations:approve-override",),
    )
    assert step_one_role.id != override_role.id

    step_one = await _get_step(db_session, invitation.id, 1)
    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    updated = await _get_step(db_session, invitation.id, 1)
    assert updated.status == "approved"
    assert updated.acted_by_user_id == caller.id


async def test_approve_step_company_wide_role_grant_matches_any_branch(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """A `UserBranchRole.branch_id IS NULL` grant of the step's approver
    role is company-wide, matching regardless of the invitation's own
    branch — mirrors `auth/models.py::User.has_permission`'s existing
    branch-or-company-wide semantics.
    """
    invitation, step_one_role, _ = await _two_step_invitation(db_session, branch)
    caller = await _user_with_role(
        db_session, None, role=step_one_role, extra_permission_codes=("invitations:approve",)
    )

    step_one = await _get_step(db_session, invitation.id, 1)
    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text


# --- Host-identified step authorization (add-approval-step-id-and-host-routing) --


async def test_approve_step_host_identified_matching_user_succeeds(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Caller matching the step's approver user
    succeeds" — the invitation's own host, granted `invitations:approve`,
    approves their own host-identified step.
    """
    invitation, host = await _host_step_invitation(db_session, branch)
    await _grant_approve_permission(db_session, host, branch.id)

    step_zero = await _get_step(db_session, invitation.id, 0)
    token = issue_token(host)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    updated = await _get_step(db_session, invitation.id, 0)
    assert updated.status == "approved"
    assert updated.acted_by_user_id == host.id


async def test_approve_step_host_identified_non_matching_user_without_override_rejected(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Caller who is not the step's approver user
    and lacks override is rejected" — a different user, holding
    `invitations:approve` but not matching the step's `approverUserId`.
    """
    invitation, _host = await _host_step_invitation(db_session, branch)
    other_role = _approve_permission_role(name="other-role")
    db_session.add(other_role)
    await db_session.flush()
    caller = await _user_with_role(db_session, branch.id, role=other_role)

    step_zero = await _get_step(db_session, invitation.id, 0)
    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    unchanged = await _get_step(db_session, invitation.id, 0)
    assert unchanged.status == "pending"


async def test_approve_step_host_identified_override_permission_bypasses_host_mismatch(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Override permission bypasses the role-match
    check" applies the same way to a host-identified step.
    """
    invitation, _host = await _host_step_invitation(db_session, branch)
    override_role = _approve_permission_role(name="override-role-host")
    db_session.add(override_role)
    await db_session.flush()
    caller = await _user_with_role(
        db_session,
        branch.id,
        role=override_role,
        extra_permission_codes=("invitations:approve-override",),
    )

    step_zero = await _get_step(db_session, invitation.id, 0)
    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    updated = await _get_step(db_session, invitation.id, 0)
    assert updated.status == "approved"


async def test_approve_step_host_identified_requires_invitations_approve_permission(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Caller lacking invitations:approve entirely
    is rejected regardless of role" — the host themself, with no
    `invitations:approve` grant at all, still can't act on their own
    host-identified step.
    """
    invitation, host = await _host_step_invitation(db_session, branch)

    step_zero = await _get_step(db_session, invitation.id, 0)
    token = issue_token(host)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    unchanged = await _get_step(db_session, invitation.id, 0)
    assert unchanged.status == "pending"


async def test_reject_step_host_identified_matching_user_denies_invitation(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """Same out-of-order/identity guards (specs/approvals/spec.md "Rejecting
    a Step Is Terminal and Denies the Invitation") apply to a
    host-identified current step, not just a role-identified one.
    """
    invitation, host = await _host_step_invitation(db_session, branch)
    await _grant_approve_permission(db_session, host, branch.id)

    step_zero = await _get_step(db_session, invitation.id, 0)
    token = issue_token(host)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/reject",
        json={"reason": "Not expected"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "denied"


# --- Delegation (invitation-relevant-to-me-and-delegation) -------------------


async def test_delegate_step_host_succeeds(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Host delegates the step following their
    own" — the delegation succeeds, the step stays `pending`, and the named
    user becomes the step's delegate.
    """
    invitation, host, step_one_role, _ = await _host_and_role_invitation(db_session, branch)
    await _grant_approve_permission(db_session, host, branch.id)
    delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    step_one = await _get_step(db_session, invitation.id, 1)

    token = issue_token(host)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    updated = await _get_step(db_session, invitation.id, 1)
    assert updated.status == "pending"
    assert updated.delegated_to_user_id == delegate.id
    assert updated.delegated_by_user_id == host.id
    assert updated.delegated_at is not None


async def test_delegate_step_non_host_caller_rejected(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Caller who is not the host is rejected" —
    holding `invitations:approve` is not enough; the caller must be the
    invitation's own host.
    """
    invitation, _host, step_one_role, _ = await _host_and_role_invitation(db_session, branch)
    other_role = _approve_permission_role(name="not-the-host")
    db_session.add(other_role)
    await db_session.flush()
    caller = await _user_with_role(db_session, branch.id, role=other_role)
    delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    step_one = await _get_step(db_session, invitation.id, 1)

    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    unchanged = await _get_step(db_session, invitation.id, 1)
    assert unchanged.delegated_to_user_id is None


async def test_delegate_step_before_host_step_approved_rejected(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Delegating before the host's own step is
    approved is rejected" — while `stepOrder` 0 is still `pending`,
    `stepOrder` 1 is not yet the invitation's current step at all.
    """
    invitation, host, step_one_role, _ = await _host_and_role_invitation(
        db_session, branch, host_step_status="pending", step_one_status="pending"
    )
    await _grant_approve_permission(db_session, host, branch.id)
    delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    step_one = await _get_step(db_session, invitation.id, 1)

    token = issue_token(host)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    unchanged = await _get_step(db_session, invitation.id, 1)
    assert unchanged.delegated_to_user_id is None


async def test_delegate_step_host_delegates_later_role_step_without_holding_its_role(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Host delegates a later role-identified step
    without holding its role" — the host's delegation privilege is a
    blanket one, independent of whether the host would otherwise be
    authorized to act on that specific step (design.md Decision 4).
    """
    invitation, host, _step_one_role, step_two_role = await _host_and_role_invitation(
        db_session,
        branch,
        host_step_status="approved",
        step_one_status="approved",
        extra_role_step=True,
    )
    await _grant_approve_permission(db_session, host, branch.id)
    assert step_two_role is not None
    delegate = await _user_with_role(db_session, branch.id, role=step_two_role)
    step_two = await _get_step(db_session, invitation.id, 2)

    token = issue_token(host)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_two.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    updated_step_two = await _get_step(db_session, invitation.id, 2)
    assert updated_step_two.delegated_to_user_id == delegate.id
    assert updated_step_two.delegated_by_user_id == host.id


async def test_delegate_step_caller_not_authorized_on_current_step_rejected(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Caller not currently authorized on the step
    is rejected" — a caller who is neither the invitation's host, a match
    for the current step's role, its current delegate, nor an override
    holder cannot delegate it.
    """
    invitation, _host, _step_one_role, step_two_role = await _host_and_role_invitation(
        db_session,
        branch,
        host_step_status="approved",
        step_one_status="approved",
        extra_role_step=True,
    )
    assert step_two_role is not None
    unrelated_role = _approve_permission_role(name=f"unrelated-caller-{uuid.uuid4().hex[:8]}")
    db_session.add(unrelated_role)
    await db_session.flush()
    caller = await _user_with_role(db_session, branch.id, role=unrelated_role)
    delegate = await _user_with_role(db_session, branch.id, role=step_two_role)
    step_two = await _get_step(db_session, invitation.id, 2)

    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_two.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    unchanged_step_two = await _get_step(db_session, invitation.id, 2)
    assert unchanged_step_two.delegated_to_user_id is None


async def test_delegate_step_host_delegates_own_step_zero_succeeds(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Host delegates their own step to another
    person" — `stepOrder` 0 is now delegable, generalized from the old
    host-only-next-step-only rule. The delegate must hold
    `invitations:approve` at the branch (a host-identified step has no
    role to match against).
    """
    invitation, host, _step_one_role, _ = await _host_and_role_invitation(
        db_session, branch, host_step_status="pending", step_one_status="pending"
    )
    await _grant_approve_permission(db_session, host, branch.id)
    unrelated_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"delegate-target-{uuid.uuid4().hex[:8]}", permissions=[]
    )
    db_session.add(unrelated_role)
    await db_session.flush()
    delegate = await _user_with_role(
        db_session,
        branch.id,
        role=unrelated_role,
        extra_permission_codes=("invitations:approve",),
    )
    step_zero = await _get_step(db_session, invitation.id, 0)

    token = issue_token(host)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    updated = await _get_step(db_session, invitation.id, 0)
    assert updated.status == "pending"
    assert updated.delegated_to_user_id == delegate.id
    assert updated.delegated_by_user_id == host.id


async def test_delegate_step_host_delegate_target_lacking_permission_rejected(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """A host-identified step's delegate must hold `invitations:approve` at
    the branch — there is no role to check instead, since the step itself
    names a person, not a role.
    """
    invitation, host, _step_one_role, _ = await _host_and_role_invitation(
        db_session, branch, host_step_status="pending", step_one_status="pending"
    )
    await _grant_approve_permission(db_session, host, branch.id)
    unrelated_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"no-approve-{uuid.uuid4().hex[:8]}", permissions=[]
    )
    db_session.add(unrelated_role)
    await db_session.flush()
    ineligible_delegate = await _user_with_role(db_session, branch.id, role=unrelated_role)
    step_zero = await _get_step(db_session, invitation.id, 0)

    token = issue_token(host)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/delegate",
        json={"delegateUserId": str(ineligible_delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    unchanged = await _get_step(db_session, invitation.id, 0)
    assert unchanged.delegated_to_user_id is None


async def test_delegate_step_role_holder_delegates_later_step_succeeds(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "A role-holder delegates a later step, not
    just the one after the host's" — any role-identified step, at any
    position, is delegable by whoever currently holds its role.
    """
    invitation, _host, _step_one_role, step_two_role = await _host_and_role_invitation(
        db_session,
        branch,
        host_step_status="approved",
        step_one_status="approved",
        extra_role_step=True,
    )
    assert step_two_role is not None
    caller = await _user_with_role(
        db_session, branch.id, role=step_two_role, extra_permission_codes=("invitations:approve",)
    )
    delegate = await _user_with_role(db_session, branch.id, role=step_two_role)
    step_two = await _get_step(db_session, invitation.id, 2)

    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_two.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    updated = await _get_step(db_session, invitation.id, 2)
    assert updated.delegated_to_user_id == delegate.id
    assert updated.delegated_by_user_id == caller.id


async def _reception_approved_two_step_invitation(
    db_session: AsyncSession, branch: Branch
) -> tuple[Invitation, User, Role]:
    """A `submitted` invitation whose role-identified `stepOrder` 0
    ownership step has already been approved directly (not delegated) by a
    specific owning-role user, with a `stepOrder` 1 step — role-identified
    for a *different* role the approver does not hold — now current and
    pending. Backs the "previous-step-approver may delegate the next step"
    tests (reception-retains-visibility-and-delegation-after-own-step).
    Returns `(invitation, step_zero_approver, step_one_role)`.
    """
    suffix = uuid.uuid4().hex[:8]
    owning_role = RoleFactory.build(id=uuid.uuid4(), name=f"owning-role-{suffix}", permissions=[])
    step_one_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"step-one-role-{suffix}", permissions=[]
    )
    db_session.add_all([owning_role, step_one_role])
    await db_session.flush()

    invitation = _build_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.flush()

    step_zero_approver = await _user_with_role(
        db_session, branch.id, role=owning_role, extra_permission_codes=("invitations:approve",)
    )

    acted_now = datetime.now(UTC)
    db_session.add_all(
        [
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                step_order=0,
                approver_role_id=owning_role.id,
                approver_user_id=None,
                status="approved",
                acted_by_user_id=step_zero_approver.id,
                acted_at=acted_now,
            ),
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                step_order=1,
                approver_role_id=step_one_role.id,
                status="pending",
            ),
        ]
    )
    await db_session.commit()
    return invitation, step_zero_approver, step_one_role


async def test_delegate_step_previous_step_approver_delegates_next_step_succeeds(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "The previous step's approver delegates the
    next step to the workflow-configured role"
    (reception-retains-visibility-and-delegation-after-own-step) — Reception,
    having approved the ownership step directly rather than delegating it,
    may still route the next, differently-role-identified step to whoever
    the workflow configures for it.
    """
    invitation, step_zero_approver, step_one_role = await _reception_approved_two_step_invitation(
        db_session, branch
    )
    delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    step_one = await _get_step(db_session, invitation.id, 1)

    token = issue_token(step_zero_approver)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    updated = await _get_step(db_session, invitation.id, 1)
    assert updated.delegated_to_user_id == delegate.id
    assert updated.delegated_by_user_id == step_zero_approver.id


async def test_delegate_step_previous_step_approver_privilege_does_not_chain_back_further(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Only the step's own approver, not an earlier
    one, gets the previous-step delegation privilege" — clause (d) only
    reaches back exactly one step, so `stepOrder` 0's approver gains no
    delegation authority over `stepOrder` 2 once `stepOrder` 1 has been
    approved by someone else.
    """
    invitation, step_zero_approver, step_one_role = await _reception_approved_two_step_invitation(
        db_session, branch
    )
    step_two_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"step-two-role-{uuid.uuid4().hex[:8]}", permissions=[]
    )
    db_session.add(step_two_role)
    await db_session.flush()
    db_session.add(
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            step_order=2,
            approver_role_id=step_two_role.id,
            status="pending",
        )
    )
    await db_session.commit()

    step_one_approver = await _user_with_role(
        db_session, branch.id, role=step_one_role, extra_permission_codes=("invitations:approve",)
    )
    step_one = await _get_step(db_session, invitation.id, 1)
    await InvitationApprovalStepRepository(db_session).approve_if_pending(
        step_one.id, user_id=step_one_approver.id
    )
    await db_session.commit()

    delegate = await _user_with_role(db_session, branch.id, role=step_two_role)
    step_two = await _get_step(db_session, invitation.id, 2)
    await _grant_approve_permission(db_session, step_zero_approver, branch.id)

    token = issue_token(step_zero_approver)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_two.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    unchanged = await _get_step(db_session, invitation.id, 2)
    assert unchanged.delegated_to_user_id is None


async def test_delegate_step_later_step_also_resolves_and_updates_host(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Delegating a later step also updates the
    resolved host" (reception-retains-visibility-and-delegation-after-own-
    step) — extended from the original `stepOrder`-0-only rule, delegating
    *any* step resolves/updates the invitation's `hostId`.
    """
    invitation, step_one_role, step_two_role = await _two_step_invitation(db_session, branch)
    assert invitation.host_id is None
    caller = await _user_with_role(
        db_session, branch.id, role=step_one_role, extra_permission_codes=("invitations:approve",)
    )
    delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    step_one = await _get_step(db_session, invitation.id, 1)

    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["hostId"] == str(delegate.id)

    refreshed = (
        await db_session.execute(select(Invitation).where(Invitation.id == invitation.id))
    ).scalar_one()
    assert refreshed.host_id == delegate.id
    assert refreshed.host_name_or_email == delegate.full_name


async def test_delegate_step_current_delegate_re_delegates_chaining(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "A delegate re-delegates the step onward,
    chaining the delegation" — the current delegate, not just the original
    host, may hand the step to a third person.
    """
    invitation, host, step_one_role, _ = await _host_and_role_invitation(db_session, branch)
    await _grant_approve_permission(db_session, host, branch.id)
    first_delegate = await _user_with_role(
        db_session, branch.id, role=step_one_role, extra_permission_codes=("invitations:approve",)
    )
    second_delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    step_one = await _get_step(db_session, invitation.id, 1)

    host_token = issue_token(host)
    first_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(first_delegate.id)},
        headers={"Authorization": f"Bearer {host_token}"},
    )
    assert first_response.status_code == 200, first_response.text

    delegate_token = issue_token(first_delegate)
    second_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(second_delegate.id)},
        headers={"Authorization": f"Bearer {delegate_token}"},
    )
    assert second_response.status_code == 200, second_response.text

    updated = await _get_step(db_session, invitation.id, 1)
    assert updated.delegated_to_user_id == second_delegate.id
    assert updated.delegated_by_user_id == first_delegate.id


async def test_delegate_step_override_permission_holder_delegates_any_step(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Override-permission holder delegates any
    step regardless of role or host match".
    """
    invitation, _host, _step_one_role, step_two_role = await _host_and_role_invitation(
        db_session,
        branch,
        host_step_status="approved",
        step_one_status="approved",
        extra_role_step=True,
    )
    assert step_two_role is not None
    unrelated_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"override-caller-{uuid.uuid4().hex[:8]}", permissions=[]
    )
    db_session.add(unrelated_role)
    await db_session.flush()
    override_caller = await _user_with_role(
        db_session,
        branch.id,
        role=unrelated_role,
        extra_permission_codes=("invitations:approve", "invitations:approve-override"),
    )
    delegate = await _user_with_role(db_session, branch.id, role=step_two_role)
    step_two = await _get_step(db_session, invitation.id, 2)

    token = issue_token(override_caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_two.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    updated = await _get_step(db_session, invitation.id, 2)
    assert updated.delegated_to_user_id == delegate.id
    assert updated.delegated_by_user_id == override_caller.id


async def test_delegate_step_delegate_lacking_role_rejected(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Delegating to a person who does not hold
    the step's role is rejected".
    """
    invitation, host, _step_one_role, _ = await _host_and_role_invitation(db_session, branch)
    await _grant_approve_permission(db_session, host, branch.id)
    unrelated_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"unrelated-{uuid.uuid4().hex[:8]}", permissions=[]
    )
    db_session.add(unrelated_role)
    await db_session.flush()
    ineligible_delegate = await _user_with_role(db_session, branch.id, role=unrelated_role)
    step_one = await _get_step(db_session, invitation.id, 1)

    token = issue_token(host)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(ineligible_delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    unchanged = await _get_step(db_session, invitation.id, 1)
    assert unchanged.delegated_to_user_id is None


async def test_delegate_step_host_re_delegates_an_already_delegated_step(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """The host's delegation privilege is blanket and persists even after
    the step has already been delegated to someone else — the host stays
    in control of routing their own invitation's approval throughout, not
    just at the moment a step first becomes current (design.md Decision 4).
    """
    invitation, host, step_one_role, _ = await _host_and_role_invitation(db_session, branch)
    await _grant_approve_permission(db_session, host, branch.id)
    first_delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    second_delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    step_one = await _get_step(db_session, invitation.id, 1)
    token = issue_token(host)

    first_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(first_delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first_response.status_code == 200, first_response.text

    second_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(second_delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert second_response.status_code == 200, second_response.text

    updated = await _get_step(db_session, invitation.id, 1)
    assert updated.delegated_to_user_id == second_delegate.id
    assert updated.delegated_by_user_id == host.id


async def test_delegate_step_already_acted_on_rejected(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Delegating an already-acted-on step is
    rejected" — once `stepOrder` 1 is itself `approved`, it is no longer
    the invitation's current step (there being no `stepOrder` 2 here), so
    it cannot be named at all.
    """
    invitation, host, step_one_role, _ = await _host_and_role_invitation(
        db_session, branch, host_step_status="approved", step_one_status="approved"
    )
    await _grant_approve_permission(db_session, host, branch.id)
    delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    step_one = await _get_step(db_session, invitation.id, 1)

    token = issue_token(host)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


async def test_delegate_step_alone_does_not_advance_workflow(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Delegation alone does not advance the
    workflow".
    """
    invitation, host, step_one_role, _ = await _host_and_role_invitation(db_session, branch)
    await _grant_approve_permission(db_session, host, branch.id)
    delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    step_one = await _get_step(db_session, invitation.id, 1)

    token = issue_token(host)
    await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )

    await db_session.refresh(invitation)
    unchanged = await _get_step(db_session, invitation.id, 1)
    assert unchanged.status == "pending"
    assert invitation.status == "submitted"


async def test_delegate_step_non_delegate_role_holder_cannot_act(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Caller matching the step's delegate
    succeeds regardless of their assigned role" / "Caller holding the
    step's role but not matching its delegate is rejected" — once a step
    has a delegate, general role membership stops being a second valid
    path in.
    """
    invitation, host, step_one_role, _ = await _host_and_role_invitation(db_session, branch)
    await _grant_approve_permission(db_session, host, branch.id)
    delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    other_role_holder = await _user_with_role(
        db_session, branch.id, role=step_one_role, extra_permission_codes=("invitations:approve",)
    )
    step_one = await _get_step(db_session, invitation.id, 1)

    host_token = issue_token(host)
    await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {host_token}"},
    )

    other_holder_token = issue_token(other_role_holder)
    rejected_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {other_holder_token}"},
    )
    assert rejected_response.status_code == 403

    delegate_token = issue_token(delegate)
    accepted_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {delegate_token}"},
    )
    assert accepted_response.status_code == 200, accepted_response.text


async def test_delegate_step_override_permission_bypasses_delegate_match(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Override permission bypasses the role-match
    check" applies to a delegated step exactly as it does to a role- or
    host-identified one.
    """
    invitation, host, step_one_role, _ = await _host_and_role_invitation(db_session, branch)
    await _grant_approve_permission(db_session, host, branch.id)
    delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    step_one = await _get_step(db_session, invitation.id, 1)

    host_token = issue_token(host)
    await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {host_token}"},
    )

    override_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"delegate-override-role-{uuid.uuid4().hex[:8]}", permissions=[]
    )
    db_session.add(override_role)
    await db_session.flush()
    override_caller = await _user_with_role(
        db_session,
        branch.id,
        role=override_role,
        extra_permission_codes=("invitations:approve", "invitations:approve-override"),
    )

    override_token = issue_token(override_caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {override_token}"},
    )
    assert response.status_code == 200, response.text


async def test_delegate_step_delegate_approving_last_step_finalizes_invitation(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    """specs/approvals/spec.md "Delegate action finalizes the workflow the
    same as any other last step" — a 2-level (host + role) workflow, so
    `stepOrder` 1 is also the last step.
    """
    invitation, host, step_one_role, _ = await _host_and_role_invitation(db_session, branch)
    await _grant_approve_permission(db_session, host, branch.id)
    delegate = await _user_with_role(
        db_session, branch.id, role=step_one_role, extra_permission_codes=("invitations:approve",)
    )
    step_one = await _get_step(db_session, invitation.id, 1)

    approval_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_notification, "delay", lambda **kw: approval_calls.append(kw)
    )

    host_token = issue_token(host)
    await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {host_token}"},
    )

    delegate_token = issue_token(delegate)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/approve",
        headers={"Authorization": f"Bearer {delegate_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "approved"
    assert len(approval_calls) == 1


async def test_delegate_step_requires_invitations_approve_permission(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "Caller lacking invitations:approve entirely
    is rejected regardless of role" applies to delegation too — even the
    host, with no `invitations:approve` grant at all, cannot delegate.
    """
    invitation, host, step_one_role, _ = await _host_and_role_invitation(db_session, branch)
    delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    step_one = await _get_step(db_session, invitation.id, 1)

    token = issue_token(host)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    unchanged = await _get_step(db_session, invitation.id, 1)
    assert unchanged.delegated_to_user_id is None


# --- Ownership step (stepOrder 0) delegation (role-based-invitation-workflow) --


async def _role_owned_invitation(
    db_session: AsyncSession, branch: Branch
) -> tuple[Invitation, Role]:
    """A `submitted` invitation with a role-identified `stepOrder` 0
    ownership step — the shape every newly submitted invitation now gets
    (replacing the old host-identified-at-creation step). No host is
    resolved yet (`Invitation.host_id` is null). Returns
    `(invitation, owning_role)`.
    """
    owning_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"owning-role-{uuid.uuid4().hex[:8]}", permissions=[]
    )
    db_session.add(owning_role)
    await db_session.flush()

    invitation = _build_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.flush()
    db_session.add(
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            step_order=0,
            approver_role_id=owning_role.id,
            approver_user_id=None,
        )
    )
    await db_session.commit()
    return invitation, owning_role


async def test_delegate_ownership_step_to_non_role_holder_succeeds(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "A holder of the owning role delegates the
    ownership step to the real host" — the named delegate need not hold the
    step's own `approverRoleId`, only `invitations:approve` at the branch,
    since the real host is normally not a front-office employee.
    """
    invitation, owning_role = await _role_owned_invitation(db_session, branch)
    caller = await _user_with_role(
        db_session, branch.id, role=owning_role, extra_permission_codes=("invitations:approve",)
    )
    delegate_permission = await _get_or_create_permission(db_session, "invitations:approve")
    delegate_role = RoleFactory.build(
        id=uuid.uuid4(), name="real-host-role", permissions=[delegate_permission]
    )
    db_session.add(delegate_role)
    await db_session.flush()
    delegate = await _user_with_role(db_session, branch.id, role=delegate_role)
    step_zero = await _get_step(db_session, invitation.id, 0)

    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    updated = await _get_step(db_session, invitation.id, 0)
    assert updated.status == "pending"
    assert updated.delegated_to_user_id == delegate.id


async def test_approve_ownership_step_directly_succeeds_and_resolves_host(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """The `stepOrder` 0 ownership step is a plain role-identified step —
    its owning-role holder (e.g. `reception`) may approve it directly,
    exactly as they could delegate it. `_role_owned_invitation` snapshots
    only this single step (a single-step, reception-only workflow), so
    there is no later step through which a real host could ever be
    delegated — approving it directly resolves the invitation's `hostId`/
    `hostNameOrEmail` to the approving caller, the same as delegating would
    (see "Approving the Only Step of a Single-Step Workflow Also Resolves
    the Invitation's Host"), so the approval-confirmation email can name a
    real point of contact instead of falling back to the front desk.
    """
    invitation, owning_role = await _role_owned_invitation(db_session, branch)
    caller = await _user_with_role(
        db_session, branch.id, role=owning_role, extra_permission_codes=("invitations:approve",)
    )
    step_zero = await _get_step(db_session, invitation.id, 0)

    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["hostId"] == str(caller.id)

    await db_session.refresh(invitation)
    assert invitation.host_id == caller.id
    assert invitation.host_name_or_email == caller.full_name

    updated = await _get_step(db_session, invitation.id, 0)
    assert updated.status == "approved"


async def test_approve_ownership_step_directly_leaves_host_unresolved_when_multi_step(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """The single-step host-resolution exception above does NOT apply once
    the category configured more than one step: approving the
    host-nomination step directly in a multi-step workflow still leaves
    `hostId` unresolved — only `delegate` (of this step or a later one)
    resolves the host in that case.
    """
    invitation, owning_role = await _role_owned_invitation(db_session, branch)
    step_one_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"next-flow-role-{uuid.uuid4().hex[:8]}", permissions=[]
    )
    db_session.add(step_one_role)
    await db_session.flush()
    db_session.add(
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            step_order=1,
            approver_role_id=step_one_role.id,
        )
    )
    await db_session.commit()

    caller = await _user_with_role(
        db_session, branch.id, role=owning_role, extra_permission_codes=("invitations:approve",)
    )
    step_zero = await _get_step(db_session, invitation.id, 0)

    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["hostId"] is None

    updated = await _get_step(db_session, invitation.id, 0)
    assert updated.status == "approved"


async def test_approve_ownership_step_after_delegation_succeeds(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """Once the ownership step has been delegated to the real host, that
    delegate approves it normally — the delegate-only rule only blocks the
    undelegated owning-role-holder path.
    """
    invitation, owning_role = await _role_owned_invitation(db_session, branch)
    caller = await _user_with_role(
        db_session, branch.id, role=owning_role, extra_permission_codes=("invitations:approve",)
    )
    delegate_permission = await _get_or_create_permission(db_session, "invitations:approve")
    delegate_role = RoleFactory.build(
        id=uuid.uuid4(), name="real-host-role-approve", permissions=[delegate_permission]
    )
    db_session.add(delegate_role)
    await db_session.flush()
    delegate = await _user_with_role(db_session, branch.id, role=delegate_role)
    step_zero = await _get_step(db_session, invitation.id, 0)

    caller_token = issue_token(caller)
    delegate_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {caller_token}"},
    )
    assert delegate_response.status_code == 200, delegate_response.text

    delegate_token = issue_token(delegate)
    approve_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/approve",
        headers={"Authorization": f"Bearer {delegate_token}"},
    )
    assert approve_response.status_code == 200, approve_response.text

    updated = await _get_step(db_session, invitation.id, 0)
    assert updated.status == "approved"
    assert updated.acted_by_user_id == delegate.id


async def test_delegate_ownership_step_alone_does_not_unlock_next_step_for_delegation(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "A Step Cannot Be Delegated or Actioned While
    an Earlier Step Is Still Pending" — delegating `stepOrder` 0 resolves
    the invitation's host but leaves the step `pending`, so `stepOrder` 1
    is not yet current; even the newly-resolved host cannot delegate it.
    """
    invitation, owning_role = await _role_owned_invitation(db_session, branch)
    step_one_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"next-flow-role-{uuid.uuid4().hex[:8]}", permissions=[]
    )
    db_session.add(step_one_role)
    await db_session.flush()
    db_session.add(
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            step_order=1,
            approver_role_id=step_one_role.id,
        )
    )
    await db_session.commit()

    caller = await _user_with_role(
        db_session, branch.id, role=owning_role, extra_permission_codes=("invitations:approve",)
    )
    delegate_permission = await _get_or_create_permission(db_session, "invitations:approve")
    delegate_role = RoleFactory.build(
        id=uuid.uuid4(),
        name=f"real-host-role-{uuid.uuid4().hex[:8]}",
        permissions=[delegate_permission],
    )
    db_session.add(delegate_role)
    await db_session.flush()
    host = await _user_with_role(db_session, branch.id, role=delegate_role)
    step_zero = await _get_step(db_session, invitation.id, 0)

    caller_token = issue_token(caller)
    delegate_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/delegate",
        json={"delegateUserId": str(host.id)},
        headers={"Authorization": f"Bearer {caller_token}"},
    )
    assert delegate_response.status_code == 200, delegate_response.text
    assert delegate_response.json()["data"]["hostId"] == str(host.id)

    step_one = await _get_step(db_session, invitation.id, 1)
    next_delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    host_token = issue_token(host)
    next_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(next_delegate.id)},
        headers={"Authorization": f"Bearer {host_token}"},
    )
    assert next_response.status_code == 409

    unchanged_step_one = await _get_step(db_session, invitation.id, 1)
    assert unchanged_step_one.delegated_to_user_id is None
    unchanged_invitation = (
        await db_session.execute(select(Invitation).where(Invitation.id == invitation.id))
    ).scalar_one()
    assert unchanged_invitation.host_id == host.id


async def test_delegate_step_override_permission_cannot_skip_pending_earlier_step(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "A Step Cannot Be Delegated or Actioned While
    an Earlier Step Is Still Pending" — an `invitations:approve-override`
    holder still cannot delegate a step that is not yet current, even
    though override otherwise bypasses the role/host/delegate match.
    """
    invitation, _owning_role = await _role_owned_invitation(db_session, branch)
    step_one_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"next-flow-role-{uuid.uuid4().hex[:8]}", permissions=[]
    )
    db_session.add(step_one_role)
    await db_session.flush()
    db_session.add(
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            step_order=1,
            approver_role_id=step_one_role.id,
        )
    )
    await db_session.commit()

    override_role = _approve_permission_role(name=f"override-role-{uuid.uuid4().hex[:8]}")
    db_session.add(override_role)
    await db_session.flush()
    override_permission = await _get_or_create_permission(
        db_session, "invitations:approve-override"
    )
    override_role.permissions = [*override_role.permissions, override_permission]
    caller = await _user_with_role(db_session, branch.id, role=override_role)
    delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    step_one = await _get_step(db_session, invitation.id, 1)

    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    unchanged = await _get_step(db_session, invitation.id, 1)
    assert unchanged.delegated_to_user_id is None


async def test_delegate_step_role_holder_cannot_skip_pending_earlier_step(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "A Step Cannot Be Delegated or Actioned While
    an Earlier Step Is Still Pending" — holding the target step's own
    `approverRoleId` role does not bypass the ordering guarantee either.
    """
    invitation, _owning_role = await _role_owned_invitation(db_session, branch)
    step_one_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"next-flow-role-{uuid.uuid4().hex[:8]}", permissions=[]
    )
    db_session.add(step_one_role)
    await db_session.flush()
    db_session.add(
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            step_order=1,
            approver_role_id=step_one_role.id,
        )
    )
    await db_session.commit()

    caller = await _user_with_role(
        db_session,
        branch.id,
        role=step_one_role,
        extra_permission_codes=("invitations:approve",),
    )
    delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    step_one = await _get_step(db_session, invitation.id, 1)

    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    unchanged = await _get_step(db_session, invitation.id, 1)
    assert unchanged.delegated_to_user_id is None


async def test_delegate_step_role_and_override_succeed_once_earlier_step_approved(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """specs/approvals/spec.md "A Step Cannot Be Delegated or Actioned While
    an Earlier Step Is Still Pending" — positive control: once `stepOrder` 0
    is actually approved (by its owning-role holder, without ever
    delegating it), `stepOrder` 1 becomes current and is delegable by both
    its own role-holder and an override-permission holder, confirming the
    409s above are about ordering, not unrelated authorization failures.
    """
    invitation, owning_role = await _role_owned_invitation(db_session, branch)
    step_one_role = RoleFactory.build(
        id=uuid.uuid4(), name=f"next-flow-role-{uuid.uuid4().hex[:8]}", permissions=[]
    )
    db_session.add(step_one_role)
    await db_session.flush()
    db_session.add(
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            step_order=1,
            approver_role_id=step_one_role.id,
        )
    )
    await db_session.commit()

    owning_holder = await _user_with_role(
        db_session, branch.id, role=owning_role, extra_permission_codes=("invitations:approve",)
    )
    step_zero = await _get_step(db_session, invitation.id, 0)
    owning_token = issue_token(owning_holder)
    approve_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/approve",
        headers={"Authorization": f"Bearer {owning_token}"},
    )
    assert approve_response.status_code == 200, approve_response.text

    step_one = await _get_step(db_session, invitation.id, 1)
    role_delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    role_holder = await _user_with_role(
        db_session,
        branch.id,
        role=step_one_role,
        extra_permission_codes=("invitations:approve",),
    )
    role_token = issue_token(role_holder)
    role_response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_one.id}/delegate",
        json={"delegateUserId": str(role_delegate.id)},
        headers={"Authorization": f"Bearer {role_token}"},
    )
    assert role_response.status_code == 200, role_response.text


async def test_delegate_ownership_step_lacking_approve_permission_rejected(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """The relaxed "no role required" rule for `stepOrder` 0 does not waive
    `invitations:approve` itself — a named delegate without it is still
    rejected.
    """
    invitation, owning_role = await _role_owned_invitation(db_session, branch)
    caller = await _user_with_role(
        db_session, branch.id, role=owning_role, extra_permission_codes=("invitations:approve",)
    )
    no_permission_role = RoleFactory.build(id=uuid.uuid4(), name="no-permission-role")
    db_session.add(no_permission_role)
    await db_session.flush()
    delegate = await _user_with_role(db_session, branch.id, role=no_permission_role)
    step_zero = await _get_step(db_session, invitation.id, 0)

    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    unchanged = await _get_step(db_session, invitation.id, 0)
    assert unchanged.delegated_to_user_id is None


async def test_delegate_ownership_step_resolves_invitation_host_and_notifies(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    """specs/approvals/spec.md "Delegating the Ownership Step Also Resolves
    the Invitation's Host" — the invitation's `hostId`/`hostNameOrEmail` are
    set to the delegate, and they're notified (push + email), which
    delegation dispatches nothing for today.
    """
    invitation, owning_role = await _role_owned_invitation(db_session, branch)
    caller = await _user_with_role(
        db_session, branch.id, role=owning_role, extra_permission_codes=("invitations:approve",)
    )
    delegate_permission = await _get_or_create_permission(db_session, "invitations:approve")
    delegate_role = RoleFactory.build(
        id=uuid.uuid4(), name="real-host-role-2", permissions=[delegate_permission]
    )
    db_session.add(delegate_role)
    await db_session.flush()
    delegate = await _user_with_role(db_session, branch.id, role=delegate_role)
    step_zero = await _get_step(db_session, invitation.id, 0)

    push_calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        push_calls.append(kwargs)

    email_calls: list[dict] = []
    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)
    monkeypatch.setattr(
        tasks.send_host_creation_notification, "delay", lambda **kw: email_calls.append(kw)
    )

    token = issue_token(caller)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/delegate",
        json={"delegateUserId": str(delegate.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["hostId"] == str(delegate.id)

    await db_session.refresh(invitation)
    assert invitation.host_id == delegate.id
    assert invitation.host_name_or_email == delegate.full_name
    assert len(push_calls) == 1
    assert push_calls[0]["user_id"] == delegate.id
    assert len(email_calls) == 1
    assert email_calls[0]["host_id"] == str(delegate.id)


async def test_redelegate_ownership_step_updates_resolved_host(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """Re-delegating an already-delegated ownership step updates the
    invitation's resolved host to the new delegate. Once step 0 is
    delegated, only the resolved host themselves (or an override-permission
    holder) may re-delegate it — the original front-office caller no longer
    qualifies (their role-match no longer applies once a delegate is
    assigned, and they are not the resolved host) — so the second
    delegation here is issued by `first_delegate`, not the original caller.
    """
    invitation, owning_role = await _role_owned_invitation(db_session, branch)
    caller = await _user_with_role(
        db_session, branch.id, role=owning_role, extra_permission_codes=("invitations:approve",)
    )
    delegate_permission = await _get_or_create_permission(db_session, "invitations:approve")
    delegate_role = RoleFactory.build(
        id=uuid.uuid4(), name="real-host-role-3", permissions=[delegate_permission]
    )
    db_session.add(delegate_role)
    await db_session.flush()
    first_delegate = await _user_with_role(db_session, branch.id, role=delegate_role)
    second_delegate = await _user_with_role(db_session, branch.id, role=delegate_role)
    step_zero = await _get_step(db_session, invitation.id, 0)

    caller_token = issue_token(caller)
    await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/delegate",
        json={"delegateUserId": str(first_delegate.id)},
        headers={"Authorization": f"Bearer {caller_token}"},
    )
    host_token = issue_token(first_delegate)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/delegate",
        json={"delegateUserId": str(second_delegate.id)},
        headers={"Authorization": f"Bearer {host_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["hostId"] == str(second_delegate.id)

    await db_session.refresh(invitation)
    assert invitation.host_id == second_delegate.id


async def test_redelegate_ownership_step_notifies_only_new_host(
    client: AsyncClient,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
    monkeypatch,
) -> None:
    """Re-delegating an already-delegated ownership step notifies only the
    newly assigned host — the previous delegate receives no notification for
    a re-delegation that supersedes them. Same scenario as
    `test_redelegate_ownership_step_updates_resolved_host`, extended with
    notification-dispatch assertions (`design.md`'s Decisions: re-delegation
    edge case is what this task group actually needed to add).
    """
    invitation, owning_role = await _role_owned_invitation(db_session, branch)
    caller = await _user_with_role(
        db_session, branch.id, role=owning_role, extra_permission_codes=("invitations:approve",)
    )
    delegate_permission = await _get_or_create_permission(db_session, "invitations:approve")
    delegate_role = RoleFactory.build(
        id=uuid.uuid4(), name="real-host-role-4", permissions=[delegate_permission]
    )
    db_session.add(delegate_role)
    await db_session.flush()
    first_delegate = await _user_with_role(db_session, branch.id, role=delegate_role)
    second_delegate = await _user_with_role(db_session, branch.id, role=delegate_role)
    step_zero = await _get_step(db_session, invitation.id, 0)

    caller_token = issue_token(caller)
    await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/delegate",
        json={"delegateUserId": str(first_delegate.id)},
        headers={"Authorization": f"Bearer {caller_token}"},
    )

    push_calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        push_calls.append(kwargs)

    email_calls: list[dict] = []
    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)
    monkeypatch.setattr(
        tasks.send_host_creation_notification, "delay", lambda **kw: email_calls.append(kw)
    )

    host_token = issue_token(first_delegate)
    response = await client.post(
        f"/api/v1/invitations/{invitation.id}/approval-steps/{step_zero.id}/delegate",
        json={"delegateUserId": str(second_delegate.id)},
        headers={"Authorization": f"Bearer {host_token}"},
    )
    assert response.status_code == 200, response.text

    assert len(push_calls) == 1
    assert push_calls[0]["user_id"] == second_delegate.id
    assert len(email_calls) == 1
    assert email_calls[0]["host_id"] == str(second_delegate.id)


# --- Tenant isolation (testing-standards.md §2) ------------------------------


async def test_invitation_approval_step_tenant_schema_isolation(
    branch: Branch,
    db_session: AsyncSession,
    make_tenant_schema: Callable,
    open_tenant_session,
) -> None:
    """A step id that exists in one tenant's schema must not resolve through
    a session bound to another tenant's schema — same isolation guarantee
    every other `TenantScopedRepository` query relies on
    (`database-architecture.md` §2), exercised directly at the repository
    layer per testing-standards.md §3's "unit-style" tier.
    """
    invitation, step_one_role, _ = await _two_step_invitation(db_session, branch)
    step_one = await _get_step(db_session, invitation.id, 1)

    other_schema = "tenant_other_approvals_test"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        found = await InvitationApprovalStepRepository(other_session).get_by_id_for_invitation(
            invitation.id, step_one.id
        )
        assert found is None

    found_in_own_schema = await InvitationApprovalStepRepository(
        db_session
    ).get_by_id_for_invitation(invitation.id, step_one.id)
    assert found_in_own_schema is not None


async def test_host_identified_approval_step_tenant_schema_isolation(
    branch: Branch,
    db_session: AsyncSession,
    make_tenant_schema: Callable,
    open_tenant_session,
) -> None:
    """Same isolation guarantee as
    `test_invitation_approval_step_tenant_schema_isolation`, for a
    host-identified (`approver_user_id` set) step.
    """
    invitation, _host = await _host_step_invitation(db_session, branch)
    step_zero = await _get_step(db_session, invitation.id, 0)

    other_schema = "tenant_other_approvals_host_test"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        found = await InvitationApprovalStepRepository(other_session).get_by_id_for_invitation(
            invitation.id, step_zero.id
        )
        assert found is None

    found_in_own_schema = await InvitationApprovalStepRepository(
        db_session
    ).get_by_id_for_invitation(invitation.id, step_zero.id)
    assert found_in_own_schema is not None


async def test_delegate_step_tenant_schema_isolation(
    branch: Branch,
    db_session: AsyncSession,
    make_tenant_schema: Callable,
    open_tenant_session,
) -> None:
    """Same isolation guarantee as
    `test_invitation_approval_step_tenant_schema_isolation`, for a step
    that has been delegated — a delegation call against one tenant's
    invitation/step id must not resolve through a session bound to another
    tenant's schema, the same 404 an unknown id already gets.
    """
    invitation, host, step_one_role, _ = await _host_and_role_invitation(db_session, branch)
    delegate = await _user_with_role(db_session, branch.id, role=step_one_role)
    step_one = await _get_step(db_session, invitation.id, 1)
    await InvitationApprovalStepRepository(db_session).delegate_if_eligible(
        step_one.id, delegated_to_user_id=delegate.id, delegated_by_user_id=host.id
    )
    await db_session.commit()

    other_schema = "tenant_other_approvals_delegate_test"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        found = await InvitationApprovalStepRepository(other_session).get_by_id_for_invitation(
            invitation.id, step_one.id
        )
        assert found is None

    found_in_own_schema = await InvitationApprovalStepRepository(
        db_session
    ).get_by_id_for_invitation(invitation.id, step_one.id)
    assert found_in_own_schema is not None
    assert found_in_own_schema.delegated_to_user_id == delegate.id


# --- Unconditional ownership step (role-based-invitation-workflow) ---------


async def test_category_with_no_active_rules_creates_only_the_ownership_step(
    tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """specs/approvals/spec.md "A category with no active rules still
    snapshots the ownership step" — replaces the old "creates no steps"
    behavior: every submitted invitation now gets at least the `stepOrder`
    0 ownership step, role-identified for the tenant's default host role
    (`reception`, seeded by this module's `_default_host_role` fixture).
    """
    from datetime import date, time

    from vmss_api.invitations import service as invitations_service
    from vmss_api.invitations.schemas import (
        ConsentsSubmit,
        IdProofType,
        InvitationCreate,
        InvitationPrimaryContactCreate,
        RegistrationType,
        VisitDetailsSubmit,
    )

    category = VisitorCategoryFactory.build(id=uuid.uuid4(), name="No Workflow", code="NO-WORKFLOW")
    db_session.add(category)
    await db_session.commit()

    payload = InvitationCreate(
        registration_type=RegistrationType.individual,
        visitor_category_id=category.id,
        primary_contact=InvitationPrimaryContactCreate(
            full_name="Test Visitor",
            email="test.visitor@example.com",
            id_proof_type=IdProofType.passport,
        ),
        visit_details=VisitDetailsSubmit(
            purpose_of_visit="Test",
            preferred_visit_date=date(2026, 9, 1),
            preferred_visit_time=time(10, 0, 0),
            expected_duration="< 1 hour",
            department_to_visit="Test",
        ),
        consents=ConsentsSubmit(
            terms_accepted=True, data_processing_accepted=True, safety_guidelines_accepted=True
        ),
    )
    invitation = await invitations_service.create_invitation(
        db_session,
        payload,
        branch_id=branch.id,
        created_by_user_id=None,
        tenant=tenant,
        primary_contact_id_proof_content=_jpeg_bytes(),
        visitor_id_proof_contents=[],
        primary_contact_photo_content=_jpeg_bytes(),
        visitor_photo_contents=[],
    )
    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None

    steps = await InvitationApprovalStepRepository(db_session).list_for_invitation(invitation.id)
    assert len(steps) == 1
    assert steps[0].step_order == 0
    assert steps[0].approver_role_id == reception_role.id
    assert steps[0].approver_user_id is None
    assert steps[0].status == "pending"
    assert invitation.host_id is None


async def test_category_with_configured_rules_snapshots_exactly_the_configured_chain(
    tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """specs/approvals/spec.md "A category with three active rules
    snapshots exactly those three ordered steps" — no separate ownership
    step is inserted ahead of them; the first configured step (`stepOrder`
    1 here) doubles as the host-nomination step instead
    (`InvitationApprovalStepRepository.get_first_step`). Revises the old
    "always an unconditional stepOrder-0 ownership step" behavior — see
    `docs/features/approvals.md` "The host-nomination step" for why.
    """
    from datetime import date, time

    from vmss_api.invitations import service as invitations_service
    from vmss_api.invitations.schemas import (
        ConsentsSubmit,
        IdProofType,
        InvitationCreate,
        InvitationPrimaryContactCreate,
        RegistrationType,
        VisitDetailsSubmit,
    )

    category = VisitorCategoryFactory.build(
        id=uuid.uuid4(), name="Configured Workflow", code="CONFIGURED-WORKFLOW"
    )
    role = RoleFactory.build(id=uuid.uuid4(), name="workflow-role", permissions=[])
    db_session.add_all([category, role])
    await db_session.flush()
    db_session.add_all(
        [
            ApprovalWorkflowRuleFactory.build(
                id=uuid.uuid4(),
                visitor_category_id=category.id,
                step_order=step_order,
                approver_role_id=role.id,
            )
            for step_order in (1, 2, 3)
        ]
    )
    await db_session.commit()

    payload = InvitationCreate(
        registration_type=RegistrationType.individual,
        visitor_category_id=category.id,
        primary_contact=InvitationPrimaryContactCreate(
            full_name="Test Visitor",
            email="test.visitor2@example.com",
            id_proof_type=IdProofType.passport,
        ),
        visit_details=VisitDetailsSubmit(
            purpose_of_visit="Test",
            preferred_visit_date=date(2026, 9, 1),
            preferred_visit_time=time(10, 0, 0),
            expected_duration="< 1 hour",
            department_to_visit="Test",
        ),
        consents=ConsentsSubmit(
            terms_accepted=True, data_processing_accepted=True, safety_guidelines_accepted=True
        ),
    )
    invitation = await invitations_service.create_invitation(
        db_session,
        payload,
        branch_id=branch.id,
        created_by_user_id=None,
        tenant=tenant,
        primary_contact_id_proof_content=_jpeg_bytes(),
        visitor_id_proof_contents=[],
        primary_contact_photo_content=_jpeg_bytes(),
        visitor_photo_contents=[],
    )
    steps = await InvitationApprovalStepRepository(db_session).list_for_invitation(invitation.id)
    assert len(steps) == 3
    by_order = {s.step_order: s for s in steps}
    for step_order in (1, 2, 3):
        assert by_order[step_order].approver_role_id == role.id
        assert by_order[step_order].approver_user_id is None
        assert by_order[step_order].status == "pending"

    first_step = await InvitationApprovalStepRepository(db_session).get_first_step(invitation.id)
    assert first_step is not None
    assert first_step.step_order == 1
    assert invitation.host_id is None
