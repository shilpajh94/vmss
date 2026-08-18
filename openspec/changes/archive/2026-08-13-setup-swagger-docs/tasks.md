## 1. OpenAPI Metadata & Tags

- [x] 1.1 Source the OpenAPI `version` from installed package metadata
      (`importlib.metadata.version("vmss-api")`, matching `pyproject.toml`'s
      `[project].version`) instead of a new `Settings` field — avoids a
      second source of truth for the same value. No `.env.example` entry
      needed since this isn't a deployer-configurable setting.
- [x] 1.2 Pass `title=settings.app_name`, `version=<package version>`, and
      a short `description` into `FastAPI(...)` in `main.py`.
- [x] 1.3 Add an `openapi_tags` list to `main.py` with one entry (`name` +
      `description`) per feature tag currently in use (`auth`,
      `organizations`), passed into `FastAPI(...)`.

## 2. Environment-Gated Documentation Endpoints

- [x] 2.1 In `main.py`, compute `docs_url`, `redoc_url`, and `openapi_url` as
      `None` when `settings.environment.lower() == "production"`, otherwise
      their FastAPI defaults (`/docs`, `/redoc`, `/openapi.json`). Factored
      into a pure `_docs_urls(environment)` helper and an app-factory
      `create_app(environment=None)` so the production-gated branch is
      unit-testable without mutating the process-wide `settings` singleton.
- [x] 2.2 Pass the computed values into `FastAPI(...)`.

## 3. Bearer Security Scheme

- [x] 3.1 In `core/security.py`, replace `_oauth2_scheme =
      OAuth2PasswordBearer(tokenUrl=...)` with
      `_bearer_scheme = HTTPBearer(auto_error=False)`.
- [x] 3.2 Update `get_current_user`'s dependency on the scheme to accept the
      resulting `HTTPAuthorizationCredentials | None` and pass
      `credentials.credentials` (the raw token string) to `decode_token`,
      preserving the existing "not authenticated" 401 behavior when absent.
- [x] 3.3 Generate the OpenAPI schema locally and confirm a route guarded by
      `get_current_user`/`require_permission` now carries a bearer security
      requirement (padlock in Swagger UI). Verified: `GET /api/v1/organizations/me`
      now shows `"security": [{"HTTPBearer": []}]` in the generated schema.

## 4. camelCase Schema Verification

- [x] 4.1 Generated the OpenAPI schema locally and found a bigger gap than
      expected: every route returned a raw `JSONResponse` with no
      `response_model`, so Swagger didn't just show the wrong casing — it
      showed no response schema at all for any endpoint (`components.schemas`
      only had `LoginRequest`). Paused and confirmed with the user how far to
      take the fix (see conversation): fix it everywhere now, since the
      current surface is only two feature endpoints plus health.
- [x] 4.2 Added `Envelope[T]` (`core/schemas.py`) documenting
      `success_response`'s real `{success, message, data}` shape, and set
      `response_model=Envelope[...]` on `/health`, `/health/ready`,
      `POST /auth/login`, and `GET /organizations/me`. Regenerated the schema
      and confirmed every one of those now renders camelCase properties
      (`isActive`, `accessToken`, `organizationId`-shaped fields, etc.) with
      no per-route `by_alias` override needed — confirming the design's
      original bet that `CamelModel`'s alias generator is sufficient once a
      `response_model` actually exists to apply it to.

## 5. Router-Registration Test

- [x] 5.1 Added `tests/test_api_documentation.py::test_every_feature_router_is_registered_in_api_router`,
      discovering every `src/vmss_api/<feature>/router.py` (excluding
      `core`) and asserting each route is present in `app.openapi()["paths"]`.
      Caught a real bug in the first draft: `route.path` on an `APIRouter`
      already includes that router's own `prefix`, so concatenating the
      prefix again produced `/auth/auth/login` and failed — fixed by using
      `route.path` as-is (see the corresponding design.md correction).
- [x] 5.2 Added `test_docs_reachable_in_non_production`, asserting `/docs`,
      `/redoc`, and `/openapi.json` return `200` via the existing `client`
      fixture (environment is `test`, i.e. non-production).
- [x] 5.3 Added `test_docs_disabled_in_production`, building an independent
      app via `create_app(environment="production")` and asserting all three
      return `404` — no mutation of the shared `settings` singleton needed.
- [x] 5.4 Added `test_authorize_flow_end_to_end`, plus confirmed
      `organizations/tests.py::test_get_my_organization_requires_auth` (401
      with no header) and `test_get_my_organization_requires_permission`
      (403 for an authenticated-but-unauthorized caller) already cover the
      rest of this scenario end to end and still pass after the
      `HTTPBearer` swap — no changes needed there.
      Also added, beyond what this task listed: `test_openapi_metadata_identifies_the_api`,
      `test_protected_routes_declare_bearer_security`, and
      `test_response_schemas_render_camel_case` — turning the manual
      verification in tasks 3.3/4.1 into permanent regression coverage for
      every spec requirement, not just the router-registration one.

## 6. New Rule File

- [x] 6.1 Created `.claude/rules/api-documentation.md` covering: every route
      must declare `response_model=Envelope[...]` (§1); registering a router
      is a three-step combined change — `api.py`, `main.py`'s
      `openapi_tags`, and the registration test (§2); environment-gated docs
      availability (§3); the `HTTPBearer` Authorize flow (§4); and that
      camelCase rendering is automatic once a `response_model` exists, not a
      manual per-route step (§5).

## 7. Docs & Config Sync

- [x] 7.1 Not applicable — task 1.1 sourced the version from package metadata
      instead of a new `Settings` field, so there's no new setting to add to
      `.env.example`. No other setting was touched by this change.
- [x] 7.2 Added `docs/api-documentation.md` describing the environment-gating
      table, the Authorize flow, and what a new endpoint needs
      (`response_model=Envelope[...]` + a tag entry).

## 8. Verification

- [x] 8.1 `ruff check` and `ruff format --check` both clean. Fixed two
      findings along the way: `Envelope` used `Generic[T]` instead of the
      PEP 695 `class Envelope[T](CamelModel)` syntax ruff expects at this
      `target-version`, and one line in the new test file exceeded the
      100-char limit.
- [x] 8.2 `mypy` clean on `core/` and on the full `vmss_api` package.
- [x] 8.3 Full suite green: 13 passed (5 pre-existing + 8 new in
      `tests/test_api_documentation.py`).
