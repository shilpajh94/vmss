from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.database import get_db
from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import success_response
from vmss_api.core.schemas import Envelope, SortOrder
from vmss_api.platform import service
from vmss_api.platform.models import SuperAdmin
from vmss_api.platform.schemas import (
    PlatformLoginRequest,
    PlatformTokenResponse,
    TenantCreateRequest,
    TenantSortableField,
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
    sort_by: Annotated[TenantSortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    """No pagination here — deliberately deferred, not an oversight. Per
    `api-conventions.md` §2, wrapping today's flat `data: [...]` in a
    pagination envelope changes the response shape for existing clients,
    which is a breaking change; `design.md`'s Decision 3 keeps this
    unpaginated in `v1` and reports it as a follow-up instead. `sort_by`/
    `sort_order` are purely additive optional params, so they're safe to
    add without that same concern. `TenantRepository.list()` already
    returns its (small, registry-sized) result set in full, so sorting it
    in Python here avoids widening this change's touched files with an
    `ORDER BY` addition to `tenant/repository.py`, which belongs to a
    different feature package.
    """
    tenants = await TenantRepository(db).list()
    reverse = sort_order == SortOrder.desc
    key_fn = {
        "name": lambda t: t.name.lower(),
        "slug": lambda t: t.slug,
        "created_at": lambda t: t.created_at,
    }[sort_by]
    tenants = sorted(tenants, key=key_fn, reverse=reverse)
    return success_response(data=[TenantSummaryOut.model_validate(t) for t in tenants])
