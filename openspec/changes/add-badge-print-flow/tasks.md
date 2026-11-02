## 1. Flags, tenant toggle, scaffold, permissions (iteration 1)

- [x] 1.1 Add `badge_print_flow_enabled` (`BADGE_PRINT_FLOW_ENABLED`, default `false`) and `badge_token_secret` to `core/config.py`; add both to `.env.example` with `_PLACEHOLDER_` values (not `.env`); document in `docs/features/configuration.md`
- [x] 1.2 Add `require_badge_print_flow` dependency in `core/deps.py` that returns `404` unless the global setting and the tenant toggle are both true; re-export it
- [x] 1.3 Add `badge_print_flow_enabled` (bool, `server_default false`) to `Tenant`, a global Alembic migration with downgrade, and expose it in `TenantOut`
- [x] 1.4 Add `PATCH /tenants/me/settings` (`tenants:update`, `response_model=Envelope[TenantOut]`, audited) and update `docs/features/tenant.md`
- [x] 1.5 Add `visitors:print_badge` (Reception, Admin) and `tenants:update` (Admin) to `auth/rbac_catalog.py`, plus a tenant migration granting them to existing roles
- [x] 1.6 Scaffold `src/vmss_api/checkin/` (`__init__`, `router`, `service`, `schemas`, `models`, `repository`); register in `api.py`, add a `checkin` entry to `_TAGS_METADATA` in `main.py`, and confirm `tests/test_api_documentation.py` passes
- [x] 1.7 Add `GET /checkin/search` (`q`, pagination, branch-scoped, read-only) matching name, digits-only phone, `tracking_id` and `checkin_code`; mask phones in logs

## 2. Gate, storage, token, renderer (iteration 2)

- [x] 2.1 Add tenant migration: `id_verified_at`, `id_verified_by_user_id` on `invitations` (nullable)
- [x] 2.2 Add `POST /checkin/{visit_id}/verify-id` (idempotent, audited)
- [x] 2.3 Implement the print gate in `checkin/service.py`: status `approved`/`checked_in`, photo present, ID verified; `409` lists all unmet conditions
- [x] 2.4 Add `BadgePrint` model and tenant migration for `badge_prints` (append-only, unique `jti`, partial unique index on `visit_id` where `active`, downgrade)
- [x] 2.5 Add `checkin/badge_token.py`: issue and verify PyJWT badge tokens (`sub`, `tid`, `day` in tenant timezone, `jti`, `exp`, `typ`); one generic invalid-token failure
- [x] 2.6 Add `checkin/badge_pdf.py`: compose name, host, photo, date, QR with Pillow and save as PDF via `anyio.to_thread.run_sync`; confirm the existing `invitations/badge.py` is not modified

## 3. Endpoints, audit, notification (iteration 3)

- [x] 3.1 Add `POST /checkin/{visit_id}/badge`: permission, flag dependency, gate, `Idempotency-Key`, returns `application/pdf`, `409` if an active badge exists, OpenAPI documented (`responses=` for the PDF media type)
- [x] 3.2 Add `GET /checkin/{visit_id}/badge?reason=`: required reason, deactivate old `jti` and insert the new row in one transaction, `Cache-Control: no-store`, `409` if never printed
- [x] 3.3 Audit every print and reprint with `record_audit_log` via `BackgroundTasks` (no token or ID numbers in the entry or logs)
- [x] 3.4 Approved (email only, SMS untouched): `invitations/tasks.py` adds `badge_flow_enabled` to the approval email context only when the flow is on, and `visit_confirmation.html/.txt` render a "Please bring your ID" callout behind it; flag-off output is byte-identical to before (verified against `HEAD` templates)

## 4. Scan flows, tests, docs (iteration 4)

- [x] 4.1 Add `POST /checkin/badge/check-out`: token in body, tenant from verified token claim, closes the visit through the existing checkout transition, deactivates the `jti`, rate-limited, audited
- [x] 4.2 Add `POST /checkin/badge/re-enter`: same-day only, active `jti` only, rate-limited, audited
- [x] 4.3 Tests: flag off (global, tenant) returns `404` and existing endpoints/messages unchanged
- [x] 4.4 Tests: permission-denied (Host/Security) on search, verify-id, print, reprint; `tenants:update` denied for Reception
- [x] 4.5 Tests: tenant isolation (search and token verification with a second tenant schema)
- [x] 4.6 Tests: gate (missing photo, unverified ID, wrong status), reprint invalidates the old QR, reprint without reason, reprint before first print
- [x] 4.7 Tests: idempotency (same key returns same result, one `badge_prints` row), expired token, wrong-day token, tampered token, timezone day boundary
- [x] 4.8 Tests: scan checkout closes the visit and kills the token, token reuse rejected, rate-limit `429`
- [x] 4.9 Add `docs/features/checkin_badge.md` (purpose, endpoints, flags, config, reprint policy)
- [x] 4.10 Run `ruff check`, `ruff format --check`, `mypy` on `core/`, `checkin/`, `auth/`, and the targeted pytest set: `checkin` tests, `tenant` tests, `auth` tests, `notifications` and invitations notification tests, `tests/test_api_documentation.py`, `tests/test_security_config.py`, tenant-migration tests (per `testing-standards.md` §5, not the full suite)
