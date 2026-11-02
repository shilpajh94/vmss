## Context

See proposal.md, Why. The current shape of things:

- `notifications` (tenant schema) has `user_id`, `dispatch_id`, `title`,
  `body`, `data JSONB`, `read_at`. The invitation is referenced only as
  `data->>'invitationId'`, a string with no FK. Every payload built in
  `invitations/push_notifications.py` carries it.
- Invitations are hard-deleted by
  `InvitationRepository.delete_with_children` (the retention purge, which
  deletes children explicitly because "the FKs have no `ON DELETE
  CASCADE`") and by `scripts/qa_regression/reset_qa_data.py` (raw SQL).
  Invitations also have a `deleted_at` soft-delete column.
- The feed is self-scoped and carries no RBAC gate. `mark_all_read` is a
  single bulk `UPDATE`, and none of the feed routes write an audit entry.

## Goals / Non-Goals

**Goals:**
- Make orphaned notifications impossible from any deletion path,
  including deletion paths that don't exist yet and raw SQL.
- Make the count and the list agree with what the board shows.
- Clean up the orphans already sitting in every tenant.

**Non-Goals:**
- Hiding notifications for invitations that are live but terminal
  (denied, checked-out). They are real history, and marking them read
  already clears them from the badge.
- Any way for staff to delete notifications (single or all), see D5.
- Changing push (FCM) delivery behaviour.

## Decisions

### D1: A real `invitation_id` FK with `ON DELETE CASCADE`

Add `notifications.invitation_id UUID NULL REFERENCES invitations(id) ON
DELETE CASCADE`, plus an index on it (Postgres doesn't index FK columns
automatically, and the cascade looks rows up by it).

- *Why*: the database enforces the requirement "deleting an invitation
  deletes its notifications" on every path: the purge, the QA script, a
  future admin delete, an ad-hoc `psql`. No caller has to remember it.
- *Alternative, add `Notification` to `_PURGE_TABLES_PARENT_FIRST`*:
  fixes only the purge. The QA script, which is the actual source of
  today's 5,883 orphans, would still leak. The purge also backs up every
  listed table before deleting, and notifications are disposable, so
  there's nothing worth backing up.
- *Alternative, filter at read time on `data->>'invitationId'` with an
  anti-join*: hides the symptom while the dead rows keep growing. It also
  needs an expression index and a text-to-uuid comparison on every poll.
- `NULL` stays valid for notifications that aren't about an invitation.
  None exist today, but the dispatch primitive is generic.
- The purge's explicit child deletes stay as they are. Its docstring gets
  a line noting that `notifications` goes via the cascade.

### D2: Soft-deleted invitations are hidden at read time, not deleted

`list_page` and `count_unread` `LEFT JOIN invitations ON id =
invitation_id` and keep only rows where `invitation_id IS NULL OR
invitations.deleted_at IS NULL`. The `total` count uses the same
condition, so list, total, and badge always agree.

- *Why not delete on soft-delete*: soft-delete exists so a row can be
  restored or kept for compliance. Deleting the notifications would make a
  restore half-complete. The join is a PK lookup per row on a page of at
  most 100, and the count stays on the existing
  `ix_notifications_user_unread` partial index.
- Mark-read and read-all operate on the user's rows without this filter.
  That is harmless: reading a hidden row has no visible effect.

### D3: Populate `invitation_id` at record time, tolerating a deleted invitation

`NotificationRepository.record_for_users` sets `invitation_id` from
`data.get("invitationId")`, after a PK lookup confirms that invitation
exists. (Implemented as a lookup and then the insert, not the
`INSERT ... SELECT` first planned. The behaviour is the same, and
`INSERT ... SELECT` had the same FK race anyway.) If the invitation is
already gone, no row is recorded, because a notification about a deleted
invitation is exactly what this change removes. The push itself is still
sent.

- *Why*: `send_push` is a Celery task, so the invitation can be purged
  between enqueue and run. A plain insert would raise an FK violation and
  burn retries on a dispatch that can never succeed. A delete that races
  the insert still fails it on the FK. `_send_push` already catches that
  `SQLAlchemyError`, logs `notification_record_failed`, and sends the
  push anyway.
- The `ON CONFLICT DO NOTHING` on `(dispatch_id, user_id)` is unchanged,
  so redelivery is still a no-op (background-jobs.md §2).

### D4: One-time cleanup inside the tenant migration

A single `alembic_tenant` revision:
1. adds the nullable column (with `schema=` passed explicitly to
   `op.add_column`, since it ignores `schema_translate_map`);
2. backfills it with `UPDATE notifications n SET invitation_id = i.id FROM
   invitations i WHERE i.id::text = n.data->>'invitationId'`, comparing as
   text so a malformed id can't abort the migration with a cast error;
3. deletes the orphans: `WHERE data ? 'invitationId' AND invitation_id IS
   NULL`;
4. creates the index and then the FK constraint (`ON DELETE CASCADE`).

Order matters: the FK can't be added while orphans exist, and backfilling
before creating the index keeps the update cheap. Downgrade drops the FK,
the index, and the column. Deleted orphans are not restored. They were
dead references to rows that no longer exist, and that is acceptable for
disposable UI state.

### D5: No clear-all; "Mark all read" stays the only bulk action

A first pass of this change added `DELETE /api/v1/notifications`, which
permanently deleted all of the caller's notifications, plus a "Clear all"
button. It was dropped before commit.

- *Why drop it*: the complaint was a badge counting dead notifications.
  D1–D4 fix that at the source, and "Mark all read" already takes the
  badge to 0. A permanent delete one click from the bell adds a way to lose
  a still-useful pointer (a pending approval) with no undo, for little gain.
- *Not a data-integrity issue either way*: notifications are disposable
  copies of pushes. Invitations and the audit log are untouched, and the
  90-day purge already hard-deletes old rows. The reason to drop it is UX
  risk versus benefit, not data loss.
- *Alternative, "Dismiss all" (hide, don't delete)*: needs a
  `dismissed_at` column, a migration and a third feed state, for a panel
  that only shows the newest 20 anyway. Revisit if staff ask for a
  tidier panel after this ships.

## Risks / Trade-offs

- [The migration runs long on a tenant with a very large `notifications`
  table] → The work is one `UPDATE ... FROM` and one `DELETE` on a table
  already pruned to 90 days, and the largest known tenant is ~6k rows.
  Run `upgrade_all_tenants.py` in a normal deploy window.
- [The FK adds a parent-row lock to every notification insert] → It's a
  `KEY SHARE` lock on a PK lookup, negligible next to the FCM call in the
  same task.
- [Test DB built by `create_all` won't pick up the new column] → Drop
  `vmss_test` before the first test run (known gotcha).

## Migration Plan

1. Merge the API change and run
   `ddev exec uv run python scripts/upgrade_all_tenants.py` (locally, then
   per environment) to apply the revision to every tenant schema.
2. No web release is needed for the count fix. The web change only
   reverts uncommitted local edits, so it ships with nothing.
3. Rollback: downgrade the tenant revision (drops the column and FK). The
   list and count code from before the change works without the column,
   so revert the code first, then downgrade.
