from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.database import get_db
from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import success_response
from vmss_api.core.schemas import Envelope
from vmss_api.platform import service
from vmss_api.platform.models import SuperAdmin
from vmss_api.platform.schemas import (
    PlatformLoginRequest,
    PlatformTokenResponse,
    TenantCreateRequest,
    TenantSummaryOut,
)
from vmss_api.tenant.repository import TenantRepository

router = APIRouter(prefix="/platform", tags=["platform"])


@router.post("/auth/login", response_model=Envelope[PlatformTokenResponse])
@limiter.limit("5/minute")
async def platform_login(
    request: Request,
    payload: PlatformLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Rate-limited (5/min per IP) — public, unauthenticated endpoint, same
    reasoning as `/auth/login`. See security-architecture.md §2.
    """
    admin = await service.authenticate_superadmin(db, payload.email, payload.password)
    token = service.issue_platform_token(admin)
    return success_response(data=PlatformTokenResponse(access_token=token))


@router.post("/tenants", response_model=Envelope[TenantSummaryOut], status_code=201)
@limiter.limit("3/minute")
async def create_tenant(
    request: Request,
    payload: TenantCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[SuperAdmin, Depends(service.get_current_superadmin)],
) -> JSONResponse:
    """Provisions a new tenant — its own Postgres schema, every tenant
    migration applied, and a `tenants` registry row. See
    `platform/service.py::create_tenant`.

    Rate-limited even though authenticated (unlike `/platform/auth/login`,
    which is rate-limited because it's public): schema creation plus a full
    Alembic migration run is expensive enough that a compromised superadmin
    token or a buggy client retry loop hammering this endpoint is a real
    resource-exhaustion risk, not just a brute-force one — defense in depth
    on top of `require_permission`-style auth, in the spirit of
    security-architecture.md §2 even though that section is written for
    unauthenticated endpoints specifically.
    """
    tenant = await service.create_tenant(db, name=payload.name, slug=payload.slug)
    return success_response(
        data=TenantSummaryOut.model_validate(tenant), status_code=201, message="Tenant provisioned"
    )


@router.get("/tenants", response_model=Envelope[list[TenantSummaryOut]])
async def list_tenants(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[SuperAdmin, Depends(service.get_current_superadmin)],
) -> JSONResponse:
    tenants = await TenantRepository(db).list()
    return success_response(data=[TenantSummaryOut.model_validate(t) for t in tenants])
