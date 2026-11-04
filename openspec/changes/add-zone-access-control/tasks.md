## 1. Config and scaffold (3.1)

- [x] 1.1 Add the per-tenant `zone_access_enabled` toggle (`Tenant` column + global migration `c8e2a5b7d9f1`, `TenantContext`, `PATCH /tenants/me/settings`, `TenantOut`); add `zone_scan_rate_limit` and `zone_denial_alert_dedupe_seconds` to `core/config.py` and `.env.example` (never stage `.env`). **Changed from the original plan:** no `ZONE_ACCESS_ENABLED` env variable
- [x] 1.2 Scaffold `src/vmss_api/access_control/` (`__init__`, `router`, `service`, `schemas`, `models`, `repository`) and `src/vmss_api/emergency/` (`__init__`, `router`, `service`, `schemas`, `repository`)
- [x] 1.3 Register both routers in `api.py`, add `access_control` and `emergency` entries to `_TAGS_METADATA` in `main.py`, and add `require_zone_access_enabled` (404 when the tenant's toggle is off) as a router dependency
- [x] 1.4 Add permissions `zones:manage`, `zones:view`, `access:scan`, `emergency:view` to `auth/rbac_catalog.py` with the default grants

## 2. Models and migration (3.2)

- [x] 2.1 Add models `Zone`, `ZoneGate`, `VisitorCategoryZone`, `InvitationZone`, `ZoneAccessEvent` (`Mapped[...]` style, `Base`, soft delete on `zones`, `created_at` only on the event table)
- [x] 2.2 Add one tenant migration in `alembic_tenant/versions/` creating the tables, partial unique `(branch_id, code)`, event indexes, and permission grants to existing roles, with downgrade
- [x] 2.3 Confirm the migration applies on a fresh tenant schema and on an existing one (tenant migration check)

## 3. Zone CRUD (3.3)

- [x] 3.1 Add schemas (`ZoneCreate`, `ZoneUpdate`, `ZoneOut`; `max_length` on text) and paginated/filterable list (`branchId`, `isActive`, whitelisted sort)
- [x] 3.2 Add `ZoneRepository` and service: create/get/list/update/soft-delete, same-branch checks for building/floor/gate links, 409 on duplicate code
- [x] 3.3 Add routes under `require_permission("zones:manage")` (read under `zones:view`) with `response_model=Envelope[...]`/`PaginatedEnvelope[...]` and `-> JSONResponse`; write audit entries for create/update/delete

## 4. Allowed-zone mapping (3.4)

- [x] 4.1 Add category default endpoints (set/get zones for a visitor category) under `zones:manage`
- [x] 4.2 Add per-invitation zone mapping via `GET`/`PUT /invitations/{id}/zones`, validated against the invitation's branch, reusing reception's existing `invitations:edit` permission; one bulk write, not a loop. **Deviation:** `zoneIds` is not added to the multipart invitation-create / registration payloads (high-risk surface for little gain); reception calls the PUT right after creating the visit. Follow-up if the portal wants a single call.
- [x] 4.3 Add one repository method resolving the effective allowed zone ids (invitation set, else category default, else empty)

## 5. Entry decision (3.5)

- [x] 5.1 Add `access_control/decision.py` with `DenyReason` enum, `AccessDecision` and a pure `can_enter(...)` implementing the fixed check order
- [x] 5.2 Add the service loader that fetches visit, zone, gate link, active-badge flag and allowed ids in a constant number of queries and calls `can_enter` with tenant-timezone `now`

## 6. Gate scan (3.6)

- [x] 6.1 Add `POST /api/v1/access/scan` (`access:scan`, `@limiter.limit(settings.zone_scan_rate_limit)`, `Idempotency-Key` support): verify token, require token tenant == caller tenant, `resolve_active_badge`, then decision for entry or always-allow for exit
- [x] 6.2 Write the `zone_access_events` row for every scan; return `{allowed, reason, visitorName}` with a generic invalid-token response for every token failure
- [x] 6.3 Confirm the scan never echoes the token and logs no token, ID number or contact detail

## 7. Denied-entry handling (3.7)

- [x] 7.1 On deny: structlog WARNING with standard fields and reason; background audit `zone_entry_denied`
- [x] 7.2 Enqueue a deduplicated push to Security at the visit's branch via `notify_role_at_branch` (zone and reason code only, no visitor identity); log a WARNING when no holders exist
- [x] 7.3 Ensure notification and audit work never runs inline in the request

## 8. Emergency and timeline (3.8)

- [x] 8.1 Add `GET /api/v1/emergency/inside` (`emergency:view`, branch-scoped): single `DISTINCT ON` occupancy query grouped by zone plus the `unzoned` bucket (not paginated: an emergency list must be complete); PII limited to name, host, badge number
- [x] 8.2 `add-visit-timeline` is present in the tree, so: add `zone_entered`, `zone_exited`, `zone_entry_denied` event types and a fourth `UNION ALL` branch over `zone_access_events`; otherwise note the deferral in the completion note

## 9. Tests and docs (3.9)

- [x] 9.1 Allow/deny matrix: table-driven `can_enter` test covering every reason, check-order precedence, watchlist override, and the allowed case
- [x] 9.2 Mapping tests: invitation overrides category, category fallback, no mapping denies, cross-branch rejected
- [x] 9.3 Scan tests: allowed, denied, exit always allowed, invalid/expired/inactive/other-day/foreign-tenant token, idempotent retry, rate limit 429
- [x] 9.4 Denial side-effect tests: WARNING log, audit row, push enqueued once under dedupe, no-Security-holder path
- [x] 9.5 Permission-denied (403) for every new route, and happy path for each endpoint
- [x] 9.6 Tenant isolation with `make_tenant_schema`/`open_tenant_session`: zones, mappings, events and the inside report never cross tenants
- [x] 9.7 Toggle off (and on via the tenant settings PATCH, 403-not-404 for a missing permission): every new route returns 404 and existing badge endpoints are unchanged
- [x] 9.8 Inside report: occupancy rules, checked-out excluded, denied excluded, constant query count
- [x] 9.9 Write `docs/features/access_control.md` (purpose, endpoints, decision order and reasons, default-deny, flag and config knobs, limitations)
- [x] 9.10 Run targeted tests only (access_control, emergency, `auth` catalog, `checkin` if its service is touched, `tests/test_api_documentation.py`, tenant migration check, timeline if 8.2 done) as one sequential `ddev exec uv run pytest <paths>`; report modules run and dependents included

## 10. Gates are security devices (revision)

- [x] 10.1 Re-point `zone_gates.gate_id` and `zone_access_events.gate_id` to `devices.id` (migration `d3a7c9e1b5f2`, with downgrade); validate gates as live, same-branch, security-mode devices on zone create/update and on scan
- [x] 10.2 Update tests to security-mode devices; add tests for kiosk-mode and deleted devices (422 on link, 404 on scan) and that events carry the device id
- [x] 10.3 Update docs and artifacts

## 11. Zone entry at front-desk QR / code check-in (revision)

- [x] 11.1 `access_control/checkin_gate.py::enforce_checkin_zone`, called from `invitations/checkin.py::_check_in_resolved` (shared by `PATCH /api/v2/invitations/qr/{token}/check-in` and the check-in-code endpoint) when the tenant toggle is on: a check-in from a security device linked to exactly one live zone is judged by `can_enter` (evaluated as the visit will stand once checked in) and logged
- [x] 11.2 Allowed: stage an `entry` event in the check-in's own transaction. Denied: commit a `denied` event and an audit row, alert Security, and reject the check-in with 403 (visit stays unchecked in)
- [x] 11.3 No device, a non-security device, or a device linked to zero or several zones: unchanged behavior, nothing logged. Toggle off: unchanged. Repeat scan while checked in: no second event
- [x] 11.4 Tests (allowed, blocked, toggle off, not-tied-to-one-zone matrix, repeat scan) and docs

