## 1. Service

- [x] 1.1 Add optional `device: Device | None = None` to `check_in_by_code` and `check_out_by_code` in `invitations/service.py` and forward it to `_check_in_resolved` / `_check_out_resolved`

## 2. Router

- [x] 2.1 Add `device: Annotated[Device | None, Depends(_public_device)]` to `check_in_by_code` and `check_out_by_code` and pass it to the service
- [x] 2.2 Add `diff=_device_diff(device)` to both audit-log entries
- [x] 2.3 Wrap the response data with `_attach_devices(out, invitation, tenant_db)` so `checkInDevice` / `checkOutDevice` are returned

## 3. Tests and docs

- [x] 3.1 Tests: code check-in/out with a valid device records and returns it; omitted header unchanged; unapproved/disabled/unknown device rejected; location mismatch rejected; idempotent repeat keeps first device
- [x] 3.2 Update `docs/features/invitations.md` for the `device-id` header on the code endpoints
- [ ] 3.3 Run `ruff check`, `ruff format --check`, and `ddev exec uv run pytest`
