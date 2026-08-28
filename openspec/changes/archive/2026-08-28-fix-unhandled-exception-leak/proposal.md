## Why

A `PUT /api/v1/auth/sso/config` request on the deployed server returned a raw
Python traceback in the response body instead of the standard error envelope
(500, file paths, package versions, and source line numbers all visible to
the calling client). The triggering exception (`SSO_ENCRYPTION_KEY` not set)
is itself a server configuration gap the operators need to fix separately —
but the fact that *any* unhandled exception can reach the client as a raw
framework traceback is a code defect independent of that one missing
setting, and directly violates `security-architecture.md` §4's "no stack
traces, no file paths ... in the client-facing response" requirement. Root
cause has two parts:

Root cause, confirmed by reproducing the failure mode directly against this
codebase's own middleware stack: Starlette's app construction extracts
whichever handler is registered for the base `Exception` type (or status
500) and gives it *exclusively* to the outermost `ServerErrorMiddleware` —
not to the per-route/`ExceptionMiddleware` layer other handlers use. That
middleware's behavior is: **if `debug` is `True`, it returns its own raw
traceback page and never calls the app's registered handler at all** — it
doesn't matter that `core/middleware.py::unhandled_exception_handler` is
correctly registered; debug mode bypasses it outright. `settings.debug`
(`APP_DEBUG`) defaults to `true` and nothing forces it off outside
local/testing, so a deployment that forgets to set `APP_DEBUG=false` runs
with `debug=True` in production, and every unhandled exception gets the raw
traceback page instead of the standard envelope — exactly what the reported
incident shows.

(When `debug` is `False`, `ServerErrorMiddleware` does call the registered
handler and does send its response to the client correctly — it separately,
and intentionally per Starlette's own comment, re-raises the original
exception afterward purely so a real ASGI server can log it; the response
was already transmitted by that point, so a real client is unaffected. Test
clients built on `httpx.ASGITransport`/Starlette's `TestClient` surface that
re-raise unless told not to, which is a test-harness detail, not a
client-visible behavior.)

## What Changes

- Derive the FastAPI `debug` flag from `environment` as well as `APP_DEBUG`:
  debug mode can only be enabled when `environment` is `local` or `testing`,
  never `staging`/`production`, regardless of what `APP_DEBUG` is set to.
  This is the fix that actually closes the reported leak — it removes the
  only path (`ServerErrorMiddleware`'s debug-mode traceback response) by
  which the app's own exception handler gets bypassed.
- Rewrite `RequestIdMiddleware` as a plain ASGI middleware (no
  `BaseHTTPMiddleware`) as defense-in-depth: Starlette's own docs flag
  `BaseHTTPMiddleware` as able to let an exception bypass the app's
  registered handlers in some circumstances (unrelated to the debug-mode
  bypass above, which is the confirmed cause of this incident). This isn't
  required to fix the reported incident but removes a documented general
  risk from a middleware that runs on every request.
- Add regression tests proving: (a) with debug mode disabled, an endpoint
  that raises an unexpected exception — and, separately, middleware that
  raises ahead of routing — returns the standard error envelope, never a
  stack trace; (b) `debug` is forced off when `environment` is
  `staging`/`production` even if `APP_DEBUG=true` is set. (Debug mode
  showing a raw traceback when genuinely enabled in `local`/`testing` is
  intentional developer behavior, not something these tests treat as a
  leak.)

Out of scope: this change does not alter `SSO_ENCRYPTION_KEY`'s
fail-loud-when-unused design (`core/encryption.py`) — that behavior is
intentional (see `add-sso-oidc-login/design.md`). The immediate fix for the
reported SSO error is an operational one: set `SSO_ENCRYPTION_KEY` (and
confirm `APP_DEBUG=false`, `APP_ENV=production`) in the server's
environment — tracked separately from this code change.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `environment-configuration`: adds requirements that (1) debug mode cannot
  be enabled outside `local`/`testing` regardless of `APP_DEBUG`, and (2)
  an unhandled exception anywhere in the request path always resolves to the
  standard error envelope, never a raw framework traceback or default
  response.

## Impact

- `src/vmss_api/core/config.py` — derive an effective debug flag from
  `environment` + `APP_DEBUG` instead of trusting `APP_DEBUG` alone.
- `src/vmss_api/main.py` — use the effective debug flag when constructing
  `FastAPI(debug=...)`.
- `src/vmss_api/core/middleware.py` — rewrite `RequestIdMiddleware` as a
  pure ASGI middleware.
- Test coverage: `src/vmss_api/core/tests.py` (or equivalent) gains
  unhandled-exception-envelope and debug-flag-safety cases.
- No database schema, API contract, or client-visible field changes for any
  existing endpoint — only the shape of an already-abnormal (500) response
  and an internal `debug` computation change.
