import uuid

import structlog
from fastapi import HTTPException, Request
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from vmss_api.core.config import settings
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

    Registered for `HTTPException`, Starlette dispatches this through
    `ExceptionMiddleware` — which sits *inside* `CORSMiddleware` in the
    middleware stack, so the response it returns still gets CORS headers
    applied normally. No special-casing needed here; contrast
    `unhandled_exception_handler` below.
    """
    return error_response(message=str(exc.detail), status_code=exc.status_code)


def _add_cors_headers(response: Response, request: Request) -> None:
    """Starlette always routes a handler registered for the bare `Exception`
    class through `ServerErrorMiddleware`, which — unlike `ExceptionMiddleware`
    — is the *outermost* layer of the stack, ahead of `CORSMiddleware`
    (`Starlette.build_middleware_stack`). A crash here therefore unwinds past
    `CORSMiddleware` entirely instead of through it, so the 500 it produces
    never gets `Access-Control-Allow-Origin` etc. added — a browser then
    reports a misleading "CORS error" for what's actually an unrelated server
    crash. Reapplying the same allow-list check here is the standard
    workaround for this Starlette/FastAPI gap.
    """
    origin = request.headers.get("origin")
    if origin is not None and origin in settings.cors_allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"


async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = structlog.contextvars.get_contextvars().get("request_id", "")
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=exc,
    )
    response = error_response(message="An unexpected error occurred.", status_code=500)
    # Same ServerErrorMiddleware gap bypasses `RequestIdMiddleware` too — echo
    # the id here so a crash stays traceable per logging-observability.md §1.
    if request_id:
        response.headers["X-Request-ID"] = request_id
    _add_cors_headers(response, request)
    return response
