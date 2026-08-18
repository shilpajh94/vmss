## Why

FastAPI already generates an OpenAPI schema and Swagger UI automatically, but
nothing in this project deliberately configures it: `/docs` is reachable
unchanged in every environment including production, the "Authorize" flow is
wired to `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")` even though
`/auth/login` actually takes a JSON body (`LoginRequest`) rather than the
OAuth2 form fields that flow expects — so Swagger's built-in login dialog
would 422 against the real endpoint — and there is no check that a new
feature's router actually gets registered in `api.py`, so a forgotten
`include_router` call would silently leave endpoints undocumented with
nothing failing. Fixing this now, while only `auth` and `organizations`
exist, is far cheaper than retrofitting once a dozen feature routers exist.

## What Changes

- Configure app-level OpenAPI metadata in `main.py`: title/version/description
  sourced from `settings`, plus per-feature `tags_metadata` so Swagger UI
  groups routes by feature with a short description instead of raw tag names.
- Gate documentation endpoints by environment: `/docs`, `/redoc`, and
  `/openapi.json` stay enabled in `local`/`dev`/`staging`; when
  `settings.environment == "production"` they are disabled (404), since a
  full endpoint/schema map is not something to publish on a public prod URL.
- Add an `HTTPBearer` security scheme to the OpenAPI spec so every route
  behind `get_current_user`/`require_permission` shows a padlock, and the
  Swagger "Authorize" dialog accepts a raw access token (obtained by calling
  `POST /auth/login` via "Try it out" first) instead of relying on the
  mismatched OAuth2-password flow described above. **BREAKING**: none of the
  currently-mismatched OAuth2 flow was usable anyway, so no client-facing
  contract changes.
- Confirm OpenAPI schemas render the camelCase field names the wire format
  actually uses (`CamelModel`'s alias), not the Python snake_case names, and
  correct the OpenAPI generation if FastAPI's default does not already do
  this for every route.
- Add a test asserting every `src/vmss_api/<feature>/router.py` module is
  registered in `api.py`'s `api_router`, so a forgotten registration is a
  failing test, not a silent gap in the docs.
- Add a new rule file, `.claude/rules/api-documentation.md`, capturing these
  Swagger/OpenAPI conventions (tags, descriptions, security scheme,
  environment gating, the router-registration guarantee) for every feature
  added after this change.

## Capabilities

### New Capabilities
- `api-documentation`: how the FastAPI app exposes its OpenAPI schema and
  Swagger/ReDoc UI — metadata, per-environment availability, the bearer
  security scheme, and the guarantee that every registered router's endpoints
  are discoverable in the generated docs.

### Modified Capabilities
- None — no existing `openspec/specs/` capabilities exist yet in this project.

## Impact

- `src/vmss_api/main.py` — OpenAPI metadata, tags_metadata, conditional
  `docs_url`/`redoc_url`/`openapi_url`.
- `src/vmss_api/core/config.py` — no new setting expected beyond the existing
  `environment` field; confirm during design whether an explicit
  `enable_api_docs` override is warranted.
- `src/vmss_api/core/security.py` — add the `HTTPBearer` scheme alongside (or
  in place of) the current `OAuth2PasswordBearer` dependency.
- `src/vmss_api/auth/router.py`, `src/vmss_api/organizations/router.py` (and
  every future feature router) — tag descriptions.
- `tests/` — new router-registration test.
- `.claude/rules/api-documentation.md` — new rule file (created during
  implementation, not during this planning step).
