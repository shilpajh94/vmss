## 1. Schema and repository

- [x] 1.1 Add `"status_changed_at"` to `InvitationSortableField` and an
  optional `status_changed_at: datetime | None` field to
  `InvitationListItemOut` in `invitations/schemas.py`.
- [x] 1.2 Add `_status_changed_at_expr()` to `invitations/repository.py`,
  following design.md Decision 1: the `COALESCE`/`CASE`/`GREATEST`
  expression, with the `archived_at IS NOT NULL` guard on
  `rescheduled_at`.
- [x] 1.3 Widen `TenantScopedRepository.paginate`'s `order_by` in
  `core/database.py` to accept a single expression or a sequence. Keep
  existing callers unchanged.
- [x] 1.4 Update `InvitationRepository.list_page` to resolve
  `status_changed_at` to the new expression. Apply `nulls_last()` to the
  `submitted_at`/`created_at` columns, and append `Invitation.id.asc()` as
  the tie-breaker for every sort.

## 2. Service and router

- [x] 2.1 Add `status_changed_at(invitation) -> datetime` to
  `invitations/service.py`, mirroring the SQL expression in Python.
- [x] 2.2 Populate `status_changed_at` in the router's
  `_to_list_item_out`.
- [x] 2.3 Run `EXPLAIN ANALYZE` on a status-filtered
  `sortBy=status_changed_at` page against the seeded dev DB, and record
  the result in the PR description (design.md Risks).

## 3. Tests (`invitations/tests.py`, via factories)

- [x] 3.1 Check-in column: a later check-in sorts first, even when its
  `submitted_at` is older. Assert `statusChangedAt` in the response.
- [x] 3.2 Each of approved, checked_out, denied, and archived sorts by its
  own timestamp. Also test `sortOrder=asc`.
- [x] 3.3 Requested column: a reverted approval, and a rescheduled
  archived invitation, sort by the revert or reschedule time. A plain
  reschedule of a never-archived submitted invitation does not move it.
- [x] 3.4 Mixed-status list without a `status` filter is interleaved by
  each row's own status time.
- [x] 3.5 Stable paging: more than one page of rows with identical
  timestamps, walked page by page, returns each id exactly once. Test
  both the default sort and `status_changed_at`.
- [x] 3.6 Parity: the Python `status_changed_at` matches the SQL ordering
  for every status, including the revert and reschedule cases.
- [x] 3.7 The default sort is unchanged: the existing
  `test_list_invitations_sort_order` still passes, and an unknown
  `sortBy` is still a 422.
- [x] 3.8 Permission-denied and tenant-isolation coverage: confirm the
  existing list tests still pass with `sortBy=status_changed_at` (a host
  without `invitations:view-all` gets 403, and a second tenant's rows are
  not returned).

## 4. Docs and checks

- [x] 4.1 Update the `sortBy` table in `docs/features/invitations.md` with
  the new value, its per-status meaning, and the `statusChangedAt` row
  field.
- [x] 4.2 Run `ruff check`, `ruff format --check`, `mypy` on `core/`, and
  `ddev exec uv run pytest src/vmss_api/invitations` (not in parallel
  with other pytest runs).

## 5. Paired web change (VMMS_WEB, separate repo)

- [x] 5.1 Propose a paired OpenSpec change in `VMMS_WEB` that updates the
  `admin-invitations` and `staff-dashboard` specs: board columns order
  newest first by status-changed time.
- [x] 5.2 In that change, have `use-paged-board-columns.ts` (or the
  `visit-request-summary-repository.ts` list call) send
  `sortBy=status_changed_at` (implemented by applying `VMMS_WEB`
  `sort-invitation-board-by-status-date`; that change's design leaves
  `statusChangedAt` out of the Zod schema, since no card renders it yet).
