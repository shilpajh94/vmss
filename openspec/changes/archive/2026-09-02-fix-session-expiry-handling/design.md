## Context

`ApiClient` (`src/data/api/api-client.ts`) has three request methods (`makeRequest`, `uploadFile`, `makeMultipartRequest`), each attaching `Authorization: Bearer <token>` from `sessionStorage.getItem('token')` when `hasToken: true`, then calling `fetch` and immediately parsing the response body — none of them check `response.status`/`response.ok` first. Per `.claude/rules/data-api-layer.md` and `clean-architecture.md`, `src/data/` must never import from `src/presentation/` — so `ApiClient` cannot call `useNavigate()` or any router API directly, and cannot import a toast context. Every authenticated page already has its own `useEffect` that checks `sessionStorage.getItem('token')` once on mount and redirects if absent (e.g. `src/presentation/pages/admin-buildings/hooks/use-admin-building-form.ts:87-94`), but nothing re-checks after mount.

Confirmed live by the user: on `/admin/security-gates`, an expired-token request surfaces as "Something went wrong loading the security gates. Please try again." — the page's own generic catch-block message, with no indication the session died and no path back to login except manually clicking "Sign out".

## Goals / Non-Goals

**Goals:**
- Detect a 401/403 on any authenticated request, from any page, in one place.
- Clear the dead token and get the user back to the correct login screen with a message that actually explains what happened.

**Non-Goals:**
- Token refresh via the backend's already-issued (and currently discarded) `refreshToken` — bigger scope, deferred per explicit user choice; this change only fixes the *experience* of expiry, not its frequency.
- Rewriting every page's individual `catch { ... }` block to specially detect and suppress its own generic message when the real cause was a session expiry — see Risks below for why this is accepted as-is rather than expanded into scope.
- Distinguishing 401 (unauthenticated) from 403 (forbidden/insufficient permission) with different messages — both are treated the same way here (session-expired-style redirect), since the app has no per-permission UI today that would benefit from telling them apart.

## Decisions

**Detect and clear in `ApiClient`; signal via a plain browser event, not a callback or context import.** `data/` cannot import `presentation/` (router, toast), so `ApiClient` can't directly navigate or show a toast. The minimal, dependency-rule-compliant option is a plain `window.dispatchEvent(new CustomEvent('auth:session-expired'))` — a browser primitive, not a presentation-layer import — right after clearing `sessionStorage`'s token and before throwing. A single new top-level component in `presentation/` (`SessionExpiryListener`, mounted in `App.tsx`'s `RootLayout` next to the existing `PushNotificationsProvider`) adds one `window.addEventListener('auth:session-expired', ...)` for the app's lifetime, and reacts with `toast.error(...)` + `navigate(...)`. This mirrors how the app already decouples layers elsewhere (e.g. `PushNotificationsProvider` also lives at the same root level, independent of routing).

*Alternative considered*: have each page's own hook catch a distinguished error type and redirect itself. Rejected — this is the pattern already in place (mount-only per-page checks) and is exactly what produces inconsistent, easy-to-forget handling; a single shared listener guarantees every page gets the same behavior without editing 20+ hook files.

**Throw a distinguished error after signaling, so the failing call's own `await` still rejects.** `ApiClient` still throws (e.g. `throw new Error('Session expired')`) after dispatching the event and clearing the token, so the specific `try/catch` in whichever hook made the call still runs its existing `finally { setIsLoading(false) }` / `setIsSaving(false)` and doesn't hang. Its `catch` block will still also set its own generic error message and fire its own toast — see Risks below.

**Detect admin-vs-staff the same way `PushNotificationsProvider`/`buildInvitationPath` already do**: `window.location.pathname.startsWith('/admin')` decides between `/admin/login` and `/staff/login`, for consistency with the one other place in the codebase that already makes this exact decision, rather than inventing a second heuristic.

**Check `response.status` in all three `ApiClient` methods via one shared private helper**, called immediately after `fetch` and before any body parsing, to avoid tripling the same 401/403 check inline in `makeRequest`, `uploadFile`, and `makeMultipartRequest`.

## Risks / Trade-offs

- [Risk] The page whose request triggered the 401/403 will show two things in quick succession: its own existing generic "Something went wrong..." toast/error message (from its unchanged `catch` block) and the new "Your session has expired..." toast+redirect → Mitigation: accepted trade-off — the user ends up correctly on the login page either way, and the accurate message is the last thing shown before the redirect happens; rewriting 20+ pages' catch blocks to suppress their own message specifically for this one error type is a much larger change for a minor duplicate-toast cosmetic issue, and is explicitly out of scope here.
- [Risk] A 403 can also mean "logged in fine, but not permitted to do this specific thing" rather than "session expired" — treating every 403 as a session expiry could log out a user who simply lacks permission for one action → Mitigation: today's app has no per-permission-denied UI to fall back to anyway (grep found no existing 403-specific handling at all), so this is strictly better than the current behavior (a confusing generic error) even if not perfectly precise; revisit if/when the backend starts returning meaningfully different 403s for real permission checks versus dead tokens.
- [Risk] `window.dispatchEvent`/`addEventListener` is a slightly unusual cross-layer signaling mechanism for this codebase (no prior use of custom events) → Mitigation: it's the standard way to cross the `data/` → `presentation/` dependency boundary without an import, and is scoped to exactly one event name used in exactly one place on each side.
