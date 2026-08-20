"""Device-credential resolution for the public `POST /registrations/walk-in`
endpoint (API-13) — the walk-in equivalent of `core.tenancy`'s JWT-based
`get_tenant`/`get_current_user` chain, keyed by a provisioned device instead
of a bearer token. See add-walkin-visitor-registration/design.md Decision 3.
"""

import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Annotated

import structlog
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

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

    A missing header gets the same 401 an invalid one does (spec.md
    "Missing or invalid device credential") — `x_device_key` is deliberately
    optional-with-a-default rather than a required `Header(...)` param, since
    FastAPI would otherwise reject a missing one with its own 422 before this
    function ever runs.

    Argon2 hashes are salted, so a matching key can't be found with a
    `WHERE key_hash = ...` lookup — every active key is compared against in
    Python instead. The active-key set is expected to stay small (one per
    branch that has walk-in registration enabled).
    """
    if x_device_key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=_INVALID_DEVICE_KEY_DETAIL)

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
