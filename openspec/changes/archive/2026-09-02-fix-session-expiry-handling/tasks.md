## 1. Detect and handle 401/403 in ApiClient

- [x] 1.1 In `src/data/api/api-client.ts`, add a private helper (e.g. `handleAuthFailure(response: Response): void`) that, when `response.status === 401 || response.status === 403`, clears `sessionStorage.removeItem('token')` and dispatches `window.dispatchEvent(new CustomEvent('auth:session-expired'))`.
- [x] 1.2 Call this helper immediately after `fetch` resolves and before any body parsing in `makeRequest`, `uploadFile`, and `makeMultipartRequest`; when it detects a 401/403, throw a distinguished error (e.g. `new Error('Session expired')`) instead of continuing to `response.json()`/`parserSchema.parse(...)`.
- [x] 1.3 Leave the existing "missing token" pre-flight check (`throw new Error(...)` when no token exists before the request is even sent) unchanged — this task only adds handling for a token that was sent but rejected.

## 2. Add the top-level session-expiry listener

- [x] 2.1 Create `src/presentation/components/session/SessionExpiryListener.tsx` (or similar): on mount, add a `window.addEventListener('auth:session-expired', ...)` listener; on cleanup, remove it.
- [x] 2.2 On the event, call `toast.error('Your session has expired. Please sign in again.')` and `navigate(...)`, choosing `/admin/login` or `/staff/login` based on `window.location.pathname.startsWith('/admin')` (same heuristic already used in `PushNotificationsProvider`'s `buildInvitationPath`).
- [x] 2.3 In `src/App.tsx`'s `RootLayout`, mount `<SessionExpiryListener />` once at the root, alongside `<PushNotificationsProvider>`.

## 3. Verify

- [ ] 3.1 Manually simulate an expired/invalid token (e.g. edit `sessionStorage`'s `token` value to something invalid) while sitting on an authenticated admin page, trigger any API call (e.g. click "Try again" or navigate to trigger a fetch), and confirm: the token is cleared, a "Your session has expired. Please sign in again." toast appears, and the app redirects to `/admin/login`.
- [ ] 3.2 Repeat on a staff-area page (e.g. `/staff/dashboard`) and confirm the redirect goes to `/staff/login` instead.
- [ ] 3.3 Confirm a normal, valid-token request is completely unaffected (no behavior change for 200/204/other non-401/403 responses).
- [ ] 3.4 Confirm the specific page's own existing error handling still runs without crashing (e.g. `isLoading`/`isSaving` still resolves to `false`) even though the request ultimately failed via the new session-expired path.
