## Context

See `proposal.md` - Why for the incident and confirmed root-cause analysis.
Reproducing the failure mode directly (a test-only route that always raises,
run through the real `create_app()` wiring) confirmed the mechanism:
Starlette's app construction gives whichever handler is registered for the
base `Exception` type exclusively to the outermost `ServerErrorMiddleware`.
That middleware, when `debug=True`, returns its own raw traceback response
and never calls the app's registered handler at all — regardless of what
else is in the middleware stack. `src/vmss_api/core/config.py::Settings.debug`
is sourced straight from `APP_DEBUG` (default `true`) with no relationship
to `environment`, and `main.py::create_app` passed it straight to
`FastAPI(debug=...)`, so a deployment that forgot to set `APP_DEBUG=false`
ran with `debug=True` in production and got the raw traceback on every
unhandled exception.

`src/vmss_api/core/middleware.py::RequestIdMiddleware` also subclassed
Starlette's `BaseHTTPMiddleware`, which Starlette's own documentation notes
can, in some circumstances, let an exception raised downstream escape the
registered exception-handler machinery. That's a real, documented general
risk, but it is **not** what caused this incident — the debug-mode
short-circuit above is sufficient on its own to explain the observed
traceback, and reproducing the incident against a version of this app with
`RequestIdMiddleware` already rewritten as pure ASGI still shows the same
traceback whenever `debug=True`. The middleware rewrite is still included as
defense-in-depth against that separate, documented risk.

## Goals / Non-Goals

**Goals:**
- Make it structurally impossible for a production/staging deployment to
  run with framework debug mode on, regardless of `APP_DEBUG`.
- Make the app's own exception handlers the single place that decides what
  an unhandled exception's response looks like, for every request path
  including middleware that runs ahead of routing.

**Non-Goals:**
- Changing `core/encryption.py`'s fail-loud-when-unused behavior for
  `SSO_ENCRYPTION_KEY` — that design is intentional and unrelated to the
  leak itself.
- Adding new environment variables or changing `.env.example` — no new
  setting is introduced, only how the existing `APP_DEBUG`/`APP_ENV`
  combination is interpreted.
- Auditing every other middleware in the stack for the same
  `BaseHTTPMiddleware` caveat beyond `RequestIdMiddleware` — `CORSMiddleware`
  is a Starlette-maintained pure ASGI middleware already and isn't affected.

## Decisions

**1. Compute an effective debug flag from `environment` + `APP_DEBUG`,
rather than trusting `APP_DEBUG` alone.**

Add a `Settings.effective_debug` property (or equivalent computed field):
`self.debug and self.environment.lower() in {"local", "testing"}`. `main.py`
passes `settings.effective_debug` to `FastAPI(debug=...)` instead of
`settings.debug`. `settings.debug` itself is left as the raw `APP_DEBUG`
value (still used by `configure_logging` for log verbosity, which is a
separate, lower-stakes concern than leaking a traceback over HTTP) so
existing callers of `settings.debug` for non-HTTP-response purposes are
unaffected.

Alternative considered: validate at startup and raise if
`environment == "production" and debug is True`, forcing a hard failure
instead of silently downgrading. Rejected because a hard crash on this
specific misconfiguration is a worse operational outcome than safely
running with debug off — the whole point is that ops already forgot one
setting; failing startup entirely over it is disproportionate when
"silently do the safe thing" fully closes the leak.

**2. Rewrite `RequestIdMiddleware` as a plain ASGI middleware (defense-in-depth,
not the fix for this incident — see Context above).**

Replace the `BaseHTTPMiddleware` subclass with a middleware implementing
`async def __call__(self, scope, receive, send)` directly: bind the request
id into `structlog`'s contextvars, wrap the `send` callable to inject the
`X-Request-ID` response header when the ASGI `http.response.start` message
passes through, and call `await self.app(scope, receive, wrapped_send)` —
no `call_next`/response-body-buffering step in between. This removes the
`BaseHTTPMiddleware` layer that Starlette's docs identify as able to let an
exception bypass the registered exception handlers, so any exception raised
below this middleware in the stack (routing, dependencies, the route
handler itself) reaches `ExceptionMiddleware`'s registered handlers exactly
as it would with no middleware present at all.

Alternative considered: keep `BaseHTTPMiddleware` and instead wrap the body
of `dispatch()` in a `try/except Exception` that calls
`unhandled_exception_handler` directly. Rejected: that duplicates the
global handler's logic in two places (a maintenance hazard — the two could
drift), and doesn't fix the same risk for any middleware added later; fixing
it at the ASGI level removes the whole class of bug once, for every current
and future middleware in this position.

**3. Leave `CORSMiddleware`'s position and the `Exception`/`HTTPException`
handler registrations in `main.py` unchanged.** Only the debug-flag
computation and `RequestIdMiddleware`'s implementation change.

## Risks / Trade-offs

- [Risk] A future contributor adds a new `BaseHTTPMiddleware`-based
  middleware ahead of `ExceptionMiddleware` and reintroduces the same class
  of bug. → Mitigation: the regression test added by this change (an
  endpoint that always raises, asserted to return the standard envelope
  end-to-end through the full middleware stack) will fail if that happens,
  catching it in CI rather than in production.
- [Risk] `effective_debug` diverging from `settings.debug` could confuse a
  future reader who expects one `debug` flag to mean one thing everywhere.
  → Mitigation: a one-line comment on `effective_debug` states which one
  gates the HTTP-visible behavior and why they're allowed to differ.

## Migration Plan

No data migration. Deploy like any other code change. Operationally,
confirm (separately from this change, as a deployment checklist item) that
the affected server's environment sets `APP_ENV=production`, so
`effective_debug` resolves to `False` there regardless of `APP_DEBUG`'s
current value, and set `SSO_ENCRYPTION_KEY` so the originally reported SSO
endpoint stops failing at all. No rollback concern beyond a normal revert —
the change only tightens an existing safety property.
