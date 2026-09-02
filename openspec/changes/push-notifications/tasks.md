## 1. Firebase project & env setup

- [x] 1.1 Add `firebase` to `package.json` dependencies.
- [x] 1.2 Add `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_STORAGE_BUCKET`, `VITE_FIREBASE_MESSAGING_SENDER_ID`, `VITE_FIREBASE_APP_ID`, `VITE_FIREBASE_MEASUREMENT_ID`, `VITE_FIREBASE_VAPID_KEY` to `.env.example` (values from the `vmss-b2c5b` Firebase project; VAPID key generated from Cloud Messaging settings in that project's console) and to the local `.env`.
- [ ] 1.3 Confirm Cloud Messaging is enabled and a Web Push certificate (VAPID key) exists for the `vmss-b2c5b` Firebase project. **Manual step — requires Firebase console access; `VITE_FIREBASE_VAPID_KEY` is still blank in `.env`.**

## 2. Data layer (per `.claude/rules/data-api-layer.md`)

- [x] 2.1 Add `REGISTER_DEVICE` (`POST /notifications/devices`, `hasToken: true`) and `UNREGISTER_DEVICE` (`DELETE /notifications/devices/:fcmToken`, `hasToken: true`) to `src/data/api/api-endpoints.ts`. (Path param named `fcmToken`, not `fcm_token` — `ApiClient.buildPath`'s regex only matches `[a-zA-Z]+`, so an underscore would have left the segment unreplaced.)
- [x] 2.2 Add `src/domain/entities/device-schema.ts`: `DevicePlatformSchema` (`z.enum(['web', 'android', 'ios'])`), `DeviceSchema` (`id`, `platform`, `lastSeenAt`), `DeviceRegisterRequestSchema` (`fcmToken`, `platform`), and their envelope-wrapped response schemas, following `invitation-detail-schema.ts`'s pattern.
- [x] 2.3 Add `src/data/repositories/notification-repository.ts` port: `registerDevice(fcmToken: string): Promise<Device>`, `unregisterDevice(fcmToken: string): Promise<void>`.
- [x] 2.4 Add `src/infrastructure/notification-repository.ts`: `HttpNotificationRepository implements NotificationRepository`, using `makeRequest` with `API_ENDPOINTS.REGISTER_DEVICE` / `API_ENDPOINTS.UNREGISTER_DEVICE`, sending `platform: "web"` always.
- [x] 2.5 Add `src/data/use-cases/register-device.ts` and `src/data/use-cases/unregister-device.ts`.
- [x] 2.6 Wire `NotificationRepository` → `HttpNotificationRepository` → `RegisterDeviceUseCase`/`UnregisterDeviceUseCase` into `src/composition-root.ts`'s lazy resolvers and `AppDependencies`.

## 3. Firebase client integration

- [x] 3.1 Add `src/infrastructure/firebase/firebase-app.ts`: builds `firebaseConfig` from `import.meta.env.VITE_FIREBASE_*`, exports `getFirebaseMessaging(): Messaging | undefined` (returns `undefined` when unsupported — no `Notification` API, or not a secure context).
- [x] 3.2 Add `public/firebase-messaging-sw.js`: `importScripts` the Firebase compat SDK, `initializeApp` with the same public config values (hardcoded there, not read from env), `onBackgroundMessage` to show a native notification carrying `data.invitationId`, and a `notificationclick` listener that calls `clients.openWindow(...)` to the appropriate board route with `?invitationId=...`.
- [x] 3.3 Register the service worker (`navigator.serviceWorker.register('/firebase-messaging-sw.js')`) during app startup, guarded by `'serviceWorker' in navigator`. (Done in `PushNotificationsProvider`, not inline in `App.tsx` — see task 4.3.)

## 4. Device lifecycle hook

- [x] 4.1 Add `src/presentation/hooks/use-push-notifications.ts` exposing `registerCurrentDevice()` and `unregisterCurrentDevice()`, using `useAppDependencies()` for the register/unregister use cases and `getFirebaseMessaging()` + `getToken(messaging, { vapidKey })` (guarded by permission + support checks, all failures caught and swallowed per design Decision 1/4).
- [x] 4.2 Persist the last-registered FCM token (e.g. `sessionStorage.setItem('fcmToken', token)`) so `unregisterCurrentDevice()` and re-registration can reference it without re-deriving it.
- [x] 4.3 Added `src/presentation/components/push-notifications/PushNotificationsProvider.tsx`, mounted in `App.tsx` between `AppDependenciesProvider` and `Routes` — calls `onMessage(messaging, handler)` once for the app's lifetime (kept separate from `use-push-notifications.ts` so the listener doesn't re-subscribe every time a login/logout call site mounts); the handler shows a toast (`useToast().info(message, { onClick: () => navigate(...) })`) built from the push payload's `invitationId`/`recipientRole`.

## 5. Wire into sign-in / sign-out

- [x] 5.1 Call `registerCurrentDevice()` from `use-staff-login-page.ts` after a successful login (after `sessionStorage.setItem('token', token)`, before or alongside navigation) — awaited but errors caught so a registration failure never blocks navigation.
- [x] 5.2 Call `registerCurrentDevice()` from `use-staff-sso-login-page.ts`'s equivalent successful-auth point.
- [x] 5.3 Call `unregisterCurrentDevice()` from `use-staff-dashboard.ts`'s `signOut`, before `sessionStorage.removeItem('token')`.
- [x] 5.4 Call `unregisterCurrentDevice()` from `AdminTopBar.tsx`'s `signOut`, before `sessionStorage.removeItem('token')`.

## 6. Toast click-to-navigate

- [x] 6.1 Extend `ToastItem`/`useToast()` in `toast-context.tsx` with an optional `onClick` passed through `success/error/info(message, { onClick? })`, defaulting to no-op/non-interactive when omitted (existing call sites unaffected).
- [x] 6.2 Update `ToastViewport`/toast rendering to render an actionable element (e.g. `role="button"`/clickable) when `onClick` is present, dismissing the toast on click. (Implemented in `Toast.tsx` — the message becomes a `<button>` when `onClick` is present.)

## 7. Invitation deep-link on arrival

- [x] 7.1 Update `use-invitations-board.ts` to read `invitationId` from the URL (`useSearchParams`) on mount and, when present, open that invitation's detail the same way selecting its card does today.
- [x] 7.2 Wire the push toast's `onClick` (task 4.3/6.1) and the service worker's `notificationclick` (task 3.2) to navigate to `/admin/invitations?invitationId=...` or `/staff/dashboard?invitationId=...` based on the payload's `recipientRole`. (Already implemented as part of 3.2/4.3.)

## 8. Verification

- [ ] 8.1 Manually verify: sign in as staff with notification permission granted → device appears registered (check via backend/DB or a temporary log); sign out → device unregistered. **Not run — needs a real staff login against a backend that has the notifications module, plus a real `VITE_FIREBASE_VAPID_KEY`.**
- [x] 8.2 Manually verify: permission denied/unsupported browser → sign-in and sign-out both complete normally with no errors surfaced to the user. Verified via `npm run build` + a dev-server smoke test (index and `/firebase-messaging-sw.js` both serve 200); every Firebase call site (`getFirebaseMessaging`, `registerCurrentDevice`, `unregisterCurrentDevice`) is try/caught and no-ops on failure/unsupported by code inspection — no live login was exercised, since `VITE_FIREBASE_VAPID_KEY` is still blank.
- [ ] 8.3 Manually verify (using Firebase console's "Send test message" or a backend-triggered invitation event): foreground push shows an in-app toast; clicking it navigates to the invitation; background push shows an OS notification; clicking it opens/focuses the app at the invitation. **Not run — needs a real push sent from the `vmss-b2c5b` Firebase project.**
- [ ] 8.4 Confirm against the deployed target environment's `/docs` (or `openapi.json`) that `/notifications/devices` exists before enabling this in that environment — it was missing from `vmss-dev.mypits.org` at proposal time. **Not run — needs the actual target deploy environment, which wasn't specified.**
