## 1. API: notifications table (design D2)

- [x] 1.1 Add `Notification` model to `notifications/models.py`: `Base` + `TimestampMixin`, columns per D2, unique `(dispatch_id, user_id)`, index `(user_id, created_at DESC)`, partial index `(user_id) WHERE read_at IS NULL`.
- [x] 1.2 Generate the `alembic_tenant` revision (generated id, not hand-typed). Pass `schema=` explicitly where the migration helpers ignore `schema_translate_map`. Confirm `alembic -c alembic_tenant.ini heads` shows one head.
- [x] 1.3 Upgrade `tenant_default` locally, and drop the `vmss_test` DB so the test schema picks up the new table.

## 2. API: record on dispatch (design D1)

- [x] 2.1 `NotificationRepository.record_for_users(dispatch_id, user_ids, title, body, data)`: a single bulk `INSERT … ON CONFLICT (dispatch_id, user_id) DO NOTHING`.
- [x] 2.2 `service.notify_user`/`notify_role_at_branch`: generate a `dispatch_id` and pass it to `send_push.delay`.
- [x] 2.3 `tasks.send_push`/`_send_push`: accept optional `dispatch_id` (default a fresh uuid). Record the rows and commit before the device lookup. Log `INFO push_no_registered_devices` with `recipient_count` when no devices are found.

## 3. API: feed endpoints (design D3)

- [x] 3.1 Schemas: `NotificationOut` (`id`, `title`, `body`, `data`, `createdAt`, `readAt`), `NotificationListQuery` (`page`, `pageSize` ≤ 100, `unreadOnly`) and `UnreadCountOut`, all `CamelModel`.
- [x] 3.2 Repository methods, every one filtered by the caller's `user_id`: `list_page`, `count_unread`, `mark_read` (an `UPDATE … RETURNING`, then a scoped existence check), and `mark_all_read` (a single `UPDATE`).
- [x] 3.3 Service and router: `GET /notifications`, `GET /notifications/unread-count`, `PATCH /notifications/{id}/read` and `POST /notifications/read-all`, with `response_model` set and the `success_response` envelope. Register no new router, since the routes extend the existing `notifications` router.

## 4. API: retention (design D4)

- [x] 4.1 `NotificationRepository.purge_older_than(cutoff)`: a single `DELETE`.
- [x] 4.2 Call it from `sweep_tenant_visit_lifecycle`'s tenant session after the lifecycle commit, in its own commit, with a 90-day module constant.

## 5. API tests (`notifications/tests.py`)

- [x] 5.1 `send_push` records one row per recipient even with zero devices, and logs `push_no_registered_devices`.
- [x] 5.2 Running the same `dispatch_id` twice leaves one row per recipient, and a role fan-out of N holders gives N rows.
- [x] 5.3 An FCM failure that exhausts retries still leaves the rows recorded.
- [x] 5.4 The list returns only the caller's rows, newest first, with pagination metadata. `unreadOnly` and `unread-count` agree.
- [x] 5.5 Mark-read of another user's id gives 404 and their row stays unread. Re-marking a read row keeps the original `readAt`. Read-all changes only the caller's rows.
- [x] 5.6 Every feed endpoint returns 401 without a token. There's no permission-denied case, because the endpoints are self-scoped with no `require_permission`. Note that in the test docstring.
- [x] 5.7 Tenant isolation: a notification in one tenant schema isn't visible through a session bound to another (reuse `make_tenant_schema`/`open_tenant_session`).
- [x] 5.8 Purge deletes rows older than 90 days and keeps newer ones.
- [x] 5.9 Extend `test_response_schemas_render_camel_case` (or assert in the feature's tests) for `NotificationOut`.

## 6. Web: data layer (VMMS_WEB)

- [x] 6.1 Add `notifications`, `notificationsUnreadCount`, `notificationMarkRead` and `notificationsReadAll` to `data/api/api-endpoints.ts`.
- [x] 6.2 Domain entity and schema for a feed item. Extend the `NotificationRepository` interface and its HTTP implementation with `listNotifications`, `getUnreadCount`, `markRead` and `markAllRead`.
- [x] 6.3 Use cases for each, wired in `composition-root.ts` following the existing lazy-resolver pattern.

## 7. Web: server-backed bell (design D5)

- [x] 7.1 Rewrite `notification-center-context.tsx` to load the feed and unread count from the API when signed in. Refresh on `visibilitychange` and on a 60-second interval while visible. Expose `refresh`, plus optimistic `markRead`/`markAllRead` with revert on error.
- [x] 7.2 `PushNotificationsProvider` `onMessage`: keep the toast, and replace `addNotification` with `notificationCenter.refresh()`.
- [x] 7.3 `NotificationBell.tsx`: render server items (title/body, relative `createdAt`, and the badge from `data.reason`). Clicking marks the item read and navigates via `buildInvitationPath`, moved to a shared helper.

## 8. Web: explicit push enablement (design D6)

- [x] 8.1 Split `use-push-notifications.ts` into `getPushState()`, `enablePush()` (prompts, click only) and `refreshRegistrationIfGranted()` (never prompts). Keep `unregisterCurrentDevice`.
- [x] 8.2 Switch both login hooks and the provider's mount, focus and interval triggers to `refreshRegistrationIfGranted()`.
- [x] 8.3 Add a push status row to the bell panel for each state (enabled, off with an Enable button, blocked with guidance, and unavailable with its reason).
- [x] 8.4 Show a toast for a failure in `enablePush`, and only the first failure per session in `refreshRegistrationIfGranted`.

## 9. Web: service worker (design D7)

- [x] 9.1 `public/firebase-messaging-sw.js`: non-admin deep link to `/staff/invitations`, with cross-reference comments in the SW and in the shared `buildInvitationPath` helper.

## 10. Docs and verification

- [x] 10.1 `docs/features/notifications.md`: the feed endpoints, the dispatch-recording behavior, retention, the push states, and the local push-testing note (use `localhost` or the DDEV HTTPS URL, not a LAN IP).
- [x] 10.2 API: `ruff check`, `ruff format --check` and `mypy` on `notifications/`, then a single `ddev exec uv run pytest src/vmss_api/notifications src/vmss_api/invitations`. Diff the failures against a baseline run, because pre-existing failures exist.
- [x] 10.3 Web: `npm run lint` and `npm run build` (typecheck). Do not run prettier.
- [ ] 10.4 Restart the DDEV Celery worker. Then do a manual end-to-end check: sign in on `localhost`, see the push state as "off", click Enable, approve an invitation in another session, and see both the system notification and the bell item. Also confirm `device_tokens` now has a real row.
