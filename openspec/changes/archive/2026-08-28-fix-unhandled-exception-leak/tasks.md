## 1. Effective debug flag

- [x] 1.1 Add `Settings.effective_debug` (or equivalent computed property) to
      `src/vmss_api/core/config.py`: `True` only when `debug` (raw
      `APP_DEBUG`) is `True` and `environment.lower()` is `local` or
      `testing`.
- [x] 1.2 Update `src/vmss_api/main.py::create_app` to pass
      `settings.effective_debug` to `FastAPI(debug=...)` instead of
      `settings.debug`. Leave `settings.debug`'s other current use
      (`configure_logging`) unchanged.

## 2. Request-id middleware rewrite

- [x] 2.1 Rewrite `RequestIdMiddleware` in `src/vmss_api/core/middleware.py`
      as a plain ASGI middleware (`async def __call__(self, scope, receive,
      send)`), removing the `BaseHTTPMiddleware` base class.
- [x] 2.2 Preserve existing behavior: bind/clear the `request_id` structlog
      contextvar at the start of each HTTP request, generate a UUID when
      `X-Request-ID` isn't present on the inbound request, and inject
      `X-Request-ID` into the outbound response headers by wrapping the ASGI
      `send` callable (intercept `http.response.start`).
- [x] 2.3 Confirm non-HTTP ASGI scopes (`lifespan`, if any pass through this
      middleware) are passed through unchanged rather than erroring on
      header injection logic that assumes an HTTP response.

## 3. Tests

- [x] 3.1 Add a test-only route (or reuse an existing internal test hook)
      that unconditionally raises an unhandled exception, and — with debug
      mode disabled (`environment="production"`, the state every real
      deployment outside local/testing must be in) — assert the full app
      (all middleware, `create_app()`'s default config) returns the
      standard error envelope with status 500 and no stack trace/file path
      in the body. (Debug mode showing a raw traceback when genuinely
      enabled in local/testing is intentional and out of scope for this
      assertion — see design.md's Context.)
- [x] 3.2 Add a second case covering an exception raised inside
      request-scoped middleware (ahead of routing), not just inside a route
      handler, with debug mode disabled — asserting the same envelope-only
      behavior.
- [x] 3.3 Add a focused unit test for `Settings.effective_debug`/the
      debug-flag computation covering: `production`+`APP_DEBUG=true` →
      `False`; `staging`+`APP_DEBUG=true` → `False`; `local`+`APP_DEBUG=true`
      → `True`; `testing`+`APP_DEBUG=true` → `True`; any
      environment+`APP_DEBUG=false` → `False`.
- [x] 3.4 Run `ddev exec uv run pytest` and confirm the full suite is green.

## 4. Documentation

- [x] 4.1 Add a short note to `docs/features/configuration.md` (the existing
      doc for the `environment-configuration` capability) describing the
      `APP_ENV`/`APP_DEBUG` interaction: debug mode is only ever honored in
      `local`/`testing`, so `APP_DEBUG` alone does not control production
      behavior.
