import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.auth.models import User, UserBranchRole
from vmss_api.invitations import service as invitations_service
from vmss_api.invitations.models import Invitation
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


async def _authorize_step_action(
    tenant_db: AsyncSession, user: User, invitation: Invitation, step: InvitationApprovalStep
) -> None:
    """specs/approvals/spec.md "Acting on a Step Requires the Caller's
    Matching Role, or an Explicit Override" — the caller's own
    `invitations:approve` permission is already checked by the router's
    `Depends()` chain before this is called (design.md Decision 4); this
    covers the role-match/host-match/override half only.

    A host-identified step (`approver_user_id` set — add-approval-step-id-
    and-host-routing/design.md) is authorized for that specific person
    only, regardless of their assigned role — it is not role-matched at
    all. A role-identified step (`approver_role_id` set) keeps the
    pre-existing role-match check. Either way,
    `invitations:approve-override` bypasses the match entirely.
    """
    if step.approver_user_id is not None:
        if user.id == step.approver_user_id:
            return
    else:
        assert step.approver_role_id is not None  # DB CHECK: exactly one of the two is set
        if await _user_holds_role_at_branch(
            tenant_db, user.id, step.approver_role_id, invitation.branch_id
        ):
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


async def _activate_next_step(tenant_db: AsyncSession, invitation_id: uuid.UUID) -> None:
    """After a step is approved, the next step by `step_order` (if any)
    becomes current — its own `escalates_at`/`auto_approves_at` are computed
    now, from its own snapshotted minute values, relative to *this* moment,
    not the invitation's original submission time (specs/approvals/spec.md
    "A later step's timestamps are set when it becomes current").
    """
    repo = InvitationApprovalStepRepository(tenant_db)
    next_step = await repo.get_current_pending(invitation_id)
    if next_step is None:
        return
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

    await _activate_next_step(tenant_db, invitation.id)
    await tenant_db.commit()
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
