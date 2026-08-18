## Context

See `proposal.md` - Why. Relevant current state:

- `main.py` constructs `FastAPI(title=settings.app_name, debug=settings.debug)`
  with no other OpenAPI configuration — `docs_url`/`redoc_url`/`openapi_url`
  are all at their FastAPI defaults, active in every environment.
- `core/security.py` defines `_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")`,
  used only to extract the bearer token from the `Authorization` header inside
  `get_current_user`. `/auth/login` (`auth/router.py`) takes a JSON body
  (`LoginRequest`: `email`, `password`), not the OAuth2 password-flow's
  form-encoded `username`/`password` — so Swagger's built-in OAuth2 login
  popup, which POSTs the latter shape to `tokenUrl`, cannot actually log in
  against this endpoint.
- `core/schemas.py`'s `CamelModel` sets `alias_generator=to_camel` and
  `populate_by_name=True`. Every feature schema extends it
  (`fastapi-architecture.md` §3).
- `core/config.py`'s `Settings.environment` is a plain `str`, default
  `"local"`, no enum/`Literal` constraint today.
- Only two feature routers exist (`auth`, `organizations`), both registered
  in `api.py` by hand.

## Goals / Non-Goals

**Goals:**
- Make the generated OpenAPI schema/Swagger UI environment-aware, correctly
  labeled, and usable end-to-end for testing an authenticated request.
- Make "a router exists but was never registered" a failing test, not a
  silent gap.
- Capture the resulting conventions in a rule file so they hold as more
  feature routers are added.

**Non-Goals:**
- Introducing a `Literal`/enum type for `Settings.environment` — out of
  scope; this change only needs a single string comparison at one call site.
- Building an OAuth2-compatible shim login endpoint purely to satisfy
  Swagger's built-in password-flow widget — see Decisions below.
- SDK/client generation from the OpenAPI schema — not currently done in this
  repo; flagged as an open question below in case it matters later.

## Decisions

**Gate docs by a direct `environment` string check, not a new setting.**
At `FastAPI(...)` construction in `main.py`, set
`docs_url=None, redoc_url=None, openapi_url=None` when
`settings.environment.lower() == "production"`, else leave them at their
defaults. Alternative considered: add a dedicated `enable_api_docs: bool`
setting — rejected as an extra knob to keep in sync with `environment` for
no real benefit; the existing field already communicates the same thing.

**Replace `OAuth2PasswordBearer` with `HTTPBearer(auto_error=False)` in
`core/security.py`.** Both classes do the same thing at request time — read
`Authorization: Bearer <token>` and hand the raw token to `get_current_user`
— so this is a docs-and-testability change, not a behavior change for real
clients. `HTTPBearer` gives Swagger UI a plain "paste your token" Authorize
dialog, which matches how a token is actually obtained here (call
`POST /auth/login` with JSON, copy the `accessToken` from the response, paste
it into Authorize). Alternative considered: keep `OAuth2PasswordBearer` and
add a second, Swagger-only, form-encoded login endpoint so the built-in OAuth2
popup works — rejected: it adds a login code path with zero use by any real
client (React/Flutter both send JSON) purely to make one widget's default
flow light up, which is more surface area than the problem is worth.

**Do not add explicit `by_alias` handling anywhere — verify FastAPI's
default already renders `CamelModel` aliases in the schema.** FastAPI
generates component schemas (and request/response bodies) using each Pydantic
field's `alias` by default — this is the documented reason to combine
`alias_generator` with `populate_by_name=True` in the first place: Python
code stays snake_case, everything client-facing (including the docs) is
camelCase, with no per-route flag needed. Implementation should confirm this
with a one-time check against `/openapi.json` for an existing `organizations`
schema before treating item as done; only add an explicit override if that
check finds a route where it doesn't hold (e.g., a schema that bypasses
`CamelModel`).

**Router-registration test walks `src/vmss_api/*/router.py` by discovery,
not a hardcoded feature list.** The test enumerates immediate subpackages of
`src/vmss_api` (skipping `core`) that define a `router.py` with a
module-level `router`, and asserts every one of that router's routes (whose
`route.path` already includes the router's own `prefix` — FastAPI bakes that
in at `add_api_route` time, so the test must not prepend it a second time)
appears among the paths the assembled `app` actually serves. Discovery-based
rather than a maintained list of feature names, so the test itself can't go
stale the way a hand-written list could.

**Centralize `tags_metadata` in `main.py`, one entry per feature tag.**
`openapi_tags` must be supplied once at `FastAPI(...)` construction as a
single list, so it can't be scattered per-feature the way route
decorators are. The new rule file (see proposal) states that registering a
feature's router in `api.py` and adding its tag description in `main.py` are
one combined step, so they can't drift apart.

## Risks / Trade-offs

- [Docs fully disabled in production] → an on-call engineer debugging a
  production incident loses the ability to browse `/docs` against the live
  process. Mitigated by staging remaining fully documented and mirroring
  what's deployed; the same schema is always derivable locally from the
  deployed commit/tag.
- [Swapping `OAuth2PasswordBearer` for `HTTPBearer` changes the OpenAPI
  security scheme's declared type from `oauth2` to `http`/`bearer`] → any
  future SDK generator or API-client tool that assumes an OAuth2 scheme would
  need to adjust. No such tooling exists in this repo today, and the OAuth2
  scheme was never functional against the real login contract, so nothing
  currently depends on it behaving as OAuth2.
- [Discovery-based router-registration test] → if a future feature
  deliberately wants a router mounted outside `api_router` (e.g., an
  internal-only diagnostic router on a separate path), the test would flag it
  as unregistered. None of the current features need this; if it comes up,
  the test needs an explicit, visible exception list rather than silently
  passing.
- [String comparison for environment gating] → a typo'd or differently-cased
  environment value (e.g. `"Production"`) either wrongly disables or wrongly
  leaves docs enabled. Mitigated by normalizing with `.lower()` at the one
  call site; a full enum is deferred (see Non-Goals).

## Migration Plan

No live production deployment exists yet (`project-rules.md`: "Deployment:
not yet decided"), and the previous OAuth2 Swagger flow was never usable
against the real login endpoint, so this is additive/corrective, not a
breaking change to a running system. Implement, run the full test suite
(`ddev exec uv run pytest`), merge — no rollback procedure beyond a normal
revert, since no external consumer depends on the current unconfigured docs
setup as a stable contract.

## Open Questions

- If this project later adds OpenAPI-based SDK/client generation for the
  React portal or Flutter app, should the security scheme move back toward
  a proper OAuth2 flow (with a real form-encoded token endpoint) instead of
  the simpler pasted-bearer-token `HTTPBearer` approach? Not needed now — no
  such generation exists — but worth revisiting if it's ever introduced.
