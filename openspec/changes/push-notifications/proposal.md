## Why

Staff currently only learn about invitation lifecycle events (new invitation awaiting their approval, an approval step assigned to them, a reschedule, a deny) by refreshing the dashboard. The backend already exposes a `notifications` module (`POST /notifications/devices`, `DELETE /notifications/devices/{fcm_token}`) backed by Firebase Cloud Messaging, so staff can be pushed a real-time browser notification instead. The frontend has no Firebase integration yet.

## What Changes

- Add the Firebase Web SDK (Cloud Messaging) to the staff/admin authenticated area, initialized from `VITE_FIREBASE_*` env vars.
- Add a `firebase-messaging-sw.js` service worker (in `public/`) so pushes are delivered as native OS notifications when the tab is backgrounded or closed.
- Register the current browser as a push-notification device with the backend (`POST /notifications/devices`) right after a staff member signs in (both `/admin/login` and SSO flows), and re-register whenever Firebase rotates the FCM token.
- Unregister the device (`DELETE /notifications/devices/{fcm_token}`) as part of sign-out, before the session token is cleared.
- Show an in-app toast (reusing the existing `notifications` toast capability) for pushes that arrive while the tab is open (foreground), and deep-link both foreground and background notification clicks to the relevant invitation detail.
- Follow this repo's data/API layer conventions: `API_ENDPOINTS` entries, a `Device` domain schema, a `NotificationRepository` port, an `HttpNotificationRepository` adapter, `RegisterDevice`/`UnregisterDevice` use cases, wired through `composition-root.ts`.

## Capabilities

### New Capabilities
- `push-notifications`: browser push notifications for invitation lifecycle events — device registration/unregistration tied to the staff session, and foreground/background message handling with click-to-navigate.

### Modified Capabilities
(none — the existing `notifications` toast capability's own requirements are unchanged; push notifications call its existing hook as an implementation detail, not a new requirement of that capability. `staff-login`'s requirements are unchanged; device registration is a side effect layered on top of the existing login flow, not a change to what login itself must do.)

## Impact

- **New files**: `src/domain/entities/device-schema.ts`, `src/data/repositories/notification-repository.ts`, `src/infrastructure/notification-repository.ts`, `src/data/use-cases/register-device.ts`, `src/data/use-cases/unregister-device.ts`, `src/infrastructure/firebase/firebase-app.ts`, `src/presentation/hooks/use-push-notifications.ts`, `public/firebase-messaging-sw.js`.
- **Modified files**: `src/data/api/api-endpoints.ts` (2 new entries), `src/composition-root.ts` (wire the new port/adapter/use cases), `src/presentation/pages/staff-login/hooks/use-staff-login-page.ts`, `src/presentation/pages/staff-sso-login/hooks/use-staff-sso-login-page.ts` (register device after login), `src/presentation/pages/staff-dashboard/hooks/use-staff-dashboard.ts`, `src/presentation/components/AdminTopBar.tsx` (unregister device on sign-out), `.env.example` (new `VITE_FIREBASE_*` keys).
- **Dependencies**: adds the `firebase` npm package.
- **Backend**: `POST /notifications/devices` and `DELETE /notifications/devices/{fcm_token}` exist on the `vmss-new-api` build reflected at `https://vmss-new-api.ddev.site:8443/docs`, but were not present in the `openapi.json` served by `https://vmss-dev.mypits.org` at proposal time — confirm the target deploy environment has the notifications module before this ships, otherwise device registration calls will 404.
- **Firebase project**: `vmss-b2c5b` (config supplied by the user) — its web app credentials will be stored as `VITE_FIREBASE_*` env vars, not hardcoded.
