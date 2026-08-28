from importlib.metadata import version
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.api import api_router
from vmss_api.core.config import settings
from vmss_api.core.database import get_db
from vmss_api.core.logging import configure_logging
from vmss_api.core.middleware import (
    RequestIdMiddleware,
    http_exception_handler,
    unhandled_exception_handler,
)
from vmss_api.core.rate_limit import limiter
from vmss_api.core.redis import get_redis
from vmss_api.core.responses import error_response, success_response
from vmss_api.core.schemas import CamelModel, Envelope

configure_logging(settings.debug, settings.log_level)

_APP_VERSION = version("vmss-api")

_TAGS_METADATA = [
    {"name": "health", "description": "Liveness/readiness probes for the running process."},
    {
        "name": "auth",
        "description": (
            "Tenant-user login, access/refresh token issuance, the caller's own "
            "profile, and RBAC user/branch-role management."
        ),
    },
    {"name": "tenants", "description": "The tenant the authenticated caller belongs to."},
    {
        "name": "org-structure",
        "description": (
            "Branches/locations — the unit RBAC and per-request access "
            "(`X-Branch-ID`) are scoped to."
        ),
    },
    {
        "name": "platform",
        "description": (
            "Superadmin operations: platform login and tenant provisioning. "
            "Not reachable with a tenant-user access token."
        ),
    },
    {
        "name": "visitor-types",
        "description": (
            "Configurable visitor categories (with a per-category form schema) "
            "and the approval workflow rules attached to each one."
        ),
    },
    {
        "name": "invitations",
        "description": (
            "Pre-registration: employee-created single/group invitations, the "
            "public multi-step self-registration form the invited visitor "
            "completes, email/SMS + QR dispatch, and the public tracking-lookup "
            "endpoint."
        ),
    },
    {
        "name": "registrations",
        "description": (
            "Walk-in visitor registration: a visitor registers themselves on "
            "arrival with no prior invitation, authenticated by a branch's "
            "device credential (`X-Device-Key`) rather than a staff bearer "
            "token. Reuses the same visit-record contract pre-registration "
            "(`invitations`) does."
        ),
    },
    {
        "name": "reports",
        "description": (
            "Cross-branch rollups for admins — org-chart footprint and active "
            "headcount aggregated across every branch in the tenant."
        ),
    },
    {
        "name": "identity-verification",
        "description": (
            "OTP generation and verification for an email or phone identifier, "
            "over email/SMS/WhatsApp — public, unauthenticated, and not yet "
            "wired into invitation or walk-in registration creation."
        ),
    },
    {
        "name": "sso",
        "description": (
            "Staff OIDC single sign-on: per-tenant provider configuration, "
            "IdP-group-to-role mapping, the login-initiate/callback/exchange "
            "flow, and just-in-time account provisioning. Visitor login is "
            "unaffected."
        ),
    },
    {
        "name": "visit-info",
        "description": (
            "Public, kiosk-facing lookups backing the walk-in registration "
            "wizard's Visit Info step: host search, branch-scoped department "
            "listing, and configured purpose/duration options. Resolves "
            "tenant/branch the same way `POST /registrations/walk-in` does."
        ),
    },
]


class HealthStatus(CamelModel):
    status: str


def _docs_urls(environment: str) -> tuple[str | None, str | None, str | None]:
    """Swagger UI, ReDoc, and the raw OpenAPI schema are disabled in
    production - see the api-documentation capability spec."""
    if environment.lower() == "production":
        return None, None, None
    return "/docs", "/redoc", "/openapi.json"


def create_app(environment: str | None = None) -> FastAPI:
    """Builds a fully wired FastAPI app. `environment` overrides
    `settings.environment` for the docs-availability gate only, so tests can
    exercise the production-gated branch without touching the process-wide
    settings singleton."""
    env = environment if environment is not None else settings.environment
    docs_url, redoc_url, openapi_url = _docs_urls(env)

    app = FastAPI(
        title=settings.app_name,
        version=_APP_VERSION,
        description="Visitor Management SaaS — backend API.",
        debug=settings.debug,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        openapi_tags=_TAGS_METADATA,
    )

    def _rate_limit_exceeded_handler(request, exc):
        return error_response("Too many requests", 429)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    # Starlette's stub types every handler as accepting the base `Exception`,
    # which a handler registered for one specific subclass can never satisfy
    # per normal parameter-contravariance rules — a stub limitation, not a
    # real type mismatch: Starlette dispatches by the registered class, so
    # this handler only ever receives an `HTTPException` at runtime.
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["health"], response_model=Envelope[HealthStatus])
    async def health() -> JSONResponse:
        """Liveness — the process is up. Doesn't touch the DB/Redis."""
        return success_response(data=HealthStatus(status="ok"))

    @app.get("/health/ready", tags=["health"], response_model=Envelope[HealthStatus])
    async def health_ready(db: Annotated[AsyncSession, Depends(get_db)]) -> JSONResponse:
        """Readiness — the process AND its dependencies are actually usable."""
        await db.execute(text("SELECT 1"))
        await (await get_redis()).ping()
        return success_response(data=HealthStatus(status="ok"))

    return app


app = create_app()
