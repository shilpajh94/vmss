"""Shared `Idempotency-Key` cache helpers (api-conventions.md §3).

Import these — do not re-implement a per-feature copy. `namespace` must
match the feature segment already used in that feature's existing cache
keys (e.g. `"invitations"`, `"audit-trail"`, `"identity-verification"`) so
this refactor doesn't invalidate any key cached before it.
"""

import json
import uuid

from fastapi.responses import JSONResponse

from vmss_api.core.redis import get_redis

IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60


def _idempotency_cache_key(tenant_id: uuid.UUID, namespace: str, idempotency_key: str) -> str:
    return f"vmss:{tenant_id}:{namespace}:idempotency:{idempotency_key}"


async def cached_response(
    tenant_id: uuid.UUID, namespace: str, idempotency_key: str | None
) -> JSONResponse | None:
    """A retried request with the same `Idempotency-Key` returns the
    original response instead of re-processing the mutation.
    """
    if idempotency_key is None:
        return None
    redis = await get_redis()
    cached = await redis.get(_idempotency_cache_key(tenant_id, namespace, idempotency_key))
    if cached is None:
        return None
    payload = json.loads(cached)
    return JSONResponse(content=payload["body"], status_code=payload["status"])


async def cache_response(
    tenant_id: uuid.UUID,
    namespace: str,
    idempotency_key: str | None,
    response: JSONResponse,
) -> None:
    if idempotency_key is None:
        return
    redis = await get_redis()
    await redis.set(
        _idempotency_cache_key(tenant_id, namespace, idempotency_key),
        json.dumps({"status": response.status_code, "body": json.loads(bytes(response.body))}),
        ex=IDEMPOTENCY_TTL_SECONDS,
    )
