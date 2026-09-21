from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.schemas import PaginationMeta
from vmss_api.core.storage import url_for as storage_url_for
from vmss_api.invitations.models import Invitation
from vmss_api.visitor_return_visit.repository import VisitorReturnVisitRepository
from vmss_api.visitor_return_visit.schemas import (
    ReturningVisitorLookupOut,
    ReturningVisitorPrefill,
    VisitHistoryEntry,
)


def _to_history_entry(invitation: Invitation) -> VisitHistoryEntry:
    return VisitHistoryEntry(
        tracking_id=invitation.tracking_id,
        status=invitation.status,
        visit_date=invitation.preferred_visit_date,
        purpose=invitation.purpose_of_visit,
    )


async def _to_prefill(invitation: Invitation) -> ReturningVisitorPrefill:
    photo_key = invitation.primary_contact_photo_storage_key
    id_proof_key = invitation.primary_contact_id_proof_storage_key
    return ReturningVisitorPrefill(
        full_name=invitation.primary_contact_full_name,
        email=invitation.primary_contact_email,
        phone=invitation.primary_contact_phone,
        preferred_contact_method=invitation.primary_contact_preferred_contact_method,
        id_proof_type=invitation.primary_contact_id_proof_type,
        id_proof_url=await storage_url_for(id_proof_key) if id_proof_key is not None else None,
        photo_url=await storage_url_for(photo_key) if photo_key is not None else None,
        visitor_category_id=invitation.visitor_category_id,
    )


async def get_returning_visitor_data(
    tenant_db: AsyncSession, identifier: str, *, page: int, page_size: int
) -> ReturningVisitorLookupOut:
    """Turns a verified identifier into its own visit history plus a prefill
    payload built from its most recent prior visit — empty history and no
    prefill for a first-time visitor, never an error (spec.md "No Prior
    Visit Found Returns an Empty Result, Not an Error").
    """
    repo = VisitorReturnVisitRepository(tenant_db)
    most_recent = await repo.get_most_recent(identifier)
    invitations, total = await repo.list_history(identifier, page=page, page_size=page_size)

    return ReturningVisitorLookupOut(
        history=[_to_history_entry(inv) for inv in invitations],
        prefill=await _to_prefill(most_recent) if most_recent is not None else None,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=-(-total // page_size) if page_size else 0,
        ),
    )
