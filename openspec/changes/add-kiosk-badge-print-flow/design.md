## Context

- Staff badge flow lives in `checkin/router.py`: search, verify-id, photo, print (POST), reprint (GET), all behind `require_badge_print_flow` and `require_branch_scope("visitors:print_badge")` / `authorize_branch_id_tolerant(user, ...)`. Business logic is in `checkin/service.py` and `checkin/repository.py`.
- Devices exist (`devices/`): `Device` has `device_id`, `branch_id`, `building_id`, `operating_mode` (`kiosk`|`security`), `approval_status`, `is_active`. `devices/deps.py::make_device_dependency` builds an **optional** `device-id` header dependency; `service.resolve_usable_device` returns `403 Device is not authorized` for unknown/unapproved/disabled devices with one shared message.
- Public (no-token) routes get their tenant from `invitations/deps.py::track_default_tenant_db` (single configured default tenant; a known limitation). Scan endpoints under `/checkin/badge/*` take the tenant from a verified token claim.
- `get_enforce_location_validation` / `check_device_location` already compare a device's branch/building to an invitation.
- `Idempotency` dependency, `record_audit_log` via `BackgroundTasks`, slowapi `limiter` are the project norms.

## Goals / Non-Goals

**Goals:**
- Same capabilities as the staff flow for an approved kiosk, with no token or login.
- Reuse the existing service layer so the print gate and badge token stay single-sourced.
- Keep PII exposure to an unauthenticated caller as small as possible.

**Non-Goals:**
- No change to staff endpoints, device registration/approval, or badge scan endpoints.
- No per-device secrets or mTLS in this change (called out as a risk).
- No printer spooling; the response is card data for the kiosk app to print.

## Decisions

**1. Separate router, `/kiosk/checkin`.** A new `checkin/kiosk_router.py` with prefix `/kiosk/checkin`, tag `kiosk-checkin`. Keeping it apart from the staff router means no route can accidentally lose its auth dependency, and the staff router stays untouched. Registered in `api.py`, `_TAGS_METADATA`, and covered by `test_every_feature_router_is_registered_in_api_router`.

**2. `require_kiosk_device` dependency.** In `devices/deps.py`: reads the `device-id` header (required; missing -> `403`, same message as an unusable device so absence is not distinguishable), resolves via `service.resolve_usable_device`, then additionally requires `operating_mode == "kiosk"`. A security-gate device calling a kiosk route gets the same `403`. Uses `track_default_tenant_db` for the tenant session, like the other public routes. Every rejection logs `device_not_authorized` at `WARNING` (no token/ID values).

**3. Scope from the device.** There is no user, so `BranchScope` and `authorize_branch_id_tolerant` do not apply. Instead the kiosk may only touch a visit where `visit.branch_id == device.branch_id`, and, when `get_enforce_location_validation` is on, `check_device_location` passes. A visit outside scope returns `404` (not `403`) so a kiosk cannot probe other branches. Visits are also limited to today's visit date in the tenant timezone.

**4. Narrow kiosk search.** `GET /kiosk/checkin/search?q=` accepts only an exact `trackingId` or the numeric check-in code, never name or phone fragments. The response is a new `KioskVisitOut` (id, status, visitor first name only plus a masked display, whether photo/ID/active badge exist, what the gate still needs) and omits phone, email, ID document URLs and host details. Reasons: the caller is unauthenticated, so a partial-name search would let anyone holding a device id enumerate visitors. Pagination is dropped; at most one row can match an exact code, so the response is a single object or `404`. A per-IP and per-device rate limit slows code guessing.

**5. Kiosk verify-id is device-attested.** `POST /kiosk/checkin/{visit_id}/verify-id` records `id_verified_at` and the new `id_verified_by_device_id` (instead of `id_verified_by_user_id`). The visitor presents the ID to the kiosk (scan/photo handled by the existing document path); no human confirms it. Idempotent like the staff version. This weakens the meaning of "ID verified" and is listed as an open item.

**5a. Gate unchanged.** `service.print_badge` still requires `approved`/`checked_in`, a photo and verified ID, and returns `409` listing every unmet condition. The kiosk gets the same code path, so a rule change applies to both.

**6. Photo upload.** Same handler logic via `service.attach_photo`: JPEG/PNG only, size limit `invitation_max_photo_size_bytes`, read one byte past the limit, `409 photo_already_captured`, content validated by decoding (per `file-upload-handling.md`).

**7. Print and reprint.** `POST /kiosk/checkin/{visit_id}/badge` with `Idempotency-Key`, keyed on `(tenant, key, device pk)` as the caller. `GET .../badge?reason=` mirrors staff reprint (state-changing GET, `no-store`, mandatory reason), kept for parity as requested. The service functions take an actor argument that is either a `User` or a `Device`; `badge_prints.printed_by_user_id` becomes nullable and `printed_by_device_id` is added, with a check constraint that at most one of the two is set (`printed_by_user_id` was already nullable).

**8. Audit.** `record_audit_log(actor_user_id=None, ..., diff={"device_id": device.device_id})` for verify, photo, print and reprint, using the existing action names with a `kiosk_` prefix (`kiosk_badge_printed`, etc.). No tokens, ID numbers or query text.

**9. Flags and limits.** Same `require_badge_print_flow` (404 when off). New `KIOSK_BADGE_RATE_LIMIT` (default conservative, e.g. `30/minute`), key function = device id when valid else IP; added to `config.py`, `.env.example` (placeholder) and `docs/features/configuration.md`.

**10. Permissions.** None. Authorisation is device approval plus `operating_mode`. No new RBAC code. (Tenant admins already control which devices are approved/enabled.)

## Risks / Trade-offs

- [`device-id` is a static header, not a secret; anyone who learns it can act as that kiosk] -> Narrow exact-match search, minimal response, branch/day scope, rate limits, admin can disable a device instantly. Recommend a follow-up with a per-device secret or signed device token. Flagged for the user.
- [Visitor-triggered reprint can invalidate a valid badge] -> Reason is mandatory and audited; consider disallowing kiosk reprint (open item).
- [Self-attested ID verification] -> Device recorded on the row; open item on whether to require reception for kiosks.
- [Default-tenant resolution] -> Same known limitation as other public routes; replace when real tenant routing exists.
- [State-changing GET reprint] -> Same as staff flow; `no-store`.
- [Check constraint on `badge_prints` actor] -> Additive migration; "at most one" (not "exactly one") so any legacy row with no actor still satisfies it.

## Migration Plan

1. Deploy the tenant migration (additive columns + check constraint) with the flow flag unchanged.
2. Deploy code; kiosk routes are live only where the flag is on.
3. Register and approve a kiosk device, then test in staging.
4. Rollback: turn the flag off (routes return `404`); the migration downgrade drops the new columns and restores `NOT NULL` only if no device-printed rows exist.

## Open Questions

- See the proposal's open items (self-attested ID, device-id strength, kiosk reprint).
- Should kiosk search also accept a full phone number, given OTP/SMS check-in codes already cover the same case?
