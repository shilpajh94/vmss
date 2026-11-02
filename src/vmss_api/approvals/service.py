import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.auth.models import User
from vmss_api.auth.rbac_catalog import DELEGATION_ONLY_ROLE_NAMES
from vmss_api.auth.repository import RoleRepository, UserRepository
from vmss_api.core.logging import current_request_id
from vmss_api.invitations import push_notifications, tasks
from vmss_api.invitations import service as invitations_service
from vmss_api.invitations.models import Invitation
from vmss_api.invitations.repository import InvitationRepository
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
    return await UserRepository(tenant_db).holds_role_at_branch(user_id, role_id, branch_id)


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
    not just-any holder of the role — or unless the role is one of
    `DELEGATION_ONLY_ROLE_NAMES` (`host`), in which case *no* holder matches
    until it has been delegated: `host` is typically held by a large,
    company-wide set of people, so an undelegated host-identified step must
    wait for Reception (or the previous step's approver) to name one
    specific person before anyone can act on it.
    """
    if step.delegated_to_user_id is not None:
        return user.id == step.delegated_to_user_id
    if step.approver_user_id is not None:
        return user.id == step.approver_user_id
    assert step.approver_role_id is not None  # DB CHECK: exactly one of the two is set
    role = await RoleRepository(tenant_db).get(step.approver_role_id)
    if role is not None and role.name.lower() in DELEGATION_ONLY_ROLE_NAMES:
        return False
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
    becomes current — see `InvitationApprovalStepRepository.
    activate_current_pending` for how its clock is computed. Returns that
    newly-current step (or `None`) so the caller can dispatch its push
    *after* its own commit (`approve_step` below) — never from in here,
    which runs before that commit.
    """
    return await InvitationApprovalStepRepository(tenant_db).activate_current_pending(invitation_id)


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
    Decision 2) — not reimplemented here. The host-nomination step (whichever
    step is first — `InvitationApprovalStepRepository.get_first_step`; see
    `invitations/service.py::_build_approval_steps`) is a plain
    role-identified step like any other: its role-holder (e.g. Reception) may
    approve it directly, exactly as they would delegate it (`delegate_step`
    below) — approving it directly leaves the invitation's `hostId`
    unresolved unless/until some step is delegated (see "Delegating the
    Host-Nomination Step Also Resolves the Invitation's Host"), UNLESS the
    host-nomination step is also the invitation's *only* step — a
    single-step, reception-only workflow with no further level to delegate
    to. In that case there is no delegation step through which a real host
    could ever be named, so the approver themself becomes the invitation's
    resolved host (see "Approving the Only Step of a Single-Step Workflow
    Also Resolves the Invitation's Host") — this is what lets the visitor's
    approval-confirmation email name a real point of contact (the approving
    Reception user) instead of falling back to the branch's generic
    front-desk contact.
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
        first_step = await InvitationApprovalStepRepository(tenant_db).get_first_step(invitation.id)
        if first_step is not None and first_step.id == named_step.id:
            updated_invitation = await InvitationRepository(tenant_db).set_host_if_exists(
                invitation.id, host_id=user.id, host_name_or_email=user.full_name
            )
            if updated_invitation is not None:
                invitation = updated_invitation
        return await invitations_service.approve_invitation(
            tenant_db, invitation, tenant=tenant, actor_user_id=user.id
        )

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
        tenant_db, invitation, reason=reason, tenant=tenant, actor_user_id=user.id
    )


async def delegate_step(
    tenant_db: AsyncSession,
    user: User,
    invitation: Invitation,
    step_id: uuid.UUID,
    *,
    delegate_user_id: uuid.UUID,
    tenant: Tenant,
) -> InvitationApprovalStep:
    """specs/approvals/spec.md "Current Step's Authorized Approver Delegates
    It to a Specific Person". Three independent ways to be authorized to
    delegate the invitation's current pending step, at any `stepOrder`: (1)
    the caller is the invitation's currently resolved host (`invitation.
    host_id`) — a blanket privilege regardless of whether the host would
    otherwise be authorized to act on that specific step (design.md Decision
    4 explains why this is not just a reuse of the acting-authorization
    predicate: the host's whole reason to delegate a role-identified step is
    that they don't hold that role) — this clause simply never matches
    before a host has been resolved, which is the common case for a freshly
    submitted invitation (role-based-invitation-workflow); (2) the
    caller otherwise matches the current step directly (role match, an
    existing delegate re-delegating); (3)
    `invitations:approve-override`; or (4) the caller is the one who
    actually approved the step immediately preceding this one (`step_order
    - 1`), regardless of whether they hold this step's own `approverRoleId`
    — so e.g. Reception, having approved the invitation's host-nomination
    step, can hand the next, differently-role-identified step straight to
    whoever the workflow configures for it, rather than having to wait for
    one of that role's holders to notice and delegate/act on it themselves
    (reception-retains-visibility-and-delegation-after-own-step). Clause (4)
    only ever matches the step immediately following the one the caller
    acted on — it does not chain further back, and does not apply to the
    host-nomination step itself (no preceding step exists). The named
    delegate's own eligibility depends on which step is being delegated: for
    the host-nomination step (`InvitationApprovalStepRepository.
    get_first_step` — whichever step that turns out to be; see
    `invitations/service.py::_build_approval_steps`), the delegate SHALL
    hold `invitations:approve` at the invitation's branch — NOT the step's
    `approverRoleId` role itself, since the real host is normally not a
    front-office employee (role-based-invitation-workflow's one exception to
    the general rule). For every other role-identified step, the delegate
    SHALL hold that step's `approverRoleId` role at the invitation's branch
    or company-wide, unchanged from before.

    Delegating *any* step — not just the host-nomination step — now
    resolves/updates the invitation's `hostId`/`hostNameOrEmail` to that
    step's delegate and
    sends them the host-assigned notification (extended from the original
    host-nomination-step-only rule; see
    "reception-retains-visibility-and-delegation-after-own-step"): the
    invitation's host always reflects whoever was most recently delegated
    any step, so a re-delegation later in the chain supersedes an earlier
    one exactly the way re-delegating the host-nomination step itself
    already did.
    """
    repo = InvitationApprovalStepRepository(tenant_db)
    named_step, current = await _resolve_current_step(tenant_db, invitation.id, step_id)
    _require_is_current(named_step, current)

    first_step = await repo.get_first_step(invitation.id)
    is_ownership_step = first_step is not None and first_step.id == named_step.id

    is_resolved_host = invitation.host_id is not None and user.id == invitation.host_id
    was_previous_step_approver = False
    if not is_ownership_step:
        previous_step = await repo.get_by_step_order(invitation.id, named_step.step_order - 1)
        was_previous_step_approver = (
            previous_step is not None
            and previous_step.status == "approved"
            and previous_step.acted_by_user_id == user.id
        )
    if (
        not is_resolved_host
        and not was_previous_step_approver
        and not await _caller_matches_step(tenant_db, user, invitation, named_step)
        and not user.has_permission("invitations:approve-override", branch_id=invitation.branch_id)
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Caller is not authorized to delegate this step",
        )

    if is_ownership_step:
        # The host-nomination step (`step_order` isn't assumed to be a
        # literal `0` anymore — see `InvitationApprovalStepRepository.
        # get_first_step`): any active user with `invitations:approve` may
        # be nominated as host, regardless of whether they hold the step's
        # own `approverRoleId` role (the tenant's default host role, e.g.
        # `reception`, when the category has no configured rules — or
        # whatever role the category's own first configured level uses
        # otherwise) — the real host is normally not a front-office
        # employee.
        delegate_user = await UserRepository(tenant_db).get_by_id(delegate_user_id)
        if delegate_user is None or not delegate_user.has_permission(
            "invitations:approve", branch_id=invitation.branch_id
        ):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Delegate does not hold invitations:approve at the invitation's branch",
            )
    elif named_step.approver_role_id is not None:
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

    # Delegating *any* step now resolves/updates the invitation's host to
    # that step's delegate (extended from the original stepOrder-0-only rule
    # — reception-retains-visibility-and-delegation-after-own-step): the
    # invitation's hostId always reflects whoever the workflow's most recent
    # delegation named, at any stepOrder, echoed the same way a legacy
    # host-identified `stepOrder` 0 step's resolved-at-creation host already
    # was (specs/approvals/spec.md "Delegating the Ownership Step Also
    # Resolves the Invitation's Host").
    delegate_user = await UserRepository(tenant_db).get_by_id(delegate_user_id)
    assert delegate_user is not None  # validated above
    updated_invitation = await InvitationRepository(tenant_db).set_host_if_exists(
        invitation.id, host_id=delegate_user.id, host_name_or_email=delegate_user.full_name
    )
    assert updated_invitation is not None  # invitation already resolved above
    invitation = updated_invitation
    await tenant_db.commit()
    title, body, data = push_notifications.host_assigned(invitation)
    await notifications_service.notify_user(
        tenant_schema=tenant.schema_name,
        user_id=delegate_user.id,
        title=title,
        body=body,
        data=data,
    )
    tasks.send_host_creation_notification.delay(
        request_id=current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(invitation.id),
        host_id=str(delegate_user.id),
    )

    return updated_step
