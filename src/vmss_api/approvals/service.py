import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.auth.models import User, UserBranchRole
from vmss_api.auth.repository import UserRepository
from vmss_api.invitations import push_notifications
from vmss_api.invitations import service as invitations_service
from vmss_api.invitations.models import Invitation
from vmss_api.notifications import service as notifications_service
from vmss_api.tenant.models import Tenant


async def _user_holds_role_at_branch(
    tenant_db: AsyncSession, user_id: uuid.UUID, role_id: uuid.UUID, branch_id: uuid.UUID
) -> bool:
    """Does `user_id` hold `role_id` via a `UserBranchRole` scoped to
    `branch_id`, or company-wide (`branch_id IS NULL`)? Mirrors
    `auth/models.py::User.has_permission`'s own branch-or-company-wide match,
    but keyed on role identity rather than a permission code — there's no
    equivalent already on `User`/`UserBranchRole` since nothing before this
    feature needed "does this user hold *this specific role*" as opposed to
    "does this user hold *some role granting this permission*".
    """
    stmt = select(UserBranchRole.id).where(
        UserBranchRole.user_id == user_id,
        UserBranchRole.role_id == role_id,
        (UserBranchRole.branch_id == branch_id) | (UserBranchRole.branch_id.is_(None)),
    )
    return (await tenant_db.execute(stmt)).scalar_one_or_none() is not None


async def _caller_matches_step(
    tenant_db: AsyncSession, user: User, invitation: Invitation, step: InvitationApprovalStep
) -> bool:
    """Does `user` match this step's assigned approver — delegate, host, or
    role-holder — independent of the `invitations:approve-override` bypass?
    Shared by `_authorize_step_action` (acting) and `delegate_step`
    (delegating): "whoever is currently authorized to act on a step may
    delegate it instead" (specs/approvals/spec.md "Current Step's
    Authorized Approver Delegates It to a Specific Person").

    A host-identified step (`approver_user_id` set) is authorized for that
    specific person only, regardless of their assigned role — it is not
    role-matched at all. A role-identified step (`approver_role_id` set)
    keeps the role-match check, unless it has been delegated
    (`delegated_to_user_id` set), in which case only the delegate matches,
    not just-any holder of the role.
    """
    if step.delegated_to_user_id is not None:
        return user.id == step.delegated_to_user_id
    if step.approver_user_id is not None:
        return user.id == step.approver_user_id
    assert step.approver_role_id is not None  # DB CHECK: exactly one of the two is set
    return await _user_holds_role_at_branch(
        tenant_db, user.id, step.approver_role_id, invitation.branch_id
    )


async def _authorize_step_action(
    tenant_db: AsyncSession, user: User, invitation: Invitation, step: InvitationApprovalStep
) -> None:
    """specs/approvals/spec.md "Acting on a Step Requires the Caller's
    Matching Role, or an Explicit Override" — the caller's own
    `invitations:approve` permission is already checked by the router's
    `Depends()` chain before this is called (design.md Decision 4); this
    covers the role-match/host-match/delegate-match half (`_caller_matches_
    step`) plus the `invitations:approve-override` bypass.
    """
    if await _caller_matches_step(tenant_db, user, invitation, step):
        return
    if user.has_permission("invitations:approve-override", branch_id=invitation.branch_id):
        return
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        detail="Caller does not match this step's approver",
    )


async def _resolve_current_step(
    tenant_db: AsyncSession, invitation_id: uuid.UUID, step_id: uuid.UUID
) -> tuple[InvitationApprovalStep, InvitationApprovalStep | None]:
    """Returns `(named_step, current_pending_step)`. Raises 404 if `step_id`
    doesn't exist for this invitation. The caller compares the two to decide
    whether `step_id` is actually actionable right now (specs/approvals
    /spec.md "Acting on a step out of order is rejected").
    """
    repo = InvitationApprovalStepRepository(tenant_db)
    named_step = await repo.get_by_id_for_invitation(invitation_id, step_id)
    if named_step is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Approval step not found")
    current = await repo.get_current_pending(invitation_id)
    return named_step, current


def _require_is_current(
    named_step: InvitationApprovalStep, current: InvitationApprovalStep | None
) -> None:
    if current is None or named_step.id != current.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This step is not the invitation's current pending step",
        )


async def _activate_next_step(
    tenant_db: AsyncSession, invitation_id: uuid.UUID
) -> InvitationApprovalStep | None:
    """After a step is approved, the next step by `step_order` (if any)
    becomes current — its own `escalates_at`/`auto_approves_at` are computed
    now, from its own snapshotted minute values, relative to *this* moment,
    not the invitation's original submission time (specs/approvals/spec.md
    "A later step's timestamps are set when it becomes current"). Returns
    that newly-current step (or `None`) so the caller can dispatch its push
    *after* its own commit (`approve_step` below) — never from in here, which
    runs before that commit.
    """
    repo = InvitationApprovalStepRepository(tenant_db)
    next_step = await repo.get_current_pending(invitation_id)
    if next_step is None:
        return None
    now = datetime.now(UTC)
    await repo.set_clock(
        next_step.id,
        escalates_at=(
            now + timedelta(minutes=next_step.escalation_minutes)
            if next_step.escalation_minutes is not None
            else None
        ),
        auto_approves_at=(
            now + timedelta(minutes=next_step.auto_approve_minutes)
            if next_step.auto_approve_minutes is not None
            else None
        ),
    )
    return next_step


async def approve_step(
    tenant_db: AsyncSession,
    user: User,
    invitation: Invitation,
    step_id: uuid.UUID,
    *,
    tenant: Tenant,
) -> Invitation:
    """specs/approvals/spec.md "Steps Are Approved in Strict Order by the
    Current Pending Step". Approving the last step finalizes the invitation
    by calling `invitations.service.approve_invitation` verbatim (design.md
    Decision 2) — not reimplemented here.
    """
    named_step, current = await _resolve_current_step(tenant_db, invitation.id, step_id)
    _require_is_current(named_step, current)
    await _authorize_step_action(tenant_db, user, invitation, named_step)

    updated_step = await InvitationApprovalStepRepository(tenant_db).approve_if_pending(
        step_id, user_id=user.id
    )
    if updated_step is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This step is not the invitation's current pending step",
        )

    remaining = await InvitationApprovalStepRepository(tenant_db).get_current_pending(invitation.id)
    if remaining is None:
        return await invitations_service.approve_invitation(tenant_db, invitation, tenant=tenant)

    activated_step = await _activate_next_step(tenant_db, invitation.id)
    await tenant_db.commit()
    if activated_step is not None:
        title, body, data = push_notifications.step_awaiting_approval(invitation)
        await notifications_service.notify_step_approver(
            tenant_db,
            tenant_schema=tenant.schema_name,
            approver_user_id=activated_step.approver_user_id,
            approver_role_id=activated_step.approver_role_id,
            branch_id=invitation.branch_id,
            title=title,
            body=body,
            data=data,
        )
    return invitation


async def reject_step(
    tenant_db: AsyncSession,
    user: User,
    invitation: Invitation,
    step_id: uuid.UUID,
    *,
    reason: str,
    tenant: Tenant,
) -> Invitation:
    """specs/approvals/spec.md "Rejecting a Step Is Terminal and Denies the
    Invitation" — regardless of how many steps remain after the rejected
    one, denies the whole invitation by calling
    `invitations.service.deny_invitation` verbatim (design.md Decision 2).
    """
    named_step, current = await _resolve_current_step(tenant_db, invitation.id, step_id)
    _require_is_current(named_step, current)
    await _authorize_step_action(tenant_db, user, invitation, named_step)

    updated_step = await InvitationApprovalStepRepository(tenant_db).reject_if_pending(
        step_id, user_id=user.id
    )
    if updated_step is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This step is not the invitation's current pending step",
        )

    return await invitations_service.deny_invitation(
        tenant_db, invitation, reason=reason, tenant=tenant
    )


async def delegate_step(
    tenant_db: AsyncSession,
    user: User,
    invitation: Invitation,
    step_id: uuid.UUID,
    *,
    delegate_user_id: uuid.UUID,
) -> InvitationApprovalStep:
    """specs/approvals/spec.md "Current Step's Authorized Approver Delegates
    It to a Specific Person". Three independent ways to be authorized to
    delegate the invitation's current pending step, at any `stepOrder`: (1)
    the caller is the invitation's host — a blanket privilege regardless of
    whether the host would otherwise be authorized to act on that specific
    step (design.md Decision 4 explains why this is not just a reuse of the
    acting-authorization predicate: the host's whole reason to delegate a
    role-identified step is that they don't hold that role); (2) the caller
    otherwise matches the current step directly (role match, an existing
    delegate re-delegating); or (3) `invitations:approve-override`. The
    named delegate must satisfy the step's own kind: hold `approverRoleId`
    at the invitation's branch (or company-wide) for a role-identified
    step, or hold `invitations:approve` at the invitation's branch for the
    host-identified `stepOrder` 0 step.
    """
    repo = InvitationApprovalStepRepository(tenant_db)
    named_step, current = await _resolve_current_step(tenant_db, invitation.id, step_id)
    _require_is_current(named_step, current)

    host_step = await repo.get_by_step_order(invitation.id, 0)
    is_invitation_host = (
        host_step is not None
        and host_step.approver_user_id is not None
        and user.id == host_step.approver_user_id
    )
    if (
        not is_invitation_host
        and not await _caller_matches_step(tenant_db, user, invitation, named_step)
        and not user.has_permission("invitations:approve-override", branch_id=invitation.branch_id)
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Caller is not authorized to delegate this step",
        )

    if named_step.approver_role_id is not None:
        if not await _user_holds_role_at_branch(
            tenant_db, delegate_user_id, named_step.approver_role_id, invitation.branch_id
        ):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Delegate does not hold this step's approver role at the invitation's branch"
                ),
            )
    else:
        assert named_step.approver_user_id is not None  # DB CHECK: exactly one of role/user is set
        delegate_user = await UserRepository(tenant_db).get_by_id(delegate_user_id)
        if delegate_user is None or not delegate_user.has_permission(
            "invitations:approve", branch_id=invitation.branch_id
        ):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Delegate does not hold invitations:approve at the invitation's branch",
            )

    updated_step = await repo.delegate_if_eligible(
        step_id,
        delegated_to_user_id=delegate_user_id,
        delegated_by_user_id=user.id,
        expected_current_delegate_id=named_step.delegated_to_user_id,
    )
    if updated_step is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This step is not currently pending",
        )
    await tenant_db.commit()
    return updated_step
