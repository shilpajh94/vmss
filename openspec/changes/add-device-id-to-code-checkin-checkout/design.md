## Context

The QR endpoints already take `device: Device | None = Depends(_public_device)` (router.py), pass it to `_check_in_resolved` / `_check_out_resolved`, which enforce location and write `device_pk`, then call `_attach_devices` on the response and `_device_diff` on the audit entry. The code endpoints share `_check_in_resolved` / `_check_out_resolved` but their service wrappers (`check_in_by_code`, `check_out_by_code`) don't accept or forward `device`, and the routes don't declare the dependency. So the gap is wiring only.

## Goals / Non-Goals

**Goals:**
- Code endpoints behave identically to QR endpoints regarding `device-id`.

**Non-Goals:**
- No schema/migration change; no change to code verification, lockout, or rate limits.
- No `device-id` on other endpoints.

## Decisions

- **Reuse `_public_device`** (bound to `track_default_tenant_db`), same as QR routes. Alternative: a new body field `deviceId`, rejected — header is the established convention and keeps parity for clients.
- **Forward `device` through the service wrappers** to the shared `_resolved` helpers rather than duplicating logic.
- **Device resolution order**: the dependency runs before the code is verified, so an invalid device yields its error before the code lockout counter is touched; same ordering as QR token routes.

## Risks / Trade-offs

- [Invalid `device-id` reveals nothing about the code] → device is validated independently of the code.
- [Idempotency-Key replay] → cached response returned; header still validated, as for QR.
