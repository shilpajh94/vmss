import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.audit import record_audit_log
from vmss_api.auth.models import User
from vmss_api.auth.schemas import TokenResponse
from vmss_api.core.config import settings
from vmss_api.core.database import get_db
from vmss_api.core.deps import get_current_user, get_tenant, get_tenant_db, require_permission
from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import success_response
from vmss_api.core.schemas import Envelope
from vmss_api.sso import service
from vmss_api.sso.models import SsoProvider, SsoRoleMapping
from vmss_api.sso.schemas import (
    SsoExchangeRequest,
    SsoProviderConfigIn,
    SsoProviderConfigOut,
    SsoProviderTestRequest,
    SsoProviderTestResult,
    SsoRoleMappingIn,
    SsoRoleMappingOut,
)
from vmss_api.tenant.models import Tenant

router = APIRouter(prefix="/auth/sso", tags=["sso"])


def _to_config_out(provider: SsoProvider) -> SsoProviderConfigOut:
    return SsoProviderConfigOut(
        id=provider.id,
        display_name=provider.display_name,
        discovery_url=provider.discovery_url,
        client_id=provider.client_id,
        client_secret_masked=provider.client_secret_masked,
        is_enabled=provider.is_enabled,
    )


def _to_mapping_out(mapping: SsoRoleMapping) -> SsoRoleMappingOut:
    return SsoRoleMappingOut(
        id=mapping.id,
        idp_group_claim_value=mapping.idp_group_claim_value,
        role_id=mapping.role_id,
        role_name=mapping.role.name,
    )


@router.get(
    "/config",
    response_model=Envelope[SsoProviderConfigOut],
    dependencies=[Depends(require_permission("sso-config:view"))],
)
async def get_config(tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)]) -> JSONResponse:
    provider = await service.get_provider_config(tenant_db)
    if provider is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SSO is not configured yet")
    return success_response(data=_to_config_out(provider))


@router.put(
    "/config",
    response_model=Envelope[SsoProviderConfigOut],
    dependencies=[Depends(require_permission("sso-config:manage"))],
)
async def put_config(
    payload: SsoProviderConfigIn,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    actor: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    provider = await service.save_provider_config(tenant_db, payload)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=actor.id,
        action="sso_config_saved",
        entity_type="SsoProvider",
        entity_id=provider.id,
        diff={"displayName": payload.display_name, "isEnabled": payload.is_enabled},
    )
    return success_response(data=_to_config_out(provider))


@router.post(
    "/config/test",
    response_model=Envelope[SsoProviderTestResult],
    dependencies=[Depends(require_permission("sso-config:manage"))],
)
async def test_config(payload: SsoProviderTestRequest) -> JSONResponse:
    result = await service.test_provider_config(payload)
    return success_response(data=result)


@router.get(
    "/role-mappings",
    response_model=Envelope[list[SsoRoleMappingOut]],
    dependencies=[Depends(require_permission("sso-config:view"))],
)
async def list_role_mappings(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    mappings = await service.list_role_mappings(tenant_db)
    return success_response(data=[_to_mapping_out(m) for m in mappings])


@router.post(
    "/role-mappings",
    response_model=Envelope[SsoRoleMappingOut],
    dependencies=[Depends(require_permission("sso-config:manage"))],
    status_code=status.HTTP_201_CREATED,
)
async def create_role_mapping(
    payload: SsoRoleMappingIn,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    actor: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    mapping = await service.create_role_mapping(tenant_db, payload)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=actor.id,
        action="sso_role_mapping_created",
        entity_type="SsoRoleMapping",
        entity_id=mapping.id,
        diff={"idpGroupClaimValue": mapping.idp_group_claim_value, "roleId": str(mapping.role_id)},
    )
    return success_response(data=_to_mapping_out(mapping), status_code=201)


@router.delete(
    "/role-mappings/{mapping_id}",
    dependencies=[Depends(require_permission("sso-config:manage"))],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_role_mapping(
    mapping_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    actor: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_role_mapping(tenant_db, mapping_id)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=actor.id,
        action="sso_role_mapping_deleted",
        entity_type="SsoRoleMapping",
        entity_id=mapping_id,
    )


@router.get("/{tenant_slug}/login")
@limiter.limit("3/minute")
async def start_login(
    request: Request, tenant_slug: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> RedirectResponse:
    """Public, unauthenticated — redirects the browser to the tenant's
    configured IdP. See spec.md's "SSO Login Initiation Redirects to the
    Tenant's Configured IdP" requirement. Rate-limited (3/min per IP), same
    as `POST /auth/login` — this is an alternate login entry point and
    `security-architecture.md` §2 requires rate limiting on every
    unauthenticated endpoint.
    """
    authorization_url = await service.start_login(db, tenant_slug)
    return RedirectResponse(authorization_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/callback")
@limiter.limit("3/minute")
async def callback(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
) -> RedirectResponse:
    """Public — the IdP's return redirect. No `response_model`: this always
    3xx-redirects rather than returning JSON, per
    `api-documentation.md`'s scope (only JSON-returning routes need one).
    Rate-limited (3/min per IP) — see `start_login`'s docstring.
    """
    exchange_code = await service.handle_callback(
        db, code=code, state=state, background_tasks=background_tasks
    )
    return RedirectResponse(
        f"{settings.sso_frontend_callback_url}?code={exchange_code}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.post("/exchange", response_model=Envelope[TokenResponse])
@limiter.limit("3/minute")
async def exchange(request: Request, payload: SsoExchangeRequest) -> JSONResponse:
    """Public — trades a short-lived, single-use exchange code (never the
    real token pair itself) for one. See spec.md's "Tokens Are Handed to
    the Caller Through a Short-Lived, Single-Use Exchange" requirement.
    Rate-limited (3/min per IP) — this is the endpoint that actually hands
    out real tokens, at least as sensitive as `POST /auth/login`.
    """
    tokens = await service.redeem_exchange_code(payload.code)
    return success_response(data=tokens)
