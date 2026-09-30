"""Verified-contact proof-token gating and tenant resolution for the public,
unauthenticated `visitor-return-visit` endpoints. See
`openspec/changes/visitor-return-visit-login/design.md` Decision 2.
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.database import get_db, tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.core.security import decode_token
from vmss_api.core.tenancy import DefaultTenantUnresolved, resolve_default_tenant

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class VerifiedContact:
    identifier: str
    channel: str


async def verified_contact(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> VerifiedContact:
    """Requires an `identity_verified` proof token
    (`identity_verification/service.py::verify_otp`'s `proof_token`) — never
    a staff access/refresh token or any other token type. `decode_token`
    alone only verifies the signature/expiry; nothing about it enforces
    `type`, so that check happens here (spec.md "A Non-Identity-Verification
    Token Is Rejected"). The token's `tenant_id` claim is not read: tenant
    context is resolved independently via `default_tenant_db` below, the
    same single-default-tenant posture `identity_verification` itself uses.
    """
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "identity_verified":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Not a verified-contact proof token"
        )
    return VerifiedContact(identifier=payload["sub"], channel=payload.get("channel", ""))


async def default_tenant_db(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncGenerator[AsyncSession]:
    """Same single-default-tenant resolution `identity_verification` and
    `registrations` already use — this unauthenticated capability has no
    other tenant signal (spec.md "Lookup Resolves the Same Single Default
    Tenant as Identity Verification"). An unresolvable default tenant is a
    server-side misconfiguration, logged at `ERROR` distinguishing "no such
    tenant" from "tenant inactive", same posture as
    `identity_verification/deps.py::default_tenant_id`.
    """
    try:
        tenant = await resolve_default_tenant(db)
    except DefaultTenantUnresolved as exc:
        logger.error("visitor_return_visit_default_tenant_unconfigured", reason=exc.reason)
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive"
        ) from exc
    structlog.contextvars.bind_contextvars(tenant_id=str(tenant.id))
    async with tenant_session_scope(tenant.schema_name) as session:
        yield session
