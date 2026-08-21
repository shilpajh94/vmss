"""Public, unauthenticated OTP request/verify endpoints (API-15). See
`add-identity-verification-otp/proposal.md` and `design.md`.
"""

import json
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse

from vmss_api.core.rate_limit import limiter
from vmss_api.core.redis import get_redis
from vmss_api.core.responses import error_response, success_response
from vmss_api.core.schemas import Envelope
from vmss_api.identity_verification import service
from vmss_api.identity_verification.deps import default_tenant_id
from vmss_api.identity_verification.schemas import (
    OtpRequestIn,
    OtpRequestOut,
    OtpVerifyIn,
    OtpVerifyOut,
)
from vmss_api.identity_verification.senders import GatewayNotConfiguredError, SmsDispatchError

router = APIRouter(prefix="/identity-verification", tags=["identity-verification"])

_IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60

_IDEMPOTENCY_KEY_HEADER = Header(
    alias="Idempotency-Key",
    description=(
        "Optional. Omitting it forgoes retry-dedup safety — a retried "
        "request with no key may dispatch a second code or count a second "
        "verification attempt. See api-conventions.md §3."
    ),
)


def _idempotency_cache_key(tenant_id: uuid.UUID, idempotency_key: str) -> str:
    return f"vmss:{tenant_id}:identity-verification:idempotency:{idempotency_key}"


async def _cached_response(
    tenant_id: uuid.UUID, idempotency_key: str | None
) -> JSONResponse | None:
    """api-conventions.md §3 — mirrors
    `invitations/router.py`'s `_cached_response`/`_cache_response` pair.
    """
    if idempotency_key is None:
        return None
    redis = await get_redis()
    cached = await redis.get(_idempotency_cache_key(tenant_id, idempotency_key))
    if cached is None:
        return None
    payload = json.loads(cached)
    return JSONResponse(content=payload["body"], status_code=payload["status"])


async def _cache_response(
    tenant_id: uuid.UUID, idempotency_key: str | None, response: JSONResponse
) -> None:
    if idempotency_key is None:
        return
    redis = await get_redis()
    await redis.set(
        _idempotency_cache_key(tenant_id, idempotency_key),
        json.dumps({"status": response.status_code, "body": json.loads(bytes(response.body))}),
        ex=_IDEMPOTENCY_TTL_SECONDS,
    )


@router.post("/otp/request", response_model=Envelope[OtpRequestOut])
@limiter.limit("20/minute")
async def request_otp(
    request: Request,
    payload: OtpRequestIn,
    tenant_id: Annotated[uuid.UUID, Depends(default_tenant_id)],
    idempotency_key: Annotated[str | None, _IDEMPOTENCY_KEY_HEADER] = None,
) -> JSONResponse:
    """A visitor requests a one-time code for an email or phone identifier,
    delivered over their chosen channel. Public, no bearer token — see
    `logging-observability.md` §2 (`tenant_id`, no `user_id`, since no user
    is authenticated).
    """
    structlog.contextvars.bind_contextvars(tenant_id=str(tenant_id))

    cached = await _cached_response(tenant_id, idempotency_key)
    if cached is not None:
        return cached

    try:
        result = await service.request_otp(
            tenant_id=tenant_id, identifier=payload.identifier, channel=payload.channel
        )
    except service.PerIdentifierRateLimitExceeded:
        # Deliberately not cached: the rate-limit window resets on its own,
        # and caching a 429 would keep replaying it past that reset.
        return error_response("Too many requests", status.HTTP_429_TOO_MANY_REQUESTS)
    except GatewayNotConfiguredError:
        response = error_response(
            "This delivery channel is not available right now",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        await _cache_response(tenant_id, idempotency_key, response)
        return response
    except SmsDispatchError:
        # Transient (design.md's Idempotency-Key refinement) — deliberately
        # NOT cached, so a retry with the same key re-attempts dispatch
        # instead of replaying a Twilio-side failure forever.
        return error_response(
            "This delivery channel is temporarily unavailable",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    response = success_response(
        data=OtpRequestOut(identifier=result.identifier, channel=result.channel)
    )
    await _cache_response(tenant_id, idempotency_key, response)
    return response


@router.post("/otp/verify", response_model=Envelope[OtpVerifyOut])
@limiter.limit("20/minute")
async def verify_otp(
    request: Request,
    payload: OtpVerifyIn,
    tenant_id: Annotated[uuid.UUID, Depends(default_tenant_id)],
    idempotency_key: Annotated[str | None, _IDEMPOTENCY_KEY_HEADER] = None,
) -> JSONResponse:
    """A visitor submits the code they received to prove control of the
    identifier, receiving a short-lived verified-contact proof in return.
    """
    structlog.contextvars.bind_contextvars(tenant_id=str(tenant_id))

    cached = await _cached_response(tenant_id, idempotency_key)
    if cached is not None:
        return cached

    try:
        result = await service.verify_otp(
            tenant_id=tenant_id,
            identifier=payload.identifier,
            channel=payload.channel,
            code=payload.code,
        )
    except service.InvalidOrExpiredCode:
        # Cached (unlike the request endpoint's transient-failure case):
        # verification is a deterministic Redis-state check, not a live
        # third-party call, so a retry with the same key must not count a
        # second attempt against the failed-attempt cap.
        response = error_response("Invalid or expired code", status.HTTP_400_BAD_REQUEST)
        await _cache_response(tenant_id, idempotency_key, response)
        return response

    response = success_response(
        data=OtpVerifyOut(
            identifier=result.identifier,
            channel=result.channel,
            proof_token=result.proof_token,
        )
    )
    await _cache_response(tenant_id, idempotency_key, response)
    return response
