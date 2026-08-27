"""Device-credential resolution for the public `POST /registrations/walk-in`
endpoint (API-13) — the walk-in equivalent of `core.tenancy`'s JWT-based
`get_tenant`/`get_current_user` chain, keyed by a provisioned device instead
of a bearer token. See add-walkin-visitor-registration/design.md Decision 3.
"""

import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Annotated, Literal, NoReturn

import structlog
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.config import settings
from vmss_api.core.database import get_db, tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.core.security import verify_password
from vmss_api.org_structure.repository import BranchRepository
from vmss_api.registrations.repository import RegistrationDeviceKeyRepository
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.repository import TenantRepository


@dataclass
class RegistrationDeviceContext:
    tenant: Tenant
    branch_id: uuid.UUID


_INVALID_DEVICE_KEY_DETAIL = "Invalid device credential"
_DEFAULT_UNCONFIGURED_DETAIL = "Registration service is not configured for this environment"


def _reject_unconfigured_default(
    event: str, *, reason: Literal["not_found", "inactive"], **fields: str
) -> NoReturn:
    """Shared by both `_resolve_default_device_context` failure branches
    (no default tenant, no default branch) — a server-side configuration
    gap, not a property of the caller's request, so it's always logged at
    `ERROR` (per `logging-observability.md` §3) with the same 401 detail.

    `reason` distinguishes "no such row exists" from "the row exists but is
    inactive" so an operator can tell from the log alone whether the fix is
    provisioning a missing tenant/branch or re-activating an existing one,
    without reading this source file.
    """
    logger.error(event, reason=reason, **fields)
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=_DEFAULT_UNCONFIGURED_DETAIL)


async def _resolve_default_device_context(db: AsyncSession) -> RegistrationDeviceContext:
    """Fallback used when the caller sends no `X-Device-Key` at all — e.g.
    the public web portal, which (unlike the Flutter kiosk app) has nowhere
    safe to hold a provisioned device secret. Tenant/branch still come from
    server-side config (`settings.default_tenant_slug` /
    `settings.registration_default_branch_code`), never from anything the
    caller supplies, per `security-architecture.md`'s "tenant_id is never
    read from a request body, query param, or path param and trusted" rule
    extended to branch (`add-walkin-visitor-registration/design.md`
    Decision 3).

    **Sanctioned default path, not a stopgap**: this path has no credential
    at all — it trades the device key's authentication away for
    availability, leaving `POST /registrations/walk-in` an unauthenticated
    write (and file-upload) endpoint against one fixed branch, protected
    only by the route's rate limit. That trade-off is the reviewed, intended
    behavior for callers with nowhere safe to hold a device secret (see
    `openspec/specs/registrations/spec.md`'s "authenticated by a device
    credential, not a user" requirement), not an open gap. Logged at WARNING
    so it stays visible/auditable rather than silently normalized. Binding
    this path to the visitor's OTP-verified `identity_verification` proof
    token remains a separate, not-yet-scheduled improvement — see
    `security-architecture.md` §2's "fake-entry prevention" open item.
    """
    logger.warning("registration_device_key_absent")
    tenant = await TenantRepository(db).get_by_slug(settings.default_tenant_slug)
    if tenant is None:
        _reject_unconfigured_default(
            "registration_default_tenant_unconfigured",
            reason="not_found",
            tenant_slug=settings.default_tenant_slug,
        )
    if not tenant.is_active:
        _reject_unconfigured_default(
            "registration_default_tenant_unconfigured",
            reason="inactive",
            tenant_slug=settings.default_tenant_slug,
        )

    async with tenant_session_scope(tenant.schema_name) as tenant_db:
        branch = await BranchRepository(tenant_db).get_by_code(
            settings.registration_default_branch_code
        )
    if branch is None:
        _reject_unconfigured_default(
            "registration_default_branch_unconfigured",
            reason="not_found",
            branch_code=settings.registration_default_branch_code,
        )
    if not branch.is_active:
        _reject_unconfigured_default(
            "registration_default_branch_unconfigured",
            reason="inactive",
            branch_code=settings.registration_default_branch_code,
        )

    structlog.contextvars.bind_contextvars(tenant_id=str(tenant.id), branch_id=str(branch.id))
    return RegistrationDeviceContext(tenant=tenant, branch_id=branch.id)


async def get_registration_device(
    db: Annotated[AsyncSession, Depends(get_db)],
    x_device_key: Annotated[str | None, Header(alias="X-Device-Key")] = None,
) -> RegistrationDeviceContext:
    """Resolves the caller's tenant + branch from `X-Device-Key`, the same
    shape of auth-routing problem `platform.models.TenantUserIndex` solves
    for login (`database-architecture.md` §2): which tenant schema to open
    has to be known before anything tenant-scoped (here: the branch itself)
    can be checked. Never trusts a client-supplied tenant/branch id — there
    is none in the request at all, by design (spec.md "Walk-in registration
    is authenticated by a device credential, not a user").

    `X-Device-Key` is optional: a missing header falls back to
    `_resolve_default_device_context` above instead of rejecting the request
    outright — see that function's docstring for the security trade-off this
    implies.

    Argon2 hashes are salted, so a matching key can't be found with a
    `WHERE key_hash = ...` lookup — every active key is compared against in
    Python instead. The active-key set is expected to stay small (one per
    branch that has walk-in registration enabled).
    """
    if x_device_key is None:
        return await _resolve_default_device_context(db)

    device_repo = RegistrationDeviceKeyRepository(db)
    matched = None
    for candidate in await device_repo.list_active():
        if verify_password(x_device_key, candidate.key_hash):
            matched = candidate
            break
    if matched is None:
        logger.warning("registration_device_key_invalid")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=_INVALID_DEVICE_KEY_DETAIL)

    tenant = await TenantRepository(db).get(matched.tenant_id)
    if tenant is None or not tenant.is_active:
        logger.warning("registration_device_tenant_inactive", tenant_id=str(matched.tenant_id))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=_INVALID_DEVICE_KEY_DETAIL)

    async with tenant_session_scope(tenant.schema_name) as tenant_db:
        branch = await BranchRepository(tenant_db).get(matched.branch_id)
    if branch is None or not branch.is_active:
        logger.warning("registration_device_branch_inactive", branch_id=str(matched.branch_id))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=_INVALID_DEVICE_KEY_DETAIL)

    structlog.contextvars.bind_contextvars(tenant_id=str(tenant.id), branch_id=str(branch.id))
    return RegistrationDeviceContext(tenant=tenant, branch_id=branch.id)


async def get_registration_tenant_db(
    device: Annotated[RegistrationDeviceContext, Depends(get_registration_device)],
) -> AsyncGenerator[AsyncSession]:
    """Tenant-bound session for the resolved device's tenant — the walk-in
    counterpart of `core.tenancy.get_tenant_db`, keyed off
    `get_registration_device` instead of a JWT claim.
    """
    async with tenant_session_scope(device.tenant.schema_name) as session:
        yield session
