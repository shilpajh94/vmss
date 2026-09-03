## Why

When a staff/admin's auth token expires or is rejected by the backend mid-session, the app currently shows a confusing, generic error (e.g. "Something went wrong loading the security gates. Please try again.") instead of signing the user out with a clear message — confirmed live by the user on `/admin/security-gates`. Root cause: `ApiClient.makeRequest` never checks the HTTP response status before parsing it, so a 401/403 response body gets fed straight into Zod parsing and fails as an unrelated-looking validation/network error. There is also no reactive redirect: the existing "check token, else redirect to login" guards only run once on page mount, so a token that goes bad while a page is already open is never caught until an API call fails in this confusing way.

## What Changes

- `ApiClient` detects a 401 or 403 response on any request and, instead of parsing the body as a normal success payload, clears the stored session token and signals that the session has expired.
- A single top-level listener (mounted once at the app root, alongside the existing `PushNotificationsProvider`) reacts to that signal by showing a clear "Your session has expired. Please sign in again." message and redirecting to the correct login route (`/admin/login` or `/staff/login`, matching the existing admin-vs-staff detection used elsewhere in the app), so this now works the same way from any page without editing each page's individual data-loading hook.
- **Out of scope**: using the backend's refresh token to silently renew the session before it expires (a bigger feature, deferred per the user's choice) — this change only fixes what happens *after* expiry, not how often it happens.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `app-shell`: a new requirement describes how the HTTP client and the app shell together handle an authenticated request rejected for an invalid/expired token — clearing the session and redirecting with a clear message, instead of the existing behavior of surfacing whatever error the failed response's body parsing produces.

## Impact

- `src/data/api/api-client.ts` — `makeRequest` (and the multipart/upload variants, if they share the same response-handling path) checks `response.status` for 401/403 before calling `parserSchema.parse(...)`; on match, clears `sessionStorage.getItem('token')` and throws/signals a distinct error rather than letting Zod or JSON parsing fail with an unrelated message.
- A new small top-level component (e.g. `SessionExpiryListener`, alongside `PushNotificationsProvider` in `src/App.tsx`'s `RootLayout`) listens for the signal, shows the toast, and navigates to the correct login route.
- No change to `src/domain/entities/staff-login-schema.ts` or `sso-exchange-schema.ts` — the already-unused `refreshToken` field stays unused (token refresh is out of scope here).
- Existing per-page `catch { setErrorMessage(...); toast.error(...) }` blocks are unchanged and will still fire their own generic message in addition to the new session-expiry toast+redirect for the specific request that failed — see design.md for why this overlap is an accepted trade-off rather than something this change also cleans up.
