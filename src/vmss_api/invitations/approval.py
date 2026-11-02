"""Approving, denying and reverting an invitation, and reading its current
approval step. Split out of `service.py`, which re-exports every name.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.approvals.schemas import CurrentApprovalStepOut
from vmss_api.auth.models import User
from vmss_api.core.logging import current_request_id, logger
from vmss_api.invitations import push_notifications, tasks
from vmss_api.invitations.common import (
    _end_of_visit_day_utc,
    _issue_checkin_code,
    _issue_qr_code,
    _notify_activated_approver,
    _notify_host,
    _notify_responsible_staff,
    _push_point_of_contact,
    _restart_approval,
    resolve_visit_timezone,
)
from vmss_api.invitations.models import (
    Invitation,
)
from vmss_api.invitations.repository import (
    InvitationRepository,
)
from vmss_api.tenant.models import Tenant


async def approve_invitation(
    tenant_db: AsyncSession,
    invitation: Invitation,
    *,
    tenant: Tenant,
    actor_user_id: uuid.UUID | None = None,
) -> Invitation:
    """Transitions a `submitted` invitation to `approved` and enqueues the
    approval notification (`add-invitation-approval-flow-and-role-resync/
    design.md` Decision 3), mirroring `create_invitation`'s own
    dispatch-after-commit pattern. `router.py` fetches `invitation` and
    resolves branch authorization (404/403) before calling this — a
    not-found or unauthorized invitation never reaches here.

    The transition itself goes through `InvitationRepository
    .approve_if_submitted` — a single conditional `UPDATE`, not a
    read-then-write on the `invitation` object already in hand — so two
    concurrent approval requests for the same invitation can't both pass a
    status check and both dispatch a notification (see
    codebase-review-and-e2e-scenario-test/design.md).

    Rejected with 409 (design.md Decision 3) if the invitation still has a
    `pending` `InvitationApprovalStep` — that invitation must be approved
    step by step through `POST /invitations/{id}/approval-steps/{stepId}
    /approve` instead (specs/invitations/spec.md "Blanket approve rejected
    for a workflow-backed invitation"). Checking for a *pending* step, not
    merely "any step at all", is what lets `approvals.service.approve_step`
    call this function verbatim to finalize the last step (design.md
    Decision 2) — by then every step is already `approved`, so this guard
    correctly falls through instead of rejecting its own caller.
    """
    if await InvitationApprovalStepRepository(tenant_db).has_pending_for_invitation(invitation.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Invitation has a configured approval workflow; approve its steps instead",
        )
    expires_at = (
        _end_of_visit_day_utc(
            invitation.preferred_visit_date, await resolve_visit_timezone(tenant_db, tenant)
        )
        if invitation.preferred_visit_date is not None
        else None
    )
    updated = await InvitationRepository(tenant_db).approve_if_submitted(
        invitation.id, expires_at=expires_at
    )
    if updated is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation is not awaiting approval")
    qr_code = await _issue_qr_code(tenant_db, updated, tenant=tenant)
    await _issue_checkin_code(tenant_db, updated)
    await tenant_db.commit()
    tasks.send_approval_notification.delay(
        request_id=current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(updated.id),
        qr_token=qr_code.qr_token,
    )
    await _notify_host(tenant, updated, push_notifications.approved)
    await _push_point_of_contact(
        tenant_db,
        tenant,
        updated,
        push_builder=push_notifications.approved,
        actor_user_id=actor_user_id,
    )
    return updated


async def deny_invitation(
    tenant_db: AsyncSession,
    invitation: Invitation,
    *,
    reason: str,
    tenant: Tenant,
    actor_user_id: uuid.UUID,
) -> Invitation:
    """Transitions a `submitted` invitation to `denied` and enqueues the
    denial notification — mirrors `approve_invitation`'s own
    dispatch-after-commit pattern (spec.md "A Submitted Invitation Can Be
    Denied With a Reason").
    """
    updated = await InvitationRepository(tenant_db).deny_if_submitted(invitation.id, reason=reason)
    if updated is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation is not awaiting approval")
    await tenant_db.commit()
    tasks.send_denial_notification.delay(
        request_id=current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(updated.id),
    )
    await _notify_host(tenant, updated, push_notifications.denied)
    await _notify_responsible_staff(
        tenant_db, tenant, updated, event="denied", actor_user_id=actor_user_id
    )
    return updated


async def revert_invitation_approval(
    tenant_db: AsyncSession,
    invitation: Invitation,
    *,
    user: User,
    reason: str,
    tenant: Tenant,
) -> Invitation:
    """Sends an `approved`, never-admitted invitation back to `submitted`
    (spec.md "An Approved, Not-Yet-Checked-In Invitation Can Have Its
    Approval Reverted"). The pre-read only picks a specific 409 message;
    `revert_approval_if_eligible`'s atomic `WHERE` is the real gate, same
    as `approve_invitation`.

    A workflow-backed invitation has every step reset to `pending` and the
    first step re-activated in the same transaction (approvals spec "Reverting
    an Approval Restarts the Invitation's Workflow From Its First Step") —
    both calls are no-ops for an invitation without steps (auto-approved).
    The QR row is kept: every check-in path already refuses a `submitted`
    invitation, and re-approval re-sends the same pass (design.md
    Decision 3).
    """
    if invitation.status == "approved" and invitation.check_in_status != "unused":
        logger.warning(
            "invitation_revert_rejected", invitation_id=str(invitation.id), reason="checked_in"
        )
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Visitor has already checked in on this invitation"
        )
    updated = await InvitationRepository(tenant_db).revert_approval_if_eligible(
        invitation.id, user_id=user.id, reason=reason
    )
    if updated is None:
        logger.warning(
            "invitation_revert_rejected", invitation_id=str(invitation.id), reason="not_approved"
        )
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation is not approved")
    activated_step = await _restart_approval(tenant_db, updated)
    await tenant_db.commit()
    logger.info(
        "invitation_approval_reverted",
        invitation_id=str(updated.id),
        workflow_restarted=activated_step is not None,
    )
    tasks.send_approval_revert_notification.delay(
        request_id=current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(updated.id),
    )
    await _notify_host(tenant, updated, push_notifications.approval_reverted)
    await _notify_responsible_staff(
        tenant_db, tenant, updated, event="approval_reverted", actor_user_id=user.id
    )
    await _notify_activated_approver(tenant_db, tenant, updated, activated_step)
    return updated


async def get_current_approval_step(
    tenant_db: AsyncSession, invitation: Invitation
) -> CurrentApprovalStepOut | None:
    """Backs the `currentApprovalStep` field on `InvitationOut`/
    `InvitationTrackingOut`/`InvitationDetailOut` (design.md Decision 7) —
    two indexed queries (current pending step + total count), run only for a
    single-invitation lookup, never for `GET /invitations` list rows
    (query-performance.md §2). `None` for an invitation with no snapshotted
    steps, or one that is no longer `submitted`
    (specs/invitations/spec.md "Non-workflow invitation omits step
    progress").

    Every caller invokes this as a trailing read *after* its own mutation
    has already committed — role-based-invitation-workflow made this read
    path reachable for every submitted invitation (previously only
    workflow-backed ones), which surfaced a latent issue: a plain `SELECT`
    still opens an implicit transaction, and nothing after this point
    commits it, leaving the caller's session `idle in transaction` for the
    rest of a test (or an unusually long-lived request). Committing here —
    a pure read, so there's nothing to lose by doing so — closes that
    transaction out immediately rather than leaving it open until whatever
    eventually closes the session.
    """
    if invitation.status != "submitted":
        return None
    repo = InvitationApprovalStepRepository(tenant_db)
    current = await repo.get_current_pending(invitation.id)
    if current is None:
        return None
    total_steps = await repo.count_for_invitation(invitation.id)
    await tenant_db.commit()
    return CurrentApprovalStepOut(
        id=current.id,
        step_order=current.step_order,
        approver_role_id=current.approver_role_id,
        approver_user_id=current.approver_user_id,
        total_steps=total_steps,
        delegated_to_user_id=current.delegated_to_user_id,
    )


async def current_approval_steps(
    tenant_db: AsyncSession, invitations: list[Invitation]
) -> dict[uuid.UUID, CurrentApprovalStepOut]:
    """`get_current_approval_step` for a whole list page in one query, keyed
    by invitation id; invitations with no pending step are absent. Same
    rules: only a `submitted` invitation has a current step."""
    submitted = [i.id for i in invitations if i.status == "submitted"]
    steps = await InvitationApprovalStepRepository(tenant_db).list_for_invitations(submitted)
    by_invitation: dict[uuid.UUID, list[InvitationApprovalStep]] = {}
    for step in steps:
        by_invitation.setdefault(step.invitation_id, []).append(step)
    current: dict[uuid.UUID, CurrentApprovalStepOut] = {}
    for invitation_id, invitation_steps in by_invitation.items():
        pending = next((s for s in invitation_steps if s.status == "pending"), None)
        if pending is None:
            continue
        current[invitation_id] = CurrentApprovalStepOut(
            id=pending.id,
            step_order=pending.step_order,
            approver_role_id=pending.approver_role_id,
            approver_user_id=pending.approver_user_id,
            total_steps=len(invitation_steps),
            delegated_to_user_id=pending.delegated_to_user_id,
        )
    return current
