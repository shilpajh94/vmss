## 1. Schema and migration

- [x] 1.1 Add `invitation_id: Mapped[uuid.UUID | None]` to `Notification` in `notifications/models.py`: FK `invitations.id`, `ondelete="CASCADE"`, indexed (design.md D1); update the docstring
- [x] 1.2 Generate a new `alembic_tenant` revision id (never hand-type one) off the current head `cf04d5501383`: add the column with explicit `schema=`, backfill from `data->>'invitationId'` with a text comparison, delete orphans, then create the index and the FK in that order (D4); downgrade drops FK, index, column
- [x] 1.3 Run `ddev exec uv run alembic -c alembic_tenant.ini heads` and confirm a single head
- [x] 1.4 Apply to every local tenant via `scripts/upgrade_all_tenants.py`; confirm `tenant_default` keeps exactly the notifications naming live invitations (~364 as of 2026-10-23) and the unread count drops to ~195

## 2. Repository

- [x] 2.1 `record_for_users`: set `invitation_id` from `data["invitationId"]`, recording a row only when the invitation exists, keeping `ON CONFLICT DO NOTHING` (D3)
- [x] 2.2 `list_page` and `count_unread`: `LEFT JOIN invitations` and exclude rows whose invitation is soft-deleted, applying the same condition to the `total` query (D2)
- [x] 2.3 Note the cascade in the `InvitationRepository.delete_with_children` docstring (it no longer needs to know about notifications)

## 3. Tests (`notifications/tests.py`, factories, real Postgres)

- [x] 3.1 Drop the `vmss_test` DB first so `create_all` picks up the new column
- [x] 3.2 Unread count and list exclude a soft-deleted invitation's notifications; list `total`, `unreadOnly` list, and count agree
- [x] 3.3 Hard-deleting an invitation (via `delete_with_children` and via raw SQL `DELETE`) removes its notifications for every recipient and leaves others
- [x] 3.4 `record_for_users` for a missing invitation records nothing and doesn't raise; a redelivered dispatch is still a no-op

## 4. Docs

- [x] 4.1 Document the invitation-cascade behaviour and the hidden-when-soft-deleted rule in `docs/features/notifications.md`

## 5. Earlier verification (before clear-all was dropped)

- [x] 5.1 `ruff check`, `ruff format --check`, `mypy` on `notifications/`; notifications, invitations, retention, approvals, and docs test modules green

## 6. Remove clear-all (design.md D5)

- [x] 6.1 Remove the `DELETE ""` route `clear_notifications` and the `ClearNotificationsOut` import from `notifications/router.py`
- [x] 6.2 Remove `ClearNotificationsOut` from `notifications/schemas.py`, `service.clear_all` from `notifications/service.py`, and `NotificationRepository.delete_all_for_user` from `notifications/repository.py`
- [x] 6.3 Remove the three clear-all tests (`test_clear_all_*`) and the `("DELETE", "/api/v1/notifications")` row in `test_feed_endpoints_require_auth` from `notifications/tests.py`; remove the `ClearNotificationsOut` case from `tests/test_api_documentation.py`
- [x] 6.4 Remove the `DELETE /api/v1/notifications` table row and the "Clear all" bell sentence from `docs/features/notifications.md`
- [x] 6.5 Replace `prune-orphaned-notifications-and-clear-all` with `prune-orphaned-notifications` in every code comment/docstring that cites it (`notifications/models.py`, `repository.py`, `tests.py`, `invitations/repository.py`, the `e6944d5e8ee2` migration, `docs/features/notifications.md`); `grep -rn "and-clear-all"` must come back empty
- [x] 6.6 Run `ruff check`, `ruff format --check`, `mypy` on `notifications/`, then only `src/vmss_api/notifications/tests.py` and `tests/test_api_documentation.py` (no full suite)
- [x] 6.7 `openspec validate prune-orphaned-notifications --strict`
