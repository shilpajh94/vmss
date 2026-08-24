"""Unauthenticated, kiosk-facing lookups backing the walk-in registration
wizard's "Visit Info" step (visit-info-lookup-api). Tenant (and, for
department listing, branch) is resolved from the same `X-Device-Key`
credential `POST /registrations/walk-in` already uses — see
`registrations/deps.py` and design.md's "Decisions" on why this feature
imports that dependency rather than duplicating it.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import success_response
from vmss_api.core.schemas import Envelope
from vmss_api.registrations.deps import (
    RegistrationDeviceContext,
    get_registration_device,
    get_registration_tenant_db,
)
from vmss_api.visit_info import service
from vmss_api.visit_info.schemas import (
    DepartmentLookupListOut,
    HostSearchOut,
    VisitInfoOptionsOut,
)

router = APIRouter(tags=["visit-info"])

_MIN_QUERY_LENGTH = 2
_DEFAULT_LIMIT = 10
_MAX_LIMIT = 25


@router.get("/hosts/search", response_model=Envelope[HostSearchOut])
@limiter.limit("20/minute")
async def search_hosts(
    request: Request,
    tenant_db: Annotated[AsyncSession, Depends(get_registration_tenant_db)],
    query: Annotated[str, Query(min_length=_MIN_QUERY_LENGTH)],
    limit: Annotated[int, Query(ge=1, le=_MAX_LIMIT)] = _DEFAULT_LIMIT,
) -> JSONResponse:
    """Autocomplete lookup so a visitor/kiosk operator can find the employee
    they're visiting by partial name or email, instead of free-typing it
    (spec.md "Host Search Returns Active Employees Matching Name or Email").
    """
    hosts = await service.search_hosts(tenant_db, query=query, limit=limit)
    return success_response(data=HostSearchOut(hosts=hosts))


@router.get("/visit-info/departments", response_model=Envelope[DepartmentLookupListOut])
@limiter.limit("20/minute")
async def list_departments(
    request: Request,
    device: Annotated[RegistrationDeviceContext, Depends(get_registration_device)],
    tenant_db: Annotated[AsyncSession, Depends(get_registration_tenant_db)],
) -> JSONResponse:
    """Replaces the free-text "Department to Visit" field with a fixed,
    selectable list scoped to the kiosk's resolved branch (spec.md
    "Department Listing Is Scoped to the Kiosk's Resolved Branch"). Not
    `GET /departments` — that path already belongs to `org_structure`'s
    authenticated, branch-scoped admin endpoint.
    """
    departments = await service.list_departments(tenant_db, branch_id=device.branch_id)
    return success_response(data=DepartmentLookupListOut(departments=departments))


@router.get("/visit-info/options", response_model=Envelope[VisitInfoOptionsOut])
@limiter.limit("20/minute")
async def get_visit_info_options(
    request: Request,
    tenant_db: Annotated[AsyncSession, Depends(get_registration_tenant_db)],
) -> JSONResponse:
    """Replaces the app's hardcoded fake Purpose/Duration dropdowns with real,
    configured catalogs (spec.md "Visit Purpose and Duration Options Are
    Served From Configured Catalogs").
    """
    options = await service.get_visit_info_options(tenant_db)
    return success_response(data=options)
