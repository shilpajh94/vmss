import importlib
import pkgutil
import re

import pytest
from httpx import ASGITransport, AsyncClient

import vmss_api
from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.invitations.schemas import InvitationCreate
from vmss_api.main import app, create_app
from vmss_api.tenant.models import Tenant


def _discover_feature_routers() -> list[tuple[str, object]]:
    """Every immediate subpackage of `vmss_api` (except `core`) that defines
    a `router.py` with a module-level `router` — discovery-based so this list
    can't go stale the way a hand-maintained one could."""
    routers = []
    for module_info in pkgutil.iter_modules(vmss_api.__path__):
        if not module_info.ispkg or module_info.name == "core":
            continue
        try:
            router_module = importlib.import_module(f"vmss_api.{module_info.name}.router")
        except ModuleNotFoundError:
            continue
        router = getattr(router_module, "router", None)
        if router is not None:
            routers.append((module_info.name, router))
    return routers


def _flatten_routes(router) -> list:
    """A feature's `router.py` may itself compose several prefixed
    sub-routers via `include_router()` (e.g. `org_structure`'s
    company/branch/building/... routers) rather than declaring one flat
    `APIRouter`. In that case `router.routes` holds lazy `_IncludedRouter`
    wrappers, not `APIRoute` objects with a `.path` — descend into
    `original_router.routes` to reach the real routes, recursively, since
    nesting could in principle go more than one level deep.
    """
    routes = []
    for route in router.routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            routes.extend(_flatten_routes(original_router))
        else:
            routes.append(route)
    return routes


def test_every_feature_router_is_registered_in_api_router() -> None:
    registered = app.openapi()["paths"]
    discovered = _discover_feature_routers()
    assert discovered, "expected at least one feature router to be discovered"

    for feature_name, router in discovered:
        for route in _flatten_routes(router):
            # `route.path` already includes every router's own `prefix` —
            # FastAPI bakes it in at `add_api_route` time.
            expected_suffix = route.path
            relevant_methods = {m.lower() for m in route.methods if m not in {"HEAD", "OPTIONS"}}
            matches = [
                path
                for path, methods in registered.items()
                if path.endswith(expected_suffix) and relevant_methods & methods.keys()
            ]
            assert matches, (
                f"{feature_name}.router.router's {sorted(relevant_methods)} "
                f"{expected_suffix} has no matching entry in the OpenAPI schema — "
                "is it registered in api.py's api_router?"
            )


async def test_docs_reachable_in_non_production(client: AsyncClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        response = await client.get(path)
        assert response.status_code == 200, path


async def test_docs_disabled_in_production() -> None:
    production_app = create_app(environment="production")
    transport = ASGITransport(app=production_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for path in ("/docs", "/redoc", "/openapi.json"):
            response = await ac.get(path)
            assert response.status_code == 404, path


def test_openapi_metadata_identifies_the_api() -> None:
    schema = app.openapi()
    assert schema["info"]["title"]
    assert schema["info"]["version"]
    assert schema["info"]["description"]

    used_tags = {
        tag
        for path in schema["paths"].values()
        for op in path.values()
        for tag in op.get("tags", [])
    }
    described_tags = {tag["name"]: tag.get("description") for tag in schema.get("tags", [])}
    for tag in used_tags:
        assert described_tags.get(tag), f"tag {tag!r} has no description in openapi_tags"


def test_protected_routes_declare_bearer_security() -> None:
    schema = app.openapi()
    protected = schema["paths"]["/api/v1/tenants/me"]["get"]
    assert protected["security"] == [{"HTTPBearer": []}]

    public = schema["paths"]["/api/v1/auth/login"]["post"]
    assert not public.get("security")


@pytest.mark.parametrize(
    ("schema_name", "expected_camel_props"),
    [
        ("TenantOut", {"id", "name", "slug", "timezone", "isActive"}),
        ("TokenResponse", {"accessToken", "refreshToken", "tokenType"}),
        ("BranchOut", {"id", "name", "code", "address", "isActive"}),
        ("UserOut", {"id", "email", "fullName", "isActive", "branchRoles"}),
        ("BranchRoleOut", {"roleName", "branchId"}),
        ("InvitationBranchOut", {"id", "name", "code", "address", "city"}),
        (
            "InvitationVisitorDetailOut",
            {"id", "fullName", "idProofType", "idProofUrl", "photoUrl"},
        ),
        (
            "InvitationDetailOut",
            {
                "branchId",
                "branch",
                "building",
                "department",
                "primaryContactIdProofType",
                "primaryContactIdProofUrl",
                "approvalRevertedAt",
                "approvalRevertedByUserId",
                "approvalRevertReason",
                "archivedAt",
                "checkedOutAutomatically",
            },
        ),
        (
            "InvitationOut",
            {
                "approvalRevertedAt",
                "approvalRevertedByUserId",
                "approvalRevertReason",
                "archivedAt",
                "checkedOutAutomatically",
            },
        ),
        ("InvitationListItemOut", {"archivedAt", "checkedOutAutomatically"}),
        ("InvitationRevertApprovalRequest", {"reason"}),
        (
            "InvitationQrCheckInOut",
            {
                "checkInStatus",
                "branch",
                "building",
                "department",
                "primaryContactIdProofType",
                "archivedAt",
                "checkedOutAutomatically",
            },
        ),
        (
            "MyDashboardOverviewOut",
            {"visitsToday", "insideNow", "awaitingApproval", "upcoming", "upcomingPreview"},
        ),
        (
            "MyUpcomingVisitorOut",
            {"trackingId", "primaryContactFullName", "preferredVisitDate", "preferredVisitTime"},
        ),
        (
            "DashboardOverviewOut",
            {
                "scheduledTodayCount",
                "checkedInTodayCount",
                "oldestPendingSubmittedAt",
                "generatedAt",
            },
        ),
        ("UpcomingVisitorOut", {"hostFullName", "preferredVisitDate", "preferredVisitTime"}),
        ("DashboardCheckInListItemOut", {"hostFullName"}),
        (
            "DashboardAnalyticsOut",
            {
                "dailyTrend",
                "statusBreakdown",
                "hourlyCheckInsToday",
                "topPurposes",
                "topDepartments",
                "generatedAt",
            },
        ),
        ("MyDashboardAnalyticsOut", {"dailyTrend", "statusBreakdown", "generatedAt"}),
        ("DailyTrendPointOut", {"checkedIn", "noShow"}),
        ("NotificationOut", {"createdAt", "readAt"}),
        ("UnreadCountOut", {"unreadCount"}),
        ("CalendarFeedOut", {"from", "to", "generatedAt", "days", "events", "truncated"}),
        (
            "CalendarEventOut",
            {
                "trackingId",
                "date",
                "time",
                "checkedInAt",
                "primaryContactFullName",
                "visitorCount",
                "hostFullName",
                "branchName",
                "visitorCategoryBadgeColor",
            },
        ),
        # audit-and-harden-api-and-web additive fields
        (
            "InvitationListItemOut",
            {"preferredVisitDate", "preferredVisitTime", "currentApprovalStep"},
        ),
        ("InvitationDetailOut", {"checkInDevice", "checkOutDevice"}),
        ("MyBranchRoleOut", {"roleName", "branchId", "permissionCodes"}),
    ],
)
def test_response_schemas_render_camel_case(schema_name: str, expected_camel_props: set) -> None:
    schema = app.openapi()
    component = schema["components"]["schemas"][schema_name]
    assert expected_camel_props <= component["properties"].keys()


def test_invitation_multipart_payload_examples_documented() -> None:
    """Regression test for a documentation bug: `Form(openapi_examples=...)`
    on a single field is silently dropped by FastAPI when the route combines
    more than one Form/File param into one synthesized body (verified against
    the installed FastAPI before writing the fix) — `openapi_extra` on the
    route is what actually reaches the schema, so this asserts against that
    real path rather than the one that doesn't work."""
    schema = app.openapi()
    request_body = schema["paths"]["/api/v1/invitations"]["post"]["requestBody"]
    examples = request_body["content"]["multipart/form-data"]["examples"]
    assert set(examples) == {"individual", "group"}

    for name, example in examples.items():
        submission = InvitationCreate.model_validate_json(example["value"]["payload"])
        assert submission.registration_type.value == name


def test_invitation_payload_description_is_self_documenting() -> None:
    """Regression test for a second documentation gap layered on top of the
    one above: Swagger UI does not apply `requestBody.examples` when
    rendering a `multipart/form-data` "Try it out" form (only for JSON
    bodies), so the schema-level examples asserted above are not actually
    visible on this project's `/docs` page without this fix. The `payload`
    Form field's own `description` renders unconditionally in Swagger's
    Parameters table, so the fix embeds both registration-type examples
    there instead of relying solely on the request-body-level examples."""
    schema = app.openapi()
    body_schema = schema["components"]["schemas"]["Body_create_invitation_api_v1_invitations_post"]
    description = body_schema["properties"]["payload"]["description"]

    blocks = re.findall(r"```json\n(.*?)\n```", description, re.DOTALL)
    assert len(blocks) == 2

    submissions = [InvitationCreate.model_validate_json(block) for block in blocks]
    assert {s.registration_type.value for s in submissions} == {"individual", "group"}


async def test_rate_limit_exceeded_returns_standard_error_envelope(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    """openspec/specs/rate-limiting/spec.md's "A Tripped Rate Limit Returns
    the Standard Error Envelope" requirement — every other rate-limit test
    in this codebase only asserts `status_code == 429`, never the body
    shape, so a regression in `main.py`'s `_rate_limit_exceeded_handler`
    (e.g. reverting to slowapi's raw default body) would go undetected.
    `GET /invitations/track` has no auth to fake, matching the pattern in
    `invitations/tests/::test_track_rate_limit_trips`.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", tenant.slug)
    monkeypatch.setattr(limiter, "enabled", True)
    responses = [
        await client.get("/api/v1/invitations/track", params={"trackingId": "INV-DEADBEEF"})
        for _ in range(25)
    ]
    tripped = next(r for r in responses if r.status_code == 429)
    body = tripped.json()
    assert body["success"] is False
    assert body["message"]


async def test_authorize_flow_end_to_end(client: AsyncClient, user: User) -> None:
    """Mirrors what Swagger's "Authorize" dialog does: obtain a token from
    POST /auth/login, then call a protected endpoint with it as a bearer
    header. See tenant/tests.py for the permission-denied and missing-auth
    variants of this same flow."""
    login = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "correct-password"}
    )
    token = login.json()["data"]["accessToken"]

    response = await client.get("/api/v1/tenants/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
