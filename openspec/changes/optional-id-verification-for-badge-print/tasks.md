## 1. Setting

- [x] 1.1 Add `badge_print_requires_id_verification` (bool, `server_default true`) to `Tenant`, a global Alembic migration with downgrade, and expose it in `TenantOut`
- [x] 1.2 Accept it in `TenantSettingsUpdate` and `PATCH /tenants/me/settings` (include in the `changes` list, `set_flags` and the audit diff); update `docs/features/tenant.md`

## 2. Print gate

- [x] 2.1 Change `unmet_print_conditions` to take `require_id_verification` and skip `id_not_verified` when false; pass the tenant value from `_create_print` (covers print and reprint, reception and kiosk)
- [x] 2.2 Update `docs/features/checkin_badge.md` to describe the optional condition

## 3. Check-in enforcement

- [x] 3.1 In `invitations/checkin.py::_perform_check_in`, after the idempotent/archived/watchlist checks, raise `409` when the badge flow is on, the tenant skips ID verification at print, and `id_verified_at` is `None`
- [x] 3.2 Confirm the tenant objects passed from `checkin/service.py` and the kiosk paths carry the flag; fix any `type: ignore` call site that does not
- [x] 3.3 Optionally mirror the rule in `check_in_if_eligible`'s atomic `WHERE` (design Decision 5)

## 4. Tests

- [x] 4.1 `checkin/tests.py`: print succeeds without verified ID when skipped; `photo_missing` still blocks; default tenant still `409`s `id_not_verified`; reprint follows the same rule
- [x] 4.2 `checkin/test_kiosk.py`: kiosk print honours the setting
- [x] 4.3 Badge-scan check-in `409`s when unverified and succeeds after verify-id; check-out unaffected; default tenant unaffected
- [x] 4.4 `tenant/tests.py`: admin can toggle, non-admin gets `403`, audit written; permission-denied and tenant-isolation cases per `testing-standards.md` §2
- [x] 4.5 Run the targeted set only: `checkin`, `invitations` check-in tests, `tenant`, and `tests/test_api_documentation.py` (`testing-standards.md` §5)
