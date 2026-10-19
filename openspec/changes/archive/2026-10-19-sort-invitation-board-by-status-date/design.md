## Context

`InvitationRepository.list_page` maps `sortBy` (`submitted_at` or
`created_at`) to one column and calls `TenantScopedRepository.paginate`
with a single `ORDER BY` expression and no tie-breaker. The web board
(`VMMS_WEB` `use-paged-board-columns.ts`) issues one query per column
(`status=submitted|approved|checked_in|checked_out|denied|archived`),
never sends `sortBy`, and does not re-sort on the client. Each status
already has its own timestamp column: `approved_at`, `checked_in_at`,
`checked_out_at`, `denied_at`, `archived_at`, `approval_reverted_at`,
and `rescheduled_at`. `_EXPORT_DATE_COLUMNS` already maps status to
timestamp for the export.

## Goals / Non-Goals

**Goals:**
- Order rows by when each one entered its current status, on request,
  using one SQL expression that works with or without a `status` filter.
- Make paging deterministic for every `sortBy` value.

**Non-Goals:**
- Changing the default `sortBy`.
- Adding a stored `status_changed_at` column or a migration.
- Re-sorting on the client.
- Changing the Flutter app. It can opt in later.

## Decisions

### 1. A computed SQL expression, not a new column

The status-changed time is computed with one SQL expression in a new
`_status_changed_at_expr()` helper in `invitations/repository.py`:

```
COALESCE(
  CASE status
    WHEN 'submitted'   THEN GREATEST(submitted_at, approval_reverted_at,
                                     CASE WHEN archived_at IS NOT NULL THEN rescheduled_at END)
    WHEN 'approved'    THEN approved_at
    WHEN 'checked_in'  THEN checked_in_at
    WHEN 'checked_out' THEN checked_out_at
    WHEN 'denied'      THEN denied_at
    WHEN 'archived'    THEN archived_at
  END,
  submitted_at, created_at)
```

- Postgres `GREATEST` ignores NULLs, so a revert or reschedule time only
  counts when it exists.
- The `archived_at IS NOT NULL` guard limits the reschedule bump to
  invitations that came back from `archived`, which is the only reschedule
  that changes status. A plain reschedule of a never-archived invitation
  does not move it.
- *Alternative considered*: a denormalised `status_changed_at` column,
  written by every state-machine `UPDATE`. It is indexable, but it needs
  a migration across both Alembic trees, a backfill, and a change to
  about ten transition methods, and any transition that misses it fails
  silently. Not worth it at board volumes. Revisit if the list query
  shows up in slow-query logs.

### 2. Expose the same expression as a row field

**Chosen:** a Python helper, `status_changed_at(invitation)`, in
`invitations/service.py` that mirrors the `CASE` expression and is used
by `_to_list_item_out`. Every column it reads is already loaded on the
row, so it adds no extra query and keeps `paginate`'s `list[Invitation]`
return type unchanged. A parity test asserts that the helper and the
SQL ordering agree.
*Alternative considered*: selecting the SQL expression as a labelled
extra column. That would change `paginate`'s return shape just for this
one caller.

### 3. Tie-breaker in the repository, not in `paginate`

`list_page` passes `order_by=(primary, Invitation.id.asc())`. `paginate`
widens its `order_by` parameter to accept a sequence. That change is
backward compatible, because existing callers pass one expression. NULL
primary keys are impossible for `status_changed_at` because of the
`COALESCE`. For `submitted_at` they use `nulls_last()`, so a stray NULL
cannot jump to the top of a `desc` list.

### 4. Opt-in rather than a new default

The default stays `submitted_at`. Changing what an existing request
returns would count as a semantics change under `api-conventions.md` §2,
and the Flutter app and integrations ship on their own schedules. The
web boards opt in through a paired change in `VMMS_WEB`.

## Risks / Trade-offs

- [The `CASE` expression can't use an index, so the database must sort
  every matching row] → each board query is already narrowed by
  status, branch, and soft-delete, and per-tenant volumes are in the low
  thousands. Run `EXPLAIN ANALYZE` on the seeded dev DB during
  implementation, and fall back to the stored column (Decision 1's
  alternative) if needed.
- [The Python helper and the SQL expression drift apart] → a parity test
  covers every status, the revert case, and the reschedule-from-archive
  case.
- [The web change lands after the API change] → nothing breaks. The
  boards just keep today's order until the web change ships.

## Migration Plan

No database migration is needed. Deploy the API first; the change is
additive. Then ship the `VMMS_WEB` change that sends
`sortBy=status_changed_at`. To roll back, revert the web change; the API
change is inert without it.
