# API Documentation (Swagger/OpenAPI) — VMSS_API

`fastapi-architecture.md` §5 mandates `success_response`/`error_response` for
every JSON endpoint; this covers what else a route needs so it actually shows
up, correctly, in the generated Swagger UI (`/docs`) and OpenAPI schema. None
of this is optional per-route polish — a route with no `response_model` isn't
"documented later," it's undocumented now, indistinguishable in Swagger from
a route that returns nothing.

## 1. Every Route Declares a `response_model`

- Every route that returns `success_response(data=...)` MUST set
  `response_model=Envelope[<YourResponseSchema>]` on the route decorator,
  where `Envelope` is the generic wrapper in `core/schemas.py` documenting
  `success_response`'s actual `{success, message, data}` shape.
  `<YourResponseSchema>` is the feature's own `CamelModel` subclass from its
  `schemas.py` (`fastapi-architecture.md` §3) — never a raw `dict` or the
  bare `data` payload type.
- Because `success_response`/`error_response` build the `JSONResponse`
  themselves rather than returning a model FastAPI serializes,
  `response_model` here is documentation only — it does not change what's
  sent on the wire. That's exactly why it's easy to forget and why this rule
  exists: nothing breaks at runtime if you skip it, but Swagger silently
  shows the route as returning an untyped body.
- Route functions should still be type-annotated `-> JSONResponse` to match
  what they actually return; `response_model` and the return annotation are
  not the same thing and both are required.

## 2. Registering a Router Is a Three-Step, Not a One-Step

Adding a feature's router to the app is **one combined change**, not just
`api_router.include_router(...)`:

1. `api.py` — `api_router.include_router(<feature>.router.router)`
   (`fastapi-architecture.md` §7).
2. `main.py` — add that feature's tag to the `_TAGS_METADATA` list passed as
   `openapi_tags` to `FastAPI(...)`, with a short (non-empty) description.
   `openapi_tags` is supplied once at app construction, so a tag with no
   entry there shows up in Swagger with no description.
3. A new or updated feature is covered by
   `tests/test_api_documentation.py::test_every_feature_router_is_registered_in_api_router`
   automatically, since that test discovers routers by walking
   `src/vmss_api/*/router.py` rather than reading a maintained list — but a
   PR that adds a feature must still confirm that test passes, since it's
   the thing that turns "forgot step 1" into a failing test instead of a
   silent gap.

## 3. Docs Availability Is Environment-Gated

- `/docs`, `/redoc`, and `/openapi.json` are enabled in every environment
  except `production` (`main.py`'s `_docs_urls`, keyed off
  `settings.environment.lower()`). Do not add a code path that re-enables
  them in production "temporarily for debugging" — use staging, which mirrors
  what's deployed, instead.
- `main.py` exposes `create_app(environment: str | None = None)` specifically
  so this gating is unit-testable without mutating the process-wide
  `settings` singleton. Prefer calling `create_app("production")` in a test
  over monkeypatching `settings.environment`.

## 4. Authenticating From Swagger UI

- Protected routes (anything depending on `get_current_user` or
  `require_permission`) are secured in the OpenAPI schema with the
  `HTTPBearer` scheme (`core/security.py`), not `OAuth2PasswordBearer`. This
  is deliberate: `/auth/login` takes a JSON body, not the OAuth2
  password-flow's form fields, so an OAuth2 scheme's built-in Swagger login
  widget can't actually authenticate against it.
- To try a protected endpoint from Swagger UI: call `POST /auth/login` via
  "Try it out" with valid credentials, copy `data.accessToken` from the
  response, click "Authorize," and paste it in (no `Bearer ` prefix needed —
  Swagger adds it). Do not build a second, Swagger-only login endpoint to make
  an OAuth2 widget's default flow work instead of this.

## 5. camelCase in the Docs Is Automatic, Not Manual

- `CamelModel`'s `alias_generator` (`fastapi-architecture.md` §3) makes
  FastAPI render every schema's fields in camelCase by default, but only for
  schemas FastAPI actually knows about — i.e., only once a route has a
  `response_model` per §1. There is no per-route `by_alias` flag to remember;
  if a schema is showing snake_case in `/docs`, the fix is almost always "this
  model doesn't extend `CamelModel`," not "add a serialization override."
- `tests/test_api_documentation.py::test_response_schemas_render_camel_case`
  is a regression test for this, not exhaustive coverage of every schema —
  extend it (or add an equivalent assertion in the feature's own tests) when
  a new response schema is added.
