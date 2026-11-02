"""rate-limiting spec "Every Unauthenticated Endpoint Is Rate-Limited"
(security-architecture.md §2): walks every route the app serves and fails,
naming the route, if one that needs no bearer token has no `slowapi` limit.
A new public route therefore can't ship unlimited by accident.
"""

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from vmss_api.core.rate_limit import limiter
from vmss_api.main import app

# Liveness/readiness probes are polled by the orchestrator, not clients.
_EXEMPT_PATHS = {"/health", "/health/ready"}

# A route depending on any of these requires a valid bearer token.
_AUTHENTICATING_DEPENDENCIES = {"get_current_user", "get_current_superadmin", "_check"}


def _flatten_routes(router) -> list:
    """Same descent as `test_api_documentation.py::_flatten_routes`:
    included routers are lazy `_IncludedRouter` wrappers."""
    routes = []
    for route in router.routes:
        original_router = getattr(route, "original_router", None)
        routes.extend(_flatten_routes(original_router) if original_router else [route])
    return routes


def _dependency_names(dependant: Dependant, names: set[str]) -> set[str]:
    for sub in dependant.dependencies:
        names.add(getattr(sub.call, "__name__", type(sub.call).__name__))
        _dependency_names(sub, names)
    return names


def test_every_unauthenticated_route_is_rate_limited() -> None:
    unlimited = []
    for route in _flatten_routes(app):
        if not isinstance(route, APIRoute) or route.path in _EXEMPT_PATHS:
            continue
        if _dependency_names(route.dependant, set()) & _AUTHENTICATING_DEPENDENCIES:
            continue
        key = f"{route.endpoint.__module__}.{route.endpoint.__name__}"
        if key not in limiter._route_limits:
            unlimited.append(f"{sorted(route.methods)} {route.path}")
    assert not unlimited, f"unauthenticated routes without a rate limit: {unlimited}"


def test_inventory_sees_the_public_routes() -> None:
    """Guards the test above against silently matching nothing (e.g. if the
    router-flattening stops descending into included routers)."""
    public_paths = {
        route.path
        for route in _flatten_routes(app)
        if isinstance(route, APIRoute)
        and not _dependency_names(route.dependant, set()) & _AUTHENTICATING_DEPENDENCIES
    }
    assert {"/form-builder/effective", "/auth/login", "/registrations/walk-in"} <= public_paths
