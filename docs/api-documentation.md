# API Documentation (Swagger/OpenAPI)

Cross-cutting `core`/`main.py` behavior, not a feature package — see
`.claude/rules/api-documentation.md` for the conventions every feature router
must follow so it shows up here correctly.

## Where the docs live

| Environment | `/docs` (Swagger UI) | `/redoc` | `/openapi.json` |
|---|---|---|---|
| `local`, `dev`, `staging` (default) | 200 | 200 | 200 |
| `production` | 404 | 404 | 404 |

Gating is keyed off `settings.environment` (`main.py`'s `_docs_urls`). There's
no separate on/off setting — set `ENVIRONMENT` and the docs follow.

## Authenticating from Swagger UI

Protected endpoints (anything requiring login) use the `HTTPBearer` scheme, so
Swagger's "Authorize" dialog just wants a raw token, not a login form:

1. Open `/docs`, find `POST /auth/login` under the **auth** tag, "Try it out"
   with valid credentials.
2. Copy `data.accessToken` from the response.
3. Click **Authorize** (top right) and paste the token in — no `Bearer `
   prefix needed.
4. "Try it out" now works on any endpoint under a padlock.

## Adding a new endpoint

Every route needs, at minimum:

- `response_model=Envelope[<YourSchema>]` on the decorator, where `Envelope`
  (`core/schemas.py`) documents the `{success, message, data}` shape
  `success_response` actually returns.
- Its feature tag added to `_TAGS_METADATA` in `main.py` (only needed once per
  feature, not once per route).

`tests/test_api_documentation.py` fails if a router is registered in `api.py`
but its routes don't show up in the generated schema — that's the backstop
for "I forgot a step above," not a substitute for following them.
