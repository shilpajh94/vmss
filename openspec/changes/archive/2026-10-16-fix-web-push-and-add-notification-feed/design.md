## Context

See proposal.md for the diagnosis. The relevant current shapes:

- `notifications/service.py`:
  - `notify_user` and `notify_role_at_branch` resolve recipient user ids
    synchronously;
  - each then enqueues **one** `tasks.send_push.delay(...)` carrying
    `tenant_schema`, `user_ids`, `title`, `body` and `data`;
  - `notify_user` adds `assignedUserId` and `reason` to `data`, and
    `notify_role_at_branch` adds `assignedRoleId` and `reason`.
- `notifications/tasks.py::_send_push`:
  - opens `tenant_session_scope`;
  - loads devices for `user_ids`, and returns silently when there are none;
  - otherwise calls FCM, prunes invalid tokens, and raises on partial
    failure so `autoretry_for` retries the whole task.
- Web:
  - `NotificationCenterProvider` holds an in-memory list fed only by
    `PushNotificationsProvider`'s `onMessage`;
  - `use-push-notifications.ts::registerCurrentDevice` both prompts and
    registers, and is called from both login hooks plus the provider's
    mount, focus and 30-minute triggers.

## Goals / Non-Goals

**Goals:**
- Every staff notification is visible in the portal, whatever the
  browser's push state.
- Each step of the push chain that fails says so where the user (UI) or an
  operator (log) will see it.

**Non-Goals:**
- Real-time feed delivery via WebSocket or SSE. A 60-second poll plus a
  refresh on foreground push and on focus is enough for human-paced
  notifications, and adds no new infrastructure.
- Per-user notification preferences, muting, or per-event opt-out.
- Notifications for the visitor (they have no account).
- Fixing pytest's leakage of real `send_push` tasks into the dev Redis
  broker (seen while diagnosing: ~1,900 failed `tenant_acme_test`
  dispatches in the worker log). It's real noise, but a separate test
  harness issue.
- Flutter. The feed endpoints are client-neutral, and the mobile app can
  adopt them separately.

## Decisions

### D1. Record notifications inside `send_push`, keyed by a dispatch id

The service layer generates `dispatch_id = uuid4()` and passes it to
`send_push.delay(...)`. At the top of `_send_push`, before the device
lookup and the FCM call, the task inserts one row per user with
`INSERT … ON CONFLICT (dispatch_id, user_id) DO NOTHING` and commits.

- **Why in the task, not in the request?** `notify_user` has no DB session.
  It's called after the triggering transaction commits and is designed
  never to touch the request's session. Writing in the task keeps the
  request path untouched, which `security-architecture.md` §5 also
  requires for audit-like writes, and reuses the task's tenant session.
- **Why a dispatch id?** Celery is at-least-once, and `_send_push` raises
  on a partial FCM failure, so the whole task retries.
  `background-jobs.md` §2 requires the body to be idempotent. The unique
  `(dispatch_id, user_id)` constraint makes the insert a no-op on every
  rerun. One bulk insert per dispatch follows `query-performance.md` §3.
- **Committed before the FCM send**, so a send that exhausts its retries
  still leaves the in-app record.
- **A recording failure never blocks the push.** A `SQLAlchemyError` from
  the insert, such as a recipient id with no `users` row, is rolled back
  and logged as `WARNING notification_record_failed`, and the send carries
  on. Retrying the whole task for it would re-send to every device.
- `dispatch_id` is an optional task kwarg that defaults to a fresh uuid
  when it's absent. A task enqueued by the old code shape and still in the
  queue during deploy then runs fine, though without retry dedupe.

*Alternative considered*: a separate `record_notifications` task. That was
rejected because it's two tasks to keep consistent for one event, and the
record could exist with no push, or the reverse, depending on which task
ran.

### D2. `notifications` table (tenant schema)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `user_id` | uuid FK `users.id` | recipient |
| `dispatch_id` | uuid | unique with `user_id` |
| `title` | varchar(255) | |
| `body` | text | |
| `data` | JSONB | push `data`, including `invitationId`, `action`, `reason` |
| `read_at` | timestamptz null | |
| `created_at` / `updated_at` | timestamptz | declared directly, like `DeviceToken`: `TimestampMixin` also carries `deleted_at`, which these hard-deleted rows don't have |

- Index `(user_id, created_at DESC)` serves the list query.
- A partial index on `(user_id) WHERE read_at IS NULL` serves the unread
  count.
- No `deleted_at`. The rows are disposable UI state with no compliance
  value, and the audit trail lives in `audit_logs`. That's the same
  posture as `DeviceToken`, so purging hard-deletes them (D4).
- No FK to `invitations`. `data.invitationId` is enough to deep-link, and a
  notification shouldn't block an invitation hard-delete or need its own
  cascade.

### D3. Feed endpoints live in the `notifications` router, scoped by `get_current_user`

`NotificationRepository` gives every query a `user_id == caller.id` filter,
so there's no path that takes a user id from the client. Mark-one is
`UPDATE … SET read_at = now() WHERE id = :id AND user_id = :me AND read_at
IS NULL RETURNING`. When that returns no row, it's followed by an
existence check scoped to the caller: an already-read row returns 200
unchanged, and another user's or an unknown id returns 404. Mark-all is a
single `UPDATE … WHERE user_id = :me AND read_at IS NULL`.

None of this needs a `require_permission` gate. Every authenticated user
can read their own feed, the same as `POST /notifications/devices`.
Responses use `Envelope`/`PaginatedEnvelope` with `response_model` set
(`api-documentation.md` §1).

### D4. Purge rides the visit-lifecycle sweep

`sweep_tenant_visit_lifecycle` already runs every 15 minutes per active
tenant, inside a tenant session. It gains one bulk `DELETE FROM
notifications WHERE created_at < now() - interval '90 days'`, committed in
its own statement after the visit-lifecycle work, so a purge error can't
roll back check-out or archive changes. That avoids a second beat schedule
and a second per-tenant fan-out. The 90 days is a module constant, not a
setting. Nobody has asked for it to vary.

### D5. Web: the server is the source of truth, and push is only a refresh hint

`NotificationCenterProvider` becomes server-backed:

- **Load:** it loads `GET /notifications?pageSize=20` and the unread count
  when a token is present.
- **Refetch:** it refetches on a foreground `onMessage`, on
  `visibilitychange` to visible, and every 60 seconds while visible.
- **Foreground push:** `onMessage` keeps its toast, which is immediate
  feedback, but no longer appends a client-only item. It calls `refresh()`
  instead, so the bell and the server never disagree.
- **Reading:** `markRead(id)` and `markAllRead()` update optimistically,
  then call the API. On error they refetch, which reverts the optimistic
  change.
- **Opening the bell no longer marks everything read.** The previous
  client-only bell did that, which was harmless when the list vanished on
  reload. With server state it would silently clear every unread item, so
  the panel has an explicit **Mark all read** button. The bell badge shows
  the unread count (capped at "9+") instead of a dot.
- **Item click:** it navigates using the same
  `buildInvitationPath(data.invitationId)` already in the provider.
- **Labels:** the addressing badge (`role_assigned`/`delegated`) reads
  `data.reason` from the stored item, so badges survive a reload.

### D6. Web: separate "enable" (click only) from "refresh registration" (automatic)

`use-push-notifications.ts` exposes:

- `getPushState()`, which returns one of:
  - `'unavailable'`, with a reason of `'insecure-context'` or
    `'unsupported'`;
  - `'blocked'` when `Notification.permission === 'denied'`;
  - `'off'` when permission is `default`, or when it's `granted` but the
    token isn't registered yet;
  - `'enabled'`.
- `enablePush()`, which calls `Notification.requestPermission()` and then
  registers. It's only wired to the bell's button `onClick`, keeping the
  call inside the user gesture.
- `refreshRegistrationIfGranted()`, which never prompts. It runs `getToken`
  and registers only if permission is already `granted`. The login hooks
  and the provider's mount, focus and interval triggers call this instead
  of the old prompting function.

A registration failure inside `enablePush` shows a toast. One inside
`refreshRegistrationIfGranted` shows a toast only on the first failure per
session, so the 30-minute timer can't spam. The bell's status row
re-reads the state after each attempt.

### D7. Service-worker deep link

`firebase-messaging-sw.js::buildInvitationUrl` uses `/staff/invitations`
for a non-admin context, matching `PushNotificationsProvider`'s
`buildInvitationPath`. A comment in each file points to the other, since a
service worker can't import app modules.

## Risks / Trade-offs

- **Row growth.** One row per recipient per event. A busy branch with a
  role POC fan-out might write a few thousand rows a day per tenant. The
  90-day purge bounds this. The indexes keep the list and count queries on
  the user's own slice.
- **A 60-second poll per open tab.** Two cheap indexed queries a minute per
  tab. → The poll pauses while the tab is hidden.
- **A push arrives before its row is committed.** That can't happen,
  because the row is committed before the FCM send (D1). The refresh
  triggered by a foreground push therefore always finds the row.
- **Users who already denied permission** must re-allow it in browser
  settings, since no page can re-prompt. → The "blocked" state shows
  per-browser guidance, and the in-app feed works meanwhile.
- **Local dev over a LAN IP.** Push stays unavailable on
  `http://<LAN-IP>:5173`. → The state row says so, and the docs say to
  use `http://localhost:5173` or the DDEV HTTPS URL for push testing.

## Migration Plan

1. API:
   - add the `alembic_tenant` revision (generate the revision id rather
     than typing one) and check that `alembic -c alembic_tenant.ini heads`
     shows exactly one head;
   - upgrade every tenant, which locally means `tenant_default` only.
2. Deploy the API first. The new task kwarg is optional, so tasks
   already queued still run.
3. Restart the DDEV Celery worker
   (`supervisorctl restart webextradaemons:vmss-api-celery-worker`). It
   doesn't reload code, and the changed `send_push` body otherwise won't
   run.
4. Deploy the web portal. A user who previously dismissed the prompt sees
   "off" and can click **Enable notifications**.

Rollback: revert the web, then the API. The `notifications` table can stay,
since nothing else reads it, or be dropped by downgrading the revision.

## Open Questions

- Should the bell offer a "view all" page beyond the 20 most recent items?
  The API already pages, so it can be added later without any API change.
