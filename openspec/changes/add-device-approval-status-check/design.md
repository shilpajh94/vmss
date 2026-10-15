## Context

`devices/router.py` already has a public `POST /devices/register` that resolves the default tenant via `track_default_tenant` / `track_default_tenant_db` and is rate limited. `DeviceRepository.get_by_device_id` already returns a live (non-deleted) device by its string `device_id`. "Approved and usable" is `approval_status='approved'` and `is_active=true`; a disabled device stays `approved` with `is_active=false`. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- A read-only, side-effect-free status lookup by `deviceId`, reusing the existing public-endpoint plumbing.

**Non-Goals:**
- No change to registration, approval, or enable/disable behavior.
- No device authentication or secret; no push/webhook notification on approval.
- No authenticated variant (admins already have `GET /devices/{id}`).

## Decisions

1. **`GET /devices/approval-status?deviceId=...`, query param rather than path.** Device IDs are client-chosen strings up to 255 chars and may contain characters awkward in a path segment. A fixed literal path also avoids colliding with `/{device_pk}` (UUID); the route is still declared before the `/{device_pk}` routes, like `register`. Alternative `GET /devices/{deviceId}/status` rejected for the path-encoding and ambiguity reasons.
2. **Minimal response `DeviceApprovalStatusOut`** (`deviceId`, `approvalStatus`, `isActive`, `approved`). `approved` is a derived convenience (`approved` status and active) so the app doesn't re-implement the disabled-device rule. Branch, name, and approver are withheld because the endpoint is unauthenticated.
3. **404 for unknown devices**, not a synthetic "unregistered" 200. It lets the app distinguish "never registered, call register" from "pending". Alternative rejected: returning 200 with a null status.
4. **Reuse `track_default_tenant` / `track_default_tenant_db`** and `@limiter.limit` (60/minute per IP, matching `kiosks/router.py`'s public lookups; looser than register's 10/minute since the app polls). No audit entry: read-only, and polling would flood the audit log.
5. **Logic in `service.get_device_approval_status`** calling `DeviceRepository.get_by_device_id`; no new repository method or migration.

## Risks / Trade-offs

- [Device-ID enumeration: anyone who guesses an ID learns its status] → Response exposes only the status fields, rate limiting is per IP, and IDs are expected to be hardware/app-generated and non-sequential. Not a secret-bearing endpoint.
- [Polling load] → Single indexed lookup (`uq_devices_device_id`); 60/minute limit.
