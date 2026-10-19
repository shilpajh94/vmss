## 1. Data model and migration

- [x] 1.1 Run `ddev exec uv run alembic -c alembic_tenant.ini heads` and confirm a single head before authoring.
- [x] 1.2 Add `archived_at: Mapped[datetime | None]` and `checked_out_automatically: Mapped[bool]` (server default `false`) to `Invitation` in `src/vmss_api/invitations/models.py`. Add short lifecycle comments in the existing section style.
- [x] 1.3 Add a tenant migration `alembic_tenant/versions/<generated-rev>_invitation_archive_and_auto_checkout.py`:
  - `upgrade()` adds both columns, passing `schema=` explicitly to `op.add_column`.
  - `downgrade()` first runs `UPDATE … SET status='approved' WHERE status='archived'`, then drops both columns with explicit `schema=`.
- [x] 1.4 Upgrade the local default tenant and drop `vmss_test` so the test DB picks up the new columns. Re-run the heads check.

## 2. Schemas and listing

- [x] 2.1 Add `archived = "archived"` to `InvitationStatus` and update its docstring's list of writers.
- [x] 2.2 Add `archived_at` and `checked_out_automatically` to the list-row, detail, tracking and check-in/check-out response schemas. Extend `test_response_schemas_render_camel_case` (or a feature test) to assert `archivedAt`/`checkedOutAutomatically`.
- [x] 2.3 Add `"archived": Invitation.archived_at` to `_EXPORT_DATE_COLUMNS` in `invitations/repository.py`.

## 3. Sweep repository methods

- [x] 3.1 Add `InvitationRepository.auto_check_out_expired(now)`. It is a single conditional `UPDATE … RETURNING id` with:
  - `WHERE`: (`status='checked_in'` OR `check_in_status='checked_in'`), `expires_at <= now`, `deleted_at IS NULL`.
  - `SET`: `status` and `check_in_status` = `checked_out`, `checked_out_at = expires_at`, `checked_out_automatically = true`.
- [x] 3.2 Add `InvitationRepository.archive_expired_no_shows(now)`. It is a single conditional `UPDATE … RETURNING id`:
  - `WHERE`: `status='approved'`, `check_in_status='unused'`, `expires_at <= now`, `deleted_at IS NULL`.
  - `SET`: `status='archived'`, `archived_at=now`.
- [x] 3.3 Add a bulk audit-insert helper for a list of invitation ids, with action, null actor, entity type `invitation` and a small `diff`. It runs in the caller's session (no separate session) so it commits with the transition.
- [x] 3.4 Make `check_out_if_checked_in` and `check_out_by_qr_if_eligible` also set `checked_out_automatically=False`.

## 4. Sweep tasks and scheduling

- [x] 4.1 In `src/vmss_api/invitations/tasks.py`, add `dispatch_visit_lifecycle_sweep`. It lists active tenants, enqueues one task per tenant with a per-tenant enqueue `try/except` + `ERROR` log, and calls `engine.dispose()`, mirroring `reports.tasks._dispatch_daily_rollup_snapshots`.
- [x] 4.2 Add `sweep_tenant_visit_lifecycle(tenant_id, tenant_schema)`. It:
  - binds `tenant_id` into structlog;
  - opens `tenant_session_scope`;
  - runs 3.1 and 3.2 with one `now`, writes their audit rows, and commits once;
  - logs `INFO` with both counts;
  - uses explicit `autoretry_for`/`retry_backoff`/`max_retries`, and logs `ERROR` with the tenant on exhaustion.
- [x] 4.3 In `src/vmss_api/core/celery_app.py`:
  - Add exact-name `task_routes` entries sending both new tasks to `cron_queue`, alongside the existing `vmss_api.invitations.tasks.*` → notifications glob.
  - Add the `beat_schedule` entry `visit-lifecycle-sweep` with `crontab(minute="*/15")`.

## 5. Archived-state service behavior

- [x] 5.1 In `_perform_check_in` and `check_in_by_qr_token`, return 409 with "Invitation is archived; reschedule it to admit the visitor" when `status == "archived"`. Keep the existing order: the idempotent checked-in no-op first, then watchlist.
- [x] 5.2 Add `InvitationRepository.reschedule_archived_if_eligible(...)`. It has the same history-capturing `SET` list as `reschedule_if_eligible`, plus `status='submitted'`, `approved_at=None` and `expires_at`, gated on `WHERE status='archived'`.
- [x] 5.3 Branch `reschedule_invitation` for `archived`:
  - Return 422 if the new date is before today in `_resolve_visit_timezone`.
  - Call 5.2, then `reset_all_for_invitation` and `activate_current_pending` in the same transaction, then commit.
  - Send the reschedule email task and the host push, plus the activated-step approver push (same block as `revert_invitation_approval`).
  - Admit `archived` in the service pre-check only.
- [x] 5.4 Update `edit_invitation` to admit `archived`:
  - An actual `preferred_visit_date` change applies the past-date 422, adds `status='submitted'`/`approved_at=None`/realigned `expires_at` to `changes`, and runs the step reset/activation before commit, with the approver push.
  - Otherwise the status is left `archived`.
- [x] 5.5 Confirm that extend, issue/reprint badge, revert, approve and deny already 409 on `archived` through their existing gates. Add no code unless a test shows otherwise.

## 6. Export

- [x] 6.1 In `src/vmss_api/invitations/export.py`:
  - Add the `archived` → `Archived` status label.
  - Append an `Archived At (<tz>)` column (column 32).
  - Add an `archived` row to the status → lifecycle-columns map (Requested At, Approved At, Archived At).
  - Write `System (auto check-out)` in Checked Out By when `checked_out_automatically` is set.

## 7. API tests

- [x] 7.1 Sweep, at the repository/service level against `vmss_test`. Cover:
  - an expired check-in is auto-checked-out with `checked_out_at == expires_at`, the flag set and a null actor;
  - an unexpired check-in is untouched;
  - an extended expiry postpones the check-out;
  - a legacy row with only `check_in_status='checked_in'` is still swept.
- [x] 7.2 Sweep archive. Cover:
  - an expired approved/unused invitation becomes `archived` with `archived_at` set;
  - unexpired approved, past-date `submitted`, `checked_out` and `denied` invitations are untouched.
- [x] 7.3 Sweep idempotency and audit. Cover:
  - one audit row per transition, with a null actor and the right action;
  - a second run changes nothing and adds no audit rows;
  - no email/push task is enqueued (patch `.delay`/`_notify_host` and assert not called).
- [x] 7.4 Sweep tenant isolation: two tenant schemas via `make_tenant_schema`/`open_tenant_session`. Sweeping tenant A leaves tenant B's expired rows untouched. Also test the dispatcher: one tenant's enqueue failure still enqueues the others.
- [x] 7.5 Manual check-out (staff and QR) after an auto check-out/re-entry cycle leaves `checked_out_automatically=false`. QR check-out of an already auto-checked-out invitation returns 409.
- [x] 7.6 Check-in of an archived invitation: QR, staff and public tracking-ID each return 409 with the archived message, and the state is unchanged.
- [x] 7.7 Reschedule from archived. Cover:
  - happy path: 200, `submitted`, `approvedAt` null, `archivedAt` kept, `expiresAt` realigned;
  - a two-step workflow is reset with the first step active and its approver pushed;
  - an auto-approve Company still leaves the invitation `submitted`;
  - a past date returns 422 with nothing sent;
  - a caller without `invitations:reschedule` gets 403;
  - re-approval re-sends the same QR token, which admits the visitor.
- [x] 7.8 Edit from archived. Cover:
  - a notes-only edit keeps `archived`;
  - a date change becomes `submitted` with steps reset;
  - a past date returns 422;
  - permission denied returns 403.
- [x] 7.9 Extend expiry on archived returns 409.
- [x] 7.10 `GET /invitations?status=archived` returns only archived rows. `?status=expired` returns 422.
- [x] 7.11 Export with `status=archived` has the header Requested At/Approved At/Archived At, with the date range on `archived_at`. The all-status export has 32 columns. An auto-checked-out row shows `System (auto check-out)`.
- [x] 7.12 Build new test rows with the existing factories, pinning `expires_at`/`status`/`check_in_status` explicitly (watch for the known unpinned-field factory flake).

## 8. Docs and verification (API)

- [x] 8.1 Update `docs/features/invitations.md`:
  - the `archived` status and how to leave it;
  - auto check-out semantics;
  - the new response fields.
- [x] 8.2 Update `docs/features/background-jobs.md` with the new beat entry, its schedule, its queue, and the fact that it needs beat and the cron worker running.
- [x] 8.3 Run `ruff check`, `ruff format --check` and `mypy` on the touched modules, then `ddev exec uv run pytest src/vmss_api/invitations src/vmss_api/reports src/vmss_api/dashboard`, then the full suite (one pytest process at a time). Diff any failures against a pre-change baseline.

## 9. Web portal (VMMS_WEB)

- [x] 9.1 `src/presentation/components/invitation-board/filter-options.ts`: add `{ value: 'archived', label: 'Archived' }` to `STATUS_OPTIONS` and `archived: 'Archived date'` to `EXPORT_DATE_LABELS`.
- [x] 9.2 `src/presentation/hooks/use-paged-board-columns.ts`, `use-invitations-board.ts` and `KanbanColumn.tsx`:
  - Add an `archived` board status and column after Denied, with column styling.
  - Make it a non-drag target.
- [x] 9.3 `src/presentation/components/invitation-board/VisitRequestCard.tsx`: include `archived` in the Reschedule/Edit action gate.
- [x] 9.4 Reschedule modal:
  - When the request is archived, set the date picker minimum to today.
  - Show a success toast "Visit rescheduled — awaiting re-approval" for archived requests.
  - Surface the API's 422 message on a past date.
- [x] 9.5 `VisitorInfoModal.tsx` (and the invitation detail zod schema):
  - Add an `archived` badge style.
  - Parse `archivedAt` and `checkedOutAutomatically`, both optional or nullable for backward compatibility.
  - Show "Archived on …" and a "Checked out automatically" note.
- [x] 9.6 Add or update component and hook tests for the new column, the action gating and the modal notes. Run the web lint, typecheck and test scripts. Do not run prettier.
