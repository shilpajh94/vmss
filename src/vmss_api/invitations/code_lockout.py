"""Failed-attempt lockout for the public check-in-by-code endpoints
(add-sms-numeric-checkin-code design.md Decision 5). The 8-digit code is far
weaker than the encrypted QR token, so beyond the per-minute `slowapi` limit
an IP that keeps submitting unknown codes is locked out for a window.

Fails closed: if Redis is unreachable the request is refused (503) rather
than allowing unthrottled guessing.
"""

import uuid

import structlog
from fastapi import HTTPException, status
from redis.exceptions import RedisError

from vmss_api.core.config import settings
from vmss_api.core.redis import get_redis

logger = structlog.get_logger()


def _key(tenant_id: uuid.UUID, ip: str) -> str:
    return f"vmss:{tenant_id}:invitations:code_fail:{ip}"


async def ensure_not_locked_out(tenant_id: uuid.UUID, ip: str) -> None:
    try:
        failures = await (await get_redis()).get(_key(tenant_id, ip))
    except RedisError as exc:
        logger.error("checkin_code_lockout_unavailable", tenant_id=str(tenant_id), error=str(exc))
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service temporarily unavailable"
        ) from exc
    if failures is not None and int(failures) >= settings.checkin_code_max_failures:
        logger.warning("checkin_code_locked_out", tenant_id=str(tenant_id), ip=ip)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many failed attempts; try again later"
        )


async def record_failure(tenant_id: uuid.UUID, ip: str) -> None:
    try:
        redis = await get_redis()
        key = _key(tenant_id, ip)
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, settings.checkin_code_lockout_seconds)
    except RedisError as exc:
        logger.error("checkin_code_lockout_unavailable", tenant_id=str(tenant_id), error=str(exc))
