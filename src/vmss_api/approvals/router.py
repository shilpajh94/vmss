import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.approvals import service
from vmss_api.approvals.schemas import InvitationApprovalStepRejectRequest
from vmss_api.auth.audit import record_audit_log
from vmss_api.auth.models import User
from vmss_api.core.deps import get_current_user, get_tenant, get_tenant_db
from vmss_api.core.responses import success_response
from vmss_api.core.schemas import Envelope
from vmss_api.invitations import service as invitations_service
from vmss_api.invitations.router import to_invitation_out
from vmss_api.invitations.schemas import InvitationOut
from vmss_api.org_structure.deps import authorize_branch_id_tolerant
from vmss_api.tenant.models import Tenant

# Deliberately prefixed "/invitations", not "/approvals" — these routes are
# the per-invitation approval-step actions the frontend calls as part of an
# invitation's own lifecycle (`POST /invitations/{id}/approval-steps/{stepId}
# /approve`), living in this separate package only because the *workflow
# engine* behind them does (fastapi-architecture.md §1,
# invitation-multi-step-approval/design.md Decision 1). `api.py` registers
# this alongside `invitations.router.router`; the two never define
# overlapping paths.
router = APIRouter(prefix="/invitations", tags=["approvals"])


@router.post(
    "/{invitation_id}/approval-steps/{step_id}/approve",
    response_model=Envelope[InvitationOut],
)
async def approve_step(
    invitation_id: uuid.UUID,
    step_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Approves one step of a workflow-backed invitation — the last step
    approves the invitation itself and fires the existing QR/notification
    dispatch; any earlier step unlocks the next one (specs/approvals/spec.md
    "Steps Are Approved in Strict Order by the Current Pending Step").
    """
    invitation = await invitations_service.get_invitation(tenant_db, invitation_id)
    await authorize_branch_id_tolerant(tenant_db, user, "invitations:approve", invitation.branch_id)
    invitation = await service.approve_step(tenant_db, user, invitation, step_id, tenant=tenant)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_approval_step_approved",
        entity_type="InvitationApprovalStep",
        entity_id=step_id,
    )
    current_approval_step = await invitations_service.get_current_approval_step(
        tenant_db, invitation
    )
    return success_response(data=to_invitation_out(invitation, current_approval_step))


@router.post(
    "/{invitation_id}/approval-steps/{step_id}/reject",
    response_model=Envelope[InvitationOut],
)
async def reject_step(
    invitation_id: uuid.UUID,
    step_id: uuid.UUID,
    payload: InvitationApprovalStepRejectRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Rejects one step — terminal, and immediately denies the whole
    invitation regardless of how many steps remain after it (specs/
    approvals/spec.md "Rejecting a Step Is Terminal and Denies the
    Invitation").
    """
    invitation = await invitations_service.get_invitation(tenant_db, invitation_id)
    await authorize_branch_id_tolerant(tenant_db, user, "invitations:approve", invitation.branch_id)
    invitation = await service.reject_step(
        tenant_db, user, invitation, step_id, reason=payload.reason, tenant=tenant
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_approval_step_rejected",
        entity_type="InvitationApprovalStep",
        entity_id=step_id,
    )
    return success_response(data=to_invitation_out(invitation))
