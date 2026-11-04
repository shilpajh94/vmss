## Why

The badge print flow (`add-badge-print-flow`) is reception-only: every `/checkin/*` endpoint needs a staff bearer token and a `visitors:print_badge` grant. A self-service kiosk has no logged-in user, so a visitor cannot find their visit, confirm ID, take a photo and print a badge without a receptionist. The device registry (`add-kiosk-device-approval-and-traceability`) already gives us an approved, branch-bound kiosk identity carried in the `device-id` header, so a kiosk can be authorised by that identity instead of a login.

## What Changes

- Add a kiosk mirror of the staff badge APIs under `/api/v1/kiosk/checkin`, authenticated only by the `device-id` header (no bearer token, no login):
  - `GET  /kiosk/checkin/search`
  - `POST /kiosk/checkin/{visit_id}/verify-id`
  - `POST /kiosk/checkin/{visit_id}/photo`
  - `POST /kiosk/checkin/{visit_id}/badge` (first print, `Idempotency-Key`)
  - `GET  /kiosk/checkin/{visit_id}/badge?reason=` (reprint)
- A new `require_kiosk_device` dependency: the header is **required**, and the device must exist, be `approved`, be enabled, and have `operating_mode = kiosk`. Failures share one `403` so device ids cannot be enumerated.
- Scope comes from the device, not a user: a kiosk only sees and acts on visits in its registered branch (and building when location enforcement is on), and only for today.
- Kiosk search is **narrower than staff search**: exact `trackingId` or numeric check-in code only (no name or partial phone), returning a minimal response with no contact details. This is the main hardening because `device-id` is a static identifier, not a secret.
- Kiosk routes reuse `checkin/service.py` (print gate, token issue, PDF render, reprint). No second implementation of the gate or the token.
- Record the device on what the kiosk does: `badge_prints.printed_by_device_id` (and `printed_by_user_id` becomes nullable), `invitations.id_verified_by_device_id`. Every action is audited with the device as actor.
- Same two flags as the staff flow (`BADGE_PRINT_FLOW_ENABLED` and the tenant toggle); kiosk endpoints return `404` when off. Rate-limited per IP and per device (`KIOSK_BADGE_RATE_LIMIT`, new setting).
- Existing staff `/checkin/*` endpoints are **not changed**.

## Capabilities

### New Capabilities
- `kiosk-badge-print-flow`: device-authenticated search, ID confirmation, photo capture, badge print and reprint for kiosks, with narrowed search, device-derived scope, device traceability and rate limits.

### Modified Capabilities
- `devices`: a new "usable kiosk device" resolution (required header, `operating_mode = kiosk`) alongside the existing optional `device-id` dependency.

## Impact

- Code: new `src/vmss_api/checkin/kiosk_router.py`, `kiosk_schemas.py`; small additions to `checkin/service.py` and `checkin/repository.py` (device actor, exact-match search); `devices/deps.py` (required-kiosk dependency); `core/config.py`, `.env.example`; `api.py`, `main.py` `_TAGS_METADATA` (`kiosk-checkin`), docs test.
- DB: one tenant Alembic revision: `badge_prints.printed_by_device_id` (FK `devices.id`, nullable), `printed_by_user_id` made nullable, `invitations.id_verified_by_device_id` (nullable). Additive; no backfill.
- API: additive only under `/api/v1/kiosk`; no breaking change.
- Docs: `docs/features/checkin_badge.md` (kiosk section), `configuration.md`.
- Frontend: Flutter kiosk app sends `device-id` and calls the new routes.
- Out of scope: kiosk check-in/out by badge scan (already unauthenticated at `/checkin/badge/*`), device registration/approval, and physical printer integration.

## Open items to confirm before apply

- Kiosk "verify ID" is self-attested by the visitor (no human checks it). Confirm whether that satisfies the print gate or whether kiosk printing needs a stricter rule (design.md Decision 5).
- `device-id` alone is a weak credential (see design.md Risks). Confirm that is acceptable or add a per-device secret.
- Should a kiosk be allowed to reprint? Reprint kills the previous QR; a visitor could invalidate someone else's badge if they know the visit.
