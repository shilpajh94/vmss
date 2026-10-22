## Why

The QR check-in/check-out endpoints record which kiosk/security device performed the action (optional `device-id` header, `add-kiosk-device-approval-and-traceability`). The SMS-code equivalents, `PATCH /api/v2/invitations/code/check-in` and `/code/check-out`, were added separately and do not accept it, so code-based entries have no device traceability and bypass device approval and location checks.

## What Changes

- `PATCH /api/v2/invitations/code/check-in` and `/code/check-out` accept the optional `device-id` header, with the same semantics as the QR endpoints: unknown/unapproved/disabled device is rejected, absent header keeps working.
- The resolved device is persisted as `check_in_device_id` / `check_out_device_id` on the invitation, subject to the same branch/building location validation as QR check-in.
- The code check-in/out responses expose `checkInDevice` / `checkOutDevice`.
- The audit-log entries for code check-in/out carry the device in their diff, as the QR ones do.
- No new column, migration, or response shape beyond the two fields already present on `InvitationQrCheckInOut`.

## Capabilities

### New Capabilities

### Modified Capabilities
- `invitations`: code-based check-in and check-out accept and persist a device id, matching the QR endpoints.

## Impact

- `src/vmss_api/invitations/router.py` (`check_in_by_code`, `check_out_by_code`), `service.py` (`check_in_by_code`, `check_out_by_code`), tests, `docs/features/invitations.md`.
- Additive and backward compatible: header is optional, so existing clients are unaffected (stays in `/api/v2`).
