import uuid

import structlog
from fastapi import HTTPException, Request
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from vmss_api.core.logging import logger
from vmss_api.core.responses import error_response


class RequestIdMiddleware:
    """Stamps every request with an id so a log line can be traced end to end.

    Binds it into structlog's contextvars so every log line emitted for this
    request — router, service, repository — inherits it automatically; see
    logging-observability.md §1.

    Implemented as a plain ASGI callable, not `starlette.middleware.base.
    BaseHTTPMiddleware` — Starlette's own docs note that base class can let
    an exception raised downstream bypass the app's registered exception
    handlers, which previously let an unhandled exception reach the client
    as a raw framework traceback instead of `unhandled_exception_handler`'s
    standard envelope. A bare ASGI callable sits directly in the chain with
    no such gap.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = Headers(scope=scope).get("x-request-id") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(raw=message["headers"]).append("X-Request-ID", request_id)
            await send(message)

        await self.app(scope, receive, send_with_request_id)


async def http_exception_handler(request: Request, exc: HTTPException):
    """Every `raise HTTPException(...)` in the codebase (401/403/404/409, ...)
    otherwise falls through to FastAPI's default `{"detail": ...}` body,
    bypassing the `{success, message, errors}` envelope every other response
    uses. See security-architecture.md §1.
    """
    return error_response(message=str(exc.detail), status_code=exc.status_code)


async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=exc,
    )
    return error_response(message="An unexpected error occurred.", status_code=500)
