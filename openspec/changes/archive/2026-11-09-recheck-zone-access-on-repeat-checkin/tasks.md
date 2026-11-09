## 1. Gate

- [x] 1.1 Add `record_allowed: bool = True` to `enforce_checkin_zone` in `access_control/checkin_gate.py`; when `False`, skip writing the `entry` event for an allowed decision (denials are always recorded)
- [x] 1.2 Confirm the snapshot passed to `can_enter` is correct for an already-checked-in visit

## 2. Check-in paths

- [x] 2.1 In `_check_in_resolved` (`invitations/checkin.py`), on the `checked_in` early return, compute `today_local` and call `enforce_checkin_zone(..., record_allowed=False)` when `tenant.zone_access_enabled`, then return `(invitation, "Verification passed", False)`
- [x] 2.2 Leave `_perform_check_in` (tracking-ID) unchanged: it never applies zone rules on a first check-in either
- [x] 2.3 Verify `PATCH /invitations/qr/{token}/check-in` and `/invitations/code/check-in` both pick this up through `_check_in_resolved`
- [x] 2.4 Update the route docstrings in `invitations/router.py` (idempotent no-op now re-checks zone access)

## 3. Tests

- [x] 3.1 Repeat check-in with zone still allowed: 200, no new entry event, no re-stamp
- [x] 3.2 Zone removed after check-in: 403 with reason, `denied` event, audit row, visit still `checked_in`
- [x] 3.3 Zone added after check-in: 200
- [x] 3.4 Same cases through the check-in-code endpoint
- [x] 3.5 No device / non-security device / multi-zone device / toggle off: unchanged idempotent 200
- [x] 3.6 Check-in after check-out uses updated zones

## 4. Docs and verification

- [x] 4.1 Update `docs/features/access_control.md` (the invitations doc has no zone section; the check-in behavior is documented in access_control.md)
- [x] 4.2 Run `ddev exec uv run pytest` on `access_control` and `invitations` tests plus `tests/test_api_documentation.py`, then `ruff check` and `ruff format --check`
