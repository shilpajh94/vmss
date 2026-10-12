## 1. Visit timezone resolver

- [x] 1.1 In `src/vmss_api/invitations/service.py`, replace `_resolve_tenant_timezone(tenant)` with `async def _resolve_visit_timezone(tenant_db, tenant, *, company=None) -> ZoneInfo`. Order: `Company.default_timezone`, then `Tenant.timezone`, then `UTC`. Skip invalid names and log `invitations_invalid_timezone` at `WARNING` with `source` (design D1).
- [x] 1.2 Change `_end_of_visit_day_utc(visit_date, tz: ZoneInfo)` to take the resolved zone instead of `tenant`. Keep it a pure function.

## 2. Recalculate expiry on every visit-date write

- [x] 2.1 `create_invitation`: resolve the zone with the already-loaded company instance (no second company query) and compute `expires_at` from it.
- [x] 2.2 `approve_invitation`: compute `expires_at` with the resolved visit timezone.
- [x] 2.3 `reschedule_invitation`: always pass `expires_at=_end_of_visit_day_utc(new_date, tz)`, not only for `approved`. Update the docstring of `InvitationRepository.reschedule_if_eligible` to match.
- [x] 2.4 `edit_invitation`: when `preferred_visit_date` is in `changes` and differs from the stored date (and not stripped by the `checked_in` location-only filter), add `changes["expires_at"]` for the new date before `edit_if_eligible`.
- [x] 2.5 `check_in_by_qr_token`: compute `today_local` with `_resolve_visit_timezone` (design D3).

## 3. Backfill migration

- [x] 3.1 Run `ddev exec uv run alembic -c alembic_tenant.ini heads` and confirm `e5f7a9b1c3d4` is the single head.
- [x] 3.2 Add `alembic_tenant/versions/<rev>_realign_invitation_expiry_to_visit_day.py` (`down_revision="e5f7a9b1c3d4"`). Resolve the zone in Python from `{schema}.companies.default_timezone` → `global.tenants.timezone` (matched on `schema_name`) → `UTC`. Run one schema-qualified `UPDATE` that only targets non-terminal rows with a visit date whose `expires_at` is within ±5 s of `created_at + 168h` (design D4). Downgrade is a no-op.
- [x] 3.3 Apply to the dev tenant. Verify `INV-D127D29A` shows `2026-10-02 23:59:59` and `INV-2015854C` shows `2026-10-20 23:59:59` in `Asia/Kolkata`, and that the approved `INV-2765667F` (created 2026-09-15) is realigned too. Re-run `heads` to confirm one head.

## 4. Remove the dead TTL setting

- [x] 4.1 Delete `invitation_token_ttl_hours` from `src/vmss_api/core/config.py`, and `INVITATION_TOKEN_TTL_HOURS` from `.env.example`, `CI-CD/k8s.yml` and `CI-CD/Openstack-K8.yml`. Leave the local `.env` unstaged (git-workflow.md §5–6).
- [x] 4.2 Confirm `git grep -n invitation_token_ttl_hours` returns nothing in `src/` or `tests/`.

## 5. Tests (`src/vmss_api/invitations/tests.py`)

- [x] 5.1 Unit: `_end_of_visit_day_utc(date(2026,10,2), ZoneInfo("Asia/Kolkata"))` returns `2026-10-02T18:29:59Z`, and with `UTC` returns `2026-10-02T23:59:59Z`.
- [x] 5.2 Resolver precedence: company `Asia/Kolkata` with tenant `UTC` resolves to Kolkata. Unset or invalid company with tenant `Asia/Kolkata` resolves to Kolkata. Both invalid resolves to UTC and the request still succeeds.
- [x] 5.3 Endpoint: creating a staff pre-registration and a walk-in for a future date returns `expiresAt` equal to the end of that day in the company timezone, regardless of submission time.
- [x] 5.4 Endpoint: rescheduling a `submitted` invitation moves `expiresAt` to the end of the new day. Repeat for `approved`.
- [x] 5.5 Endpoint: an edit that sets `preferredVisitDate` moves `expiresAt`. An edit without it leaves a staff-extended `expiresAt` unchanged.
- [x] 5.6 QR check-in: with company `Asia/Kolkata` and tenant `UTC`, a scan at 2026-10-02 00:30 IST for a 2026-10-02 visit succeeds (freeze/patch "now").
- [x] 5.7 Permission-denied and tenant-isolation coverage: confirm the existing reschedule/edit tests cover both, and add them if missing (testing-standards.md §2).
- [x] 5.8 Migration: test the backfill SQL against seeded rows (old-TTL open row realigned; denied, checked-out and extended rows untouched).

## 6. Docs and verification

- [x] 6.1 `docs/features/invitations.md`: remove the `INVITATION_TOKEN_TTL_HOURS` row. Document the end-of-visit-day expiry rule, the company → tenant → UTC timezone precedence, and that reschedule/edit recalculate expiry.
- [x] 6.2 Run `ruff check`, `ruff format --check`, and `mypy` on touched modules, then `ddev exec uv run pytest` (a single process, never parallel). Note any failures that already exist on this branch and aren't caused by this change.
- [ ] 6.3 Manual check: reopen Visitor Info for `INV-D127D29A` in the staff portal. `Expires` should read "Oct 2, 2026, 11:59 PM".
