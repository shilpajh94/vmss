"""Shared `Idempotency-Key` handling (api-conventions.md §3;
api-compliance-hardening "Idempotency Keys Are Scoped to One Endpoint,
Caller, and Request").

A cached response is replayed only for a retry of the *same* request: the
same tenant, HTTP method and route, the same caller, and the same request
fingerprint (path, query and body). The key alone is not enough — before
this, every invitations mutation shared one namespace, so a key reused on
another endpoint (or an OTP verify for a different identifier) replayed the
first response, proof token included.

Routes take an `Idempotency` guard via `Depends(idempotency)`:

    cached = await idem.begin(tenant.id, "invitations", key, caller=..., body=...)
    if cached is not None:
        return cached
    ...
    await idem.store(response)

`begin` replays a cached response, rejects a key reused for a different
request (422), rejects a concurrent duplicate still in flight (409), or
takes the in-flight lock. The dependency releases the lock when the request
ends, success or error, so a failed attempt can be retried with its key.
"""

import hashlib
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import Request, status
from fastapi.responses import JSONResponse

from vmss_api.core.logging import logger
from vmss_api.core.redis import get_redis
from vmss_api.core.responses import error_response

IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60
# Long enough for the slowest mutation (multipart invitation create), short
# enough that a crashed worker's lock doesn't block a retry for long.
IN_FLIGHT_LOCK_SECONDS = 60


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class Idempotency:
    def __init__(self, request: Request) -> None:
        self._request = request
        self._record_key: str | None = None
        self._lock_key: str | None = None
        self._fingerprint = ""
        self._locked = False

    def _scope(self) -> str:
        route = self._request.scope.get("route")
        template = getattr(route, "path", self._request.url.path)
        return f"{self._request.method} {template}"

    async def begin(
        self,
        tenant_id: uuid.UUID,
        namespace: str,
        idempotency_key: str | None,
        *,
        caller: str,
        body: str = "",
    ) -> JSONResponse | None:
        """`caller` identifies who is retrying — a user or device id, or for
        a public OTP route the identifier being verified. `body` is the
        request's own payload (a JSON body, or a multipart `payload` field),
        which the dependency can't re-read once FastAPI has parsed it."""
        if idempotency_key is None:
            return None
        scope = _sha256(f"{self._scope()}|{caller}|{idempotency_key}")
        base = f"vmss:{tenant_id}:{namespace}:idempotency:{scope}"
        self._record_key, self._lock_key = base, f"{base}:in-flight"
        self._fingerprint = _sha256(f"{self._request.url.path}?{self._request.url.query}|{body}")
        redis = await get_redis()
        cached = await redis.get(self._record_key)
        if cached is not None:
            payload = json.loads(cached)
            if payload.get("fingerprint") != self._fingerprint:
                logger.warning("idempotency_key_reused_for_different_request", scope=self._scope())
                return error_response(
                    "This Idempotency-Key was already used for a different request",
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                )
            return JSONResponse(content=payload["body"], status_code=payload["status"])
        acquired = await redis.set(self._lock_key, "1", nx=True, ex=IN_FLIGHT_LOCK_SECONDS)
        if not acquired:
            return error_response(
                "A request with this Idempotency-Key is already being processed",
                status.HTTP_409_CONFLICT,
            )
        self._locked = True
        return None

    async def store(self, response: JSONResponse) -> None:
        if self._record_key is None:
            return
        redis = await get_redis()
        await redis.set(
            self._record_key,
            json.dumps(
                {
                    "status": response.status_code,
                    "body": json.loads(bytes(response.body)),
                    "fingerprint": self._fingerprint,
                }
            ),
            ex=IDEMPOTENCY_TTL_SECONDS,
        )

    async def release(self) -> None:
        if not self._locked or self._lock_key is None:
            return
        self._locked = False
        try:
            await (await get_redis()).delete(self._lock_key)
        except Exception:
            # The lock expires on its own; never fail a finished request here.
            logger.warning("idempotency_lock_release_failed", exc_info=True)


async def idempotency(request: Request) -> AsyncIterator[Idempotency]:
    guard = Idempotency(request)
    try:
        yield guard
    finally:
        await guard.release()
