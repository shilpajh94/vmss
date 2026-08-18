import uuid

import structlog
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from vmss_api.core.logging import logger
from vmss_api.core.responses import error_response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Stamps every request with an id so a log line can be traced end to end.

    Binds it into structlog's contextvars so every log line emitted for this
    request — router, service, repository — inherits it automatically; see
    logging-observability.md §1.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


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
