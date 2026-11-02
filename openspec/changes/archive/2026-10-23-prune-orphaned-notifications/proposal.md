## Why

The staff bell shows **1345** unread while the Requested column holds 170
invitations. The extra notifications point at invitations that have since
been deleted. In local `tenant_default` on 2026-10-23, 5,883 of 6,247
notification rows reference an invitation that no longer exists, and only
~195 of 1,453 unread rows belong to a live invitation.

How it happens: `notifications` stores the invitation id only inside the
`data` JSONB, with no foreign key. Anything that hard-deletes invitations
leaves its notifications behind. Today that is
`scripts/qa_regression/reset_qa_data.py` and the 90-day invitation
retention purge (`invitations/tasks.py::purge_expired_invitations`). The
count and list endpoints then report those rows as if they were live.

## What Changes

- Notifications about an invitation are tied to it. When the invitation
  is hard-deleted, by any path, its notifications are deleted with it.
- The feed list and unread count leave out notifications whose invitation
  is soft-deleted (`deleted_at` set) or missing.
- A one-time tenant migration deletes the orphaned notifications that
  already exist in every tenant schema.
- "Mark all read" stays the only bulk action on the feed. A user-facing
  "Clear all" was considered and dropped (design.md D5): it's irreversible,
  and once the orphans are gone, "Mark all read" already zeroes the badge,
  which was the actual complaint.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `notifications`: the feed and unread count exclude notifications for
  deleted invitations, and deleting an invitation removes its
  notifications.

## Impact

- **Code**: `notifications/models.py` (new `invitation_id` column),
  `notifications/repository.py`, `tests.py`; the dispatch path
  (`record_for_users`) fills in `invitation_id`.
- **Migration**: one new `alembic_tenant` revision (add column + FK +
  index, backfill from `data->>'invitationId'`, delete orphans). It must be
  applied to every tenant (`scripts/upgrade_all_tenants.py`).
- **API**: no new routes. The list and count responses keep their shapes
  but return fewer stale rows. Not breaking under `api-conventions.md` §2.
- **Docs**: `docs/features/notifications.md` describes the cascade and the
  hidden-when-soft-deleted rule.
- **Clients**: the React portal and Flutter app get correct counts with no
  client change. `VMMS_WEB`'s same-named change only reverts the
  uncommitted "Clear all" button.
- **Already implemented:** a first pass of this change also built
  `DELETE /api/v1/notifications` (clear-all), uncommitted. Section 6 of
  tasks.md removes it.
