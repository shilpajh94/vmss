import io
import uuid
from collections.abc import Callable

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
from vmss_api.invitations import tasks
from vmss_api.invitations.models import Invitation
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="JPEG")
    return buffer.getvalue()


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


# --- Category-with-no-workflow fallback (cross-check with invitations/tests.py) --


async def test_category_with_no_active_rules_creates_no_steps(
    tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """specs/approvals/spec.md "A category with no active rules creates no
    steps" — exercised directly at the service layer (testing-standards.md
    §3), complementing `invitations/tests.py`'s endpoint-level coverage of
    the same fallback.
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
            host_name_or_email="host@example.com",
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
    )
    steps = await InvitationApprovalStepRepository(db_session).list_for_invitation(invitation.id)
    assert steps == []


# --- Host-as-step-0 snapshotting (add-approval-step-id-and-host-routing) ----


async def test_resolved_host_with_no_active_rules_creates_single_host_step(
    tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """specs/approvals/spec.md "A resolved host with no configured rules
    creates a single host-approval step".
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

    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    category = VisitorCategoryFactory.build(id=uuid.uuid4(), name="Host Only", code="HOST-ONLY")
    db_session.add_all([host, category])
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
            host_name_or_email="ignored@example.com",
            host_id=host.id,
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
    )
    assert invitation.host_id == host.id

    steps = await InvitationApprovalStepRepository(db_session).list_for_invitation(invitation.id)
    assert len(steps) == 1
    assert steps[0].step_order == 0
    assert steps[0].approver_user_id == host.id
    assert steps[0].approver_role_id is None
    assert steps[0].status == "pending"


async def test_resolved_host_with_configured_rules_creates_host_step_ahead_of_role_chain(
    tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """specs/approvals/spec.md "A resolved host with configured rules
    creates a host step ahead of the role chain" — host is `stepOrder` 0,
    the three configured rules keep their own `stepOrder` 1/2/3 unchanged.
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

    host = UserFactory.build(
        id=uuid.uuid4(),
        email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Host With Workflow",
    )
    category = VisitorCategoryFactory.build(
        id=uuid.uuid4(), name="Host And Workflow", code="HOST-AND-WORKFLOW"
    )
    role = RoleFactory.build(id=uuid.uuid4(), name="workflow-role", permissions=[])
    db_session.add_all([host, category, role])
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
            host_name_or_email="ignored@example.com",
            host_id=host.id,
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
    )

    steps = await InvitationApprovalStepRepository(db_session).list_for_invitation(invitation.id)
    assert len(steps) == 4
    by_order = {s.step_order: s for s in steps}
    assert by_order[0].approver_user_id == host.id
    assert by_order[0].approver_role_id is None
    assert by_order[0].status == "pending"
    for step_order in (1, 2, 3):
        assert by_order[step_order].approver_role_id == role.id
        assert by_order[step_order].approver_user_id is None
        assert by_order[step_order].status == "pending"
