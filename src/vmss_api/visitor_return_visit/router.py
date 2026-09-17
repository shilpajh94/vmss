"""Public, OTP-gated returning-visitor lookup. A visitor who has just
verified an email/phone via `POST /identity-verification/otp/verify` uses
the resulting proof token here to retrieve their own prior visit history and
a prefill payload for a new registration — see
`openspec/changes/visitor-return-visit-login/proposal.md` and
`specs/visitor-return-visit/spec.md`.
"""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import success_response
from vmss_api.core.schemas import Envelope
from vmss_api.identity_verification.masking import mask_identifier
from vmss_api.visitor_return_visit import service
from vmss_api.visitor_return_visit.deps import VerifiedContact, default_tenant_db, verified_contact
from vmss_api.visitor_return_visit.schemas import ReturningVisitorLookupOut

router = APIRouter(prefix="/visitor-portal", tags=["visitor-portal"])


@router.get("/me", response_model=Envelope[ReturningVisitorLookupOut])
@limiter.limit("20/minute")
async def get_my_visits(
    request: Request,
    contact: Annotated[VerifiedContact, Depends(verified_contact)],
    tenant_db: Annotated[AsyncSession, Depends(default_tenant_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> JSONResponse:
    """The lookup key comes solely from the proof token's own claims — never
    from a client-supplied identifier — so a caller can only ever retrieve
    data tied to an identifier they just proved control of (spec.md
    "Returning-Visitor Lookup Is Keyed Solely to a Verified-Contact Proof").
    """
    structlog.contextvars.bind_contextvars(identifier=mask_identifier(contact.identifier))
    data = await service.get_returning_visitor_data(
        tenant_db, contact.identifier, page=page, page_size=page_size
    )
    return success_response(data=data)
