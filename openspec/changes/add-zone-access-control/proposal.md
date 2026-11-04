## Why

Once a visitor is checked in at the front desk they can walk anywhere. Sites need to restrict visitors to specific areas (lab, server room, floor 3) and know who is where when something goes wrong. Today there are no zones, no per-area access decision, and the "who's inside" figure is a single branch-wide count.

This is parent task 3 (subtasks 3.1–3.9). The request adds one rule: **zones are mapped to a visit by reception at registration/invitation time, and the visitor's badge QR is what grants (or refuses) access at a zone gate.**

## What Changes

- Add a per-tenant `zone_access_enabled` toggle (default off, on `tenants`, switched with `PATCH /tenants/me/settings` like the badge print flow; no env variable) and an `access_control/` feature package registered in `api.py` and `_TAGS_METADATA`.
- Add `zones` (linked to branch, optional building/floor) and `zone_gates` (zone ↔ gate, where a gate is a registered security-mode `Device`, not a `SecurityGate` row) tables, with a tenant migration.
- Add zone CRUD under `zones:manage`, soft delete.
- Add allowed-zone mapping per visitor category (defaults) and per invitation (set by reception at registration/invitation, overrides the default), via two new join tables.
- Add `can_enter(visit, zone)`: a pure decision returning allow/deny plus a machine-readable reason (visit status, time window, approval, blacklist/watchlist, badge active, zone allowed).
- Add `POST /api/v1/access/scan`: gate scan using the existing signed badge QR token, rate-limited, writes an append-only entry/exit log (`zone_access_events`).
- Add denied-entry handling: WARNING log, audit entry, push alert to Security at the visit's branch (deduplicated).
- Add `emergency/` "who's inside" by zone, and zone entry/exit/denied events in the visit timeline.
- Add permissions `zones:manage`, `zones:view`, `access:scan`, `emergency:view`.
- Add tests (allow/deny matrix, permission-denied, tenant isolation, flag off) and `docs/features/access_control.md`.

Additive only. With the toggle off, nothing observable changes and the new routes return 404.

## Capabilities

### New Capabilities
- `zone-access-control`: zones, gate links, allowed-zone mapping, the `can_enter` decision, the gate scan endpoint, the entry/exit log, denied-entry handling, the per-tenant toggle.
- `emergency-inside-report`: who's inside grouped by zone, and zone events in the timeline.

### Modified Capabilities
- `auth`: four new permissions and their default role grants.
- `tenant` (settings): `PATCH /tenants/me/settings` accepts `zoneAccessEnabled`; `badgePrintFlowEnabled` becomes optional (each switch changes only when present); `TenantOut` exposes `zoneAccessEnabled`.

## Impact

- Code: new `src/vmss_api/access_control/` and `src/vmss_api/emergency/` packages; edits to `tenant/` (model, schemas, repository, router), `core/tenancy.py`, `api.py`, `main.py`, `auth/rbac_catalog.py`; a fourth branch in the timeline query (depends on `add-visit-timeline`).
- Database: a global migration adds `tenants.zone_access_enabled`; a tenant migration adds `zones`, `zone_gates`, `visitor_category_zones`, `invitation_zones`, `zone_access_events`, plus permission grants. No change to existing tables.
- API: new endpoints only. Additive.
- Config: `ZONE_SCAN_RATE_LIMIT`, `ZONE_DENIAL_ALERT_DEDUPE_SECONDS` (in `.env.example`). No on/off env variable: the switch is the per-tenant toggle.
- Docs: `docs/features/access_control.md`.
- Frontend (separate repos): portal zone admin, zone picker on invitation/registration, guard-app scan screen, inside-by-zone view.

## Out of scope

- RFID/biometric/turnstile hardware integration (gates are scanned by a guard app or kiosk calling the API).
- Automatic blacklist/watchlist matching. No blacklist table exists; only `invitations.watchlist_flagged` (+ override). `can_enter` reads that flag.
- Overstay detection and time-in-zone limits.
- Anti-passback and tailgating detection.
- Changing the existing `/badge/check-in|check-out|re-enter` endpoints.

## Gates are devices (revised)

The product has no `SecurityGate` records: a gate is a registered `Device` with `operating_mode = security` (the Security Gates page, `GET /devices`). So `zone_gates.gate_id`, `zone_access_events.gate_id`, a zone's `gateIds` and the scan's `gateId` are all **device ids** (`devices.id`, not the string `deviceId`). Linking requires a live (not deleted) security-mode device in the zone's branch. Migration `d3a7c9e1b5f2` re-points both FKs; existing gate links are cleared and ledger rows are kept.

## Assumptions (change if wrong)

- The request's closing line was garbled. Read as: *reception maps zones when registering/inviting the visitor, and access is granted through the badge QR.* Per-invitation mapping therefore wins over visitor-category defaults.
- **Default deny:** a visit with no allowed zones (neither per-invitation nor category default) is denied every zone.
- **Exit is never denied**, only logged, so nobody is "locked in" and the inside report stays accurate.
- The gate scan is called by authenticated staff/devices (`access:scan`), not anonymously. Unlike the existing badge scans, the caller names a gate and zone, so token-as-credential alone would let anyone claim a gate.
- The "who's inside" report does not exist yet as an endpoint (only a dashboard `insideNow` count), so `emergency/` is created here.

## Open items to confirm before apply

- Role grants: proposed `zones:manage` Admin; `zones:view` Admin, Reception, Security; `access:scan` Security; `emergency:view` Admin, Security, Reception.
- Whether reception may pick any zone at the branch or only zones the visitor category permits.
- Whether the scan caller must be a Security user or may also be a kiosk device token.
