import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.invitations import service as invitations_service
from vmss_api.invitations.models import Invitation
from vmss_api.invitations.schemas import InvitationCreate, RegistrationSource
from vmss_api.tenant.models import Tenant


async def create_walk_in_registration(
    tenant_db: AsyncSession,
    payload: InvitationCreate,
    *,
    branch_id: uuid.UUID,
    tenant: Tenant,
    primary_contact_id_proof_content: bytes,
    visitor_id_proof_contents: list[bytes],
    primary_contact_photo_content: bytes | None,
    visitor_photo_contents: list[bytes],
) -> Invitation:
    """API-13. A visitor registering on arrival, with no staff creator and no
    prior invitation. Everything else about record creation — validation,
    ID-proof storage, tracking-id generation, visit-confirmation dispatch —
    is identical to staff pre-registration (API-09), so it is delegated to
    `invitations.service.create_invitation` rather than reimplemented (see
    add-walkin-visitor-registration/design.md Decision 2). This feature owns
    no `Invitation` repository of its own. Optional profile photo capture
    (checkin-approval-workflow-improvements) is inherited the same way.
    """
    return await invitations_service.create_invitation(
        tenant_db,
        payload,
        branch_id=branch_id,
        created_by_user_id=None,
        tenant=tenant,
        primary_contact_id_proof_content=primary_contact_id_proof_content,
        visitor_id_proof_contents=visitor_id_proof_contents,
        primary_contact_photo_content=primary_contact_photo_content,
        visitor_photo_contents=visitor_photo_contents,
        source=RegistrationSource.visitor_walk_in,
    )
