## 1. Permission

- [x] 1.1 Add `invitations:clear-all` to `auth/rbac_catalog.py` and grant it to Admin only
- [x] 1.2 Ensure existing tenants receive the permission (catalog sync or tenant migration, matching prior permission additions)

## 2. Repository and Task

- [x] 2.1 Add `InvitationRepository.list_ids_for_clear(limit, include_checked_in, from_date, to_date)` filtering on `preferred_visit_date` (inclusive, NULL dates excluded when bounded)
- [x] 2.2 Extract the shared backup-then-delete batch loop from `purge_expired_invitations`; keep retention behavior and `test_retention.py` unchanged
- [x] 2.3 Add `clear_tenant_invitations` Celery task (lock, retries, ERROR on exhaustion, request-id rebind, `from_date`/`to_date` args, `invitations_cleared` audit with actor and scope)

## 3. API

- [x] 3.1 Add `ClearAllInvitationsRequest` (`confirm`, `includeCheckedIn`, `fromDate`/`toDate`/`month`) with validation: month vs range exclusive, `fromDate <= toDate`, `YYYY-MM` format, confirm phrase matching scoped/unscoped and response schema in `schemas.py` extending `CamelModel`
- [x] 3.2 Add `POST /invitations/clear-all` route with `require_permission("invitations:clear-all")`, 202 envelope, `response_model=Envelope[...]`, 409 on held lock, Idempotency-Key support
- [x] 3.3 Add service method that validates, converts `month` to a date range, pre-checks the lock, and enqueues the task via `.delay()`

## 4. Tests

- [x] 4.1 Happy path: all invitations and dependents removed, other tenant untouched (tenant-isolation case)
- [x] 4.2 Permission-denied (403) and wrong/missing confirmation (422)
- [x] 4.3 Checked-in skipped by default, removed with `includeCheckedIn`
- [x] 4.4 Backup failure aborts deletion; second run is a no-op; concurrent request returns 409
- [x] 4.5 Audit row contains actor, scope, count, backup keys
- [x] 4.6 Scoped clear: month scope, inclusive range boundaries, invalid-scope 422s, NULL visit dates untouched, other tenant untouched

## 5. Docs

- [x] 5.1 Update `docs/features/invitations.md` with the endpoint, permission, scope options (month / date range), confirmation phrases, and warnings
- [x] 5.2 Run `ruff check`, `ruff format --check`, `mypy` on touched modules, full `pytest`, and `tests/test_api_documentation.py`
