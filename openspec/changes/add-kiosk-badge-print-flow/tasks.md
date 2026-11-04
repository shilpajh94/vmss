## 1. Device auth, config, scaffold

- [x] 1.1 Add `require_kiosk_device` to `devices/deps.py` (required header, approved + enabled + `operating_mode == "kiosk"`, single generic `403`, `WARNING` log without visitor data); keep `make_device_dependency` unchanged
- [x] 1.2 Add `kiosk_badge_rate_limit` (`KIOSK_BADGE_RATE_LIMIT`) to `core/config.py`, `.env.example` (placeholder value, not `.env`) and `docs/features/configuration.md`; rate-limit key = device id when resolved, else IP
- [x] 1.3 Scaffold `checkin/kiosk_router.py` (`/kiosk/checkin`, tag `kiosk-checkin`) and `checkin/kiosk_schemas.py`; register in `api.py`, add a `kiosk-checkin` entry to `_TAGS_METADATA` in `main.py`; confirm `tests/test_api_documentation.py` passes
- [x] 1.4 Apply `require_badge_print_flow` and the tenant session via `track_default_tenant_db` on every kiosk route

## 2. Data model and service changes

- [x] 2.1 Tenant Alembic revision: `badge_prints.printed_by_device_id` (FK `devices.id`, nullable), check constraint "at most one of user/device" (`printed_by_user_id` was already nullable), `invitations.id_verified_by_device_id` (FK, nullable); downgrade included
- [x] 2.2 Update `BadgePrint`/`Invitation` models and `checkin/repository.py`; add exact-match lookup (`tracking_id` or `checkin_code`, branch + today filter) with no `LIKE`
- [x] 2.3 Let `checkin/service.py` print/reprint/verify-id accept an actor that is a `User` or a `Device`; keep the gate and token code single-sourced; confirm staff behaviour is byte-identical
- [x] 2.4 Add a device scope helper: visit branch equals device branch, visit date is today in tenant timezone, and `check_device_location` when enforcement is on; out-of-scope returns `404`

## 3. Kiosk endpoints

- [x] 3.1 `GET /kiosk/checkin/search?q=` exact match only, returns one `KioskVisitOut` (no phone/email/ID URLs), `404` when none, query never logged in full
- [x] 3.2 `POST /kiosk/checkin/{visit_id}/verify-id` (idempotent, records `id_verified_by_device_id`)
- [x] 3.3 `POST /kiosk/checkin/{visit_id}/photo` (JPEG/PNG, size cap, content validation, `409 photo_already_captured`)
- [x] 3.4 `POST /kiosk/checkin/{visit_id}/badge` with `Idempotency-Key` keyed on the device, returns badge card data, `409` on gate failure or active badge
- [x] 3.5 `GET /kiosk/checkin/{visit_id}/badge?reason=` mandatory reason, `no-store`, one transaction, `409` if never printed
- [x] 3.6 Every route: `response_model=Envelope[...]`, `-> JSONResponse`, `success_response`/`error_response`, audit via `record_audit_log` in `BackgroundTasks` (actor none, device id in diff, `kiosk_`-prefixed actions)

## 4. Tests and docs

- [x] 4.1 Tests: flag off (global, tenant) returns `404`; existing staff `/checkin/*` unchanged and still `401` without a token
- [x] 4.2 Tests (permission-denied equivalent): missing header, unknown, pending, disabled, deleted and `security`-mode device all return the same `403`
- [x] 4.3 Tests: scope (other branch `404`, not-today visit `404`, building mismatch with enforcement on/off)
- [x] 4.4 Tests: search exact code works, name/partial phone `404`, response has no contact fields, rate limit `429`
- [x] 4.5 Tests: gate failures list all unmet conditions, idempotent print creates one row with `printed_by_device_id`, reprint kills the old token, blank reason, reprint before first print
- [x] 4.6 Tests: tenant isolation with a second tenant schema (device and visit from another tenant are not reachable)
- [x] 4.7 Update `docs/features/checkin_badge.md` with a kiosk section (endpoints, header, scope, flags, config, limitations)
- [x] 4.8 Run `ruff check`, `ruff format --check`, `mypy` on `core/`, `checkin/`, `devices/`, and the targeted pytest set: `checkin` tests, `devices` tests, invitations check-in tests (shared service code), `tests/test_api_documentation.py`, `tests/test_security_config.py`, tenant-migration tests (per `testing-standards.md` §5, not the full suite)
