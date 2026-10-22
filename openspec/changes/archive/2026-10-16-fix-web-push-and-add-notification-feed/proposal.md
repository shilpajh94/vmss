## Why

Staff see no notifications on the web portal. The API side works: it
resolves recipients and enqueues pushes, and Celery runs `send_push`. But
**no browser has ever registered a device**. `tenant_default.device_tokens`
has 0 rows, and the only `POST /notifications/devices` calls in the API log
come from the QA harness's fake `qa-fcm-*` tokens. So every push resolves to
zero devices and `send_push` returns "success" without sending anything,
and without a log line.

The portal side fails silently:

- **No explicit way to turn push on.** The portal calls
  `Notification.requestPermission()` automatically after login and again
  on tab focus or a 30-minute timer. Those calls aren't tied to a click, so
  browsers quiet or auto-block the prompt (Chrome's quieter permission UI,
  Firefox's user-gesture rule). Once permission is `denied` or left at
  `default`, registration returns early forever.
- **Every failure is invisible.** An insecure context (the portal opened on
  `http://<LAN-IP>:5173` instead of `localhost` or HTTPS), an unsupported
  browser, a denied permission and a `getToken` error all go only to
  `console.error`. To the user, each looks exactly like "no notifications".
- **Nothing is stored.** The bell's notification center is in memory. It
  shows only pushes that arrived live in this tab, so a reload, a closed
  tab or push being off means nothing to see. There's no server-side list.
- **The background-push click goes to the wrong page.** The service
  worker's notification click still opens `/staff/dashboard`, which since
  `staff-lifecycle-emails-and-dashboard-landing` is the KPI dashboard, not
  the invitations board the foreground toast links to.

## What Changes

- **Persisted in-app notification feed (API).** Every staff push dispatch
  also writes one `notifications` row per resolved recipient, whether or
  not they have a registered device. The row holds the same title, body
  and data as the push, plus `readAt`. The write is idempotent per dispatch
  and recipient, so a Celery redelivery doesn't duplicate rows.
- **New feed endpoints**, which any authenticated tenant user can call for
  their own notifications only:
  - `GET /api/v1/notifications`, paginated per `api-conventions.md` §1,
    with an `unreadOnly` filter;
  - `GET /api/v1/notifications/unread-count`;
  - `PATCH /api/v1/notifications/{id}/read`;
  - `POST /api/v1/notifications/read-all`.
- **Observable zero-device sends (API).** A push whose recipients have no
  registered device logs `INFO push_no_registered_devices` with the
  recipient count. "Sent to nobody" is then visible in the logs instead of
  looking like success.
- **Retention.** Notifications older than 90 days are purged by the
  existing visit-lifecycle sweep tick. Notifications are disposable, so
  they're hard-deleted.
- **Web: the bell is backed by the server.** The bell loads the feed and
  unread count from the API. It refreshes on a foreground push, on tab
  focus and on a 60-second poll. Clicking an item marks it read and opens
  its invitation. "Mark all read" calls the API. Notifications show up even
  when browser push is off.
- **Web: explicit push enablement.** The bell panel shows a push status row:
  - *Enabled*;
  - *Off*, with an **Enable notifications** button that requests
    permission from inside the click;
  - *Blocked*, with how to unblock it in browser settings;
  - *Unavailable*, explaining that it needs HTTPS or `localhost`, or a
    supported browser.

  The automatic permission prompt on login, focus and timer is removed.
  Those triggers now only re-register when permission is already
  `granted`. A registration failure shows a toast, not just a console
  error.
- **Web: the service-worker click opens the right page.** A staff
  background-push click opens `/staff/invitations?invitationId=…`, matching
  the foreground toast.

Nothing here is **BREAKING**. All API changes are new endpoints and a new
table. The push payload is unchanged.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `notifications`:
  - dispatch also persists an in-app notification per recipient;
  - zero-device sends are logged;
  - new requirements for the feed endpoints, read state, retention, and the
    portal's push-enablement and feed behavior.

## Impact

- **API code**:
  - `notifications/{models,repository,schemas,service,router,tasks}.py`;
  - a new tenant migration for the `notifications` table;
  - a retention call from `invitations/tasks.py::sweep_tenant_visit_lifecycle`.
- **DB**: one new tenant-schema table, `notifications`. Run
  `alembic_tenant` on every tenant (locally, only `tenant_default`).
- **RBAC**: none. Every endpoint is scoped to the caller's own user id.
- **Web code (VMMS_WEB)**:
  - `notification-center-context.tsx` becomes server-backed;
  - `NotificationBell.tsx` gets the feed list and the push status row;
  - `use-push-notifications.ts` splits a click-only `enablePush` from
    `refreshRegistrationIfGranted`;
  - `PushNotificationsProvider.tsx` and both login hooks;
  - `public/firebase-messaging-sw.js`;
  - a new notification-feed repository, use cases and API endpoints, wired
    in `composition-root.ts`.
- **Docs**: `docs/features/notifications.md`.
- **Dependencies**: none.
