## Context

See `proposal.md` for motivation. Relevant current state:

- Auth: staff sign in via `/admin/login` (`use-staff-login-page.ts`) or SSO (`use-staff-sso-login-page.ts`), both storing a bearer token in `sessionStorage.getItem/setItem('token')`, read by `ApiClient` for `hasToken: true` endpoints.
- Sign-out is duplicated in two places today: `use-staff-dashboard.ts`'s `signOut` and `AdminTopBar.tsx`'s inline `signOut`, both just doing `sessionStorage.removeItem('token')` + `navigate(...)`.
- Toasts already exist (`presentation/components/toast/toast-context.tsx`, `useToast()` → `.success/.error/.info(message)`), and `AdminTopBar` already has a static bell icon placeholder.
- Backend contract (from `vmss-new-api`'s OpenAPI, confirmed on the ddev build, `hasToken: true`, self-service — see proposal's Impact note on environment coverage):
  - `POST /notifications/devices` — body `{ fcmToken: string, platform: "web" | "android" | "ios" }` → `201` `{ success, message, data: { id: uuid, platform, lastSeenAt } }`.
  - `DELETE /notifications/devices/{fcm_token}` — path param, no body → `200` `{ success, message, data: null }`. No-op (not an error) if the token was never registered or belongs to someone else.
- Firebase project `vmss-b2c5b` web config is already provisioned (values supplied by the user); Cloud Messaging + a VAPID key must be confirmed enabled in that project's console before `getToken()` will work.

## Goals / Non-Goals

**Goals:**
- Wire device registration/unregistration into the existing login and sign-out paths with minimal duplication.
- Keep the Firebase SDK entirely inside `infrastructure/` and a presentation hook — never call it from a use case or domain code.
- Make notification permission handling fully non-blocking and silently degrade when unsupported/denied.

**Non-Goals:**
- The visitor portal (unauthenticated) does not participate — no visitor-facing push notifications.
- The backend's actual push-sending logic (Firebase Admin SDK, event → push mapping) is out of scope; this change only covers the frontend device lifecycle and message handling.
- Native mobile (Android/iOS) apps are out of scope — `platform` is always sent as `"web"` from this codebase, even though the backend's `DevicePlatform` enum also allows `android`/`ios`.
- Rich notification actions (inline approve/deny from the notification itself) are out of scope; clicking only navigates to the invitation detail.

## Decisions

**1. Firebase init lives in `src/infrastructure/firebase/firebase-app.ts`, not `data/`.**
It's a third-party SDK client analogous to `ApiClient`, so it follows the same rule that `data/` never imports `infrastructure/`. It exports `getFirebaseMessaging(): Messaging | undefined` (undefined when `Notification`/`messaging` isn't supported in the current browser, e.g. Safari or non-secure context) built from `import.meta.env.VITE_FIREBASE_*`.

**2. The device port/use cases follow the standard data-api-layer pattern exactly**, per `.claude/rules/data-api-layer.md`:
- `domain/entities/device-schema.ts`: `DeviceSchema` (`id`, `platform`, `lastSeenAt`), `DeviceRegisterRequestSchema` (`fcmToken`, `platform`), both envelope-wrapped response schemas, mirroring `invitation-detail-schema.ts`'s pattern.
- `data/repositories/notification-repository.ts`: port with `registerDevice(fcmToken: string): Promise<Device>` and `unregisterDevice(fcmToken: string): Promise<void>`.
- `infrastructure/notification-repository.ts`: `HttpNotificationRepository implements NotificationRepository`, using `API_ENDPOINTS.REGISTER_DEVICE` / `API_ENDPOINTS.UNREGISTER_DEVICE` (the delete uses `pathParams: { fcm_token: fcmToken }`).
- `data/use-cases/register-device.ts` / `unregister-device.ts`: thin classes delegating to the port, added to `AppDependencies` and wired in `composition-root.ts` the same way every other feature is.

**3. A single presentation hook, `use-push-notifications.ts`, owns the whole client-side lifecycle**, instead of scattering Firebase calls across login/logout call sites:
- Exposes `registerCurrentDevice(): Promise<void>` and `unregisterCurrentDevice(): Promise<void>`, called explicitly from the login hooks and sign-out call sites (not an effect that runs implicitly on every mount — sign-in/sign-out are explicit user actions and the calls should be easy to trace).
- Internally: requests `Notification.requestPermission()`, calls `getToken(messaging, { vapidKey })`, calls `registerDeviceUseCase.execute(token)`, and remembers the last-registered token (module-level or `sessionStorage`, e.g. `sessionStorage.getItem('fcmToken')`) so `unregisterCurrentDevice()` and token-rotation re-registration both know which token to act on without re-deriving it.
- Sets up `onMessage(messaging, handler)` once (e.g. mounted from `AppDependenciesProvider` or a small `PushNotificationsProvider` alongside `ToastProvider` in `App.tsx`) to show foreground pushes via `useToast().info(...)` and expose a click/navigate callback.
- Sets up `onTokenRefresh`-equivalent handling (the modular SDK re-delivers via `getToken()` on refresh; there's no separate refresh callback) is not applicable — instead, re-registration on rotation is handled by re-running `getToken()` opportunistically (e.g. on next app load) rather than a persistent listener, since the modular Firebase JS SDK doesn't expose a token-refresh event.

**4. Sign-out call sites call `unregisterCurrentDevice()` before clearing the token**, awaited but not blocking navigation on failure (fire-and-forget with a caught error) so a flaky unregister call never traps a staff member on a signed-in screen. This touches both `use-staff-dashboard.ts` and `AdminTopBar.tsx`; the existing duplication between them is preserved as-is (not refactored into a shared sign-out utility — out of scope for this change).

**5. Service worker at `public/firebase-messaging-sw.js`** uses the compat SDK (`importScripts`) per Firebase's documented pattern for background messages, with the `firebaseConfig` object duplicated there (service workers can't read `import.meta.env`) — the same public web config values, not the VAPID key. `onBackgroundMessage` shows the OS notification with `data: { invitationId }` so the `notificationclick` handler can build the deep-link URL.

**6. Click-to-navigate — there is no standalone per-invitation route today** (`GetInvitationDetailUseCase` backs an in-board modal/card expansion keyed by id, opened from `use-invitations-board.ts`, not a URL). Rather than invent new routing architecture, both push paths land on the existing board route with the target invitation id as a query param, and the board opens that invitation's detail on load if present:
- The push payload's `data` carries `invitationId` and a `recipientRole` (`admin` | `staff`) the backend already knows from the device's owner, used to pick the board route.
- Foreground: `use-push-notifications.ts`'s `onMessage` handler shows the toast with an attached navigation target rather than navigating immediately (auto-navigating a staff member away from what they're doing the instant a push arrives would be surprising/disruptive). This requires extending `ToastItem`/`useToast()` with an optional click target (e.g. `toast.info(message, { onClick: () => navigate(...) })`) so the toast becomes an actionable element when one is provided, while existing non-push toasts (which pass no `onClick`) render exactly as they do today.
- Background (service worker): `self.addEventListener('notificationclick', ...)` calls `clients.openWindow('/admin/invitations?invitationId=...')` (or the staff route) built from the notification's `data`.
- `use-invitations-board.ts` reads `invitationId` from the URL (via `useSearchParams`) on mount and, if present, calls the existing `getInvitationDetailUseCase` flow to open that invitation's detail the same way clicking its card does today.

## Risks / Trade-offs

- [Backend notifications module not deployed everywhere] → confirmed present on `vmss-new-api.ddev.site:8443` but absent from `vmss-dev.mypits.org`'s current OpenAPI spec at proposal time. Mitigation: registration/unregistration failures are swallowed (non-blocking, per Decision 4), so the feature degrades to "no push notifications" rather than breaking login/logout on environments where the backend hasn't shipped it yet.
- [Firebase web `apiKey` and other config values are not secret by design (restricted via Firebase console, not confidentiality)] → still sourced from env vars rather than hardcoded, for environment flexibility (dev/staging/prod Firebase projects) and to match this repo's existing `VITE_*` convention.
- [Browsers without Notification/Push API support, or non-HTTPS contexts] → `getFirebaseMessaging()` returns `undefined` in that case; every call site checks for that and no-ops rather than throwing.
- [Toast component has no existing click-to-navigate affordance] → flagged as an Open Question below rather than silently deciding UI behavior that doesn't exist yet.

## Open Questions

- The push payload is assumed to carry `invitationId` and enough context (`recipientRole`) to pick the admin vs. staff board route. The exact payload shape is the backend/Firebase-Admin-SDK team's decision (out of scope here) — confirm it against this assumption before implementing the `onMessage`/service-worker handlers, and adjust the payload field names in `tasks.md` if they differ.
