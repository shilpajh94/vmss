## Context

- A visit is an `Invitation` row (`status`, `check_in_status`, `branch_id`, `expires_at`, `approved_at`, `preferred_visit_date/time`, `watchlist_flagged` + override fields). Visitor types are `VisitorCategory` rows.
- Org structure already has `Branch`, `Building`, `Floor` in `org_structure/models.py`. A gate is **not** a `SecurityGate` row: it is a `Device` (`devices/models.py`) with `operating_mode = security` and a `branch_id`.
- Badge QR: `checkin/badge_token.py` verifies a signed, day-bound token (`visit_id`, `tenant_id`, `day`, `jti`); `checkin/service.py::resolve_active_badge` checks the jti is active and the day is today. Existing scans are unauthenticated and rate-limited with `limiter.limit(settings.badge_scan_rate_limit)`.
- Audit uses `record_audit_log` via `BackgroundTasks`; push alerts use `notifications/service.py::notify_role_at_branch`.
- There is no blacklist table, no `emergency` package, and no zones.
- Tenant tables inherit `Base`; new tables go in `alembic_tenant/`.

## Goals / Non-Goals

**Goals:**
- Reception defines who may enter which zone when registering/inviting; the badge QR enforces it.
- One pure, exhaustively testable decision function with explicit reasons.
- Entry/exit log that powers the inside-by-zone report and the timeline.
- Fully inert while the tenant's `zone_access_enabled` toggle is off.

**Non-Goals:** hardware integration, overstay, anti-passback, blacklist matching, changing existing badge endpoints.

## Decisions

**1. Toggle (per tenant, not an env var).** `tenants.zone_access_enabled boolean not null default false`, a global-schema column added by a global migration, mirroring `badge_print_flow_enabled`. It is copied into `TenantContext` by `get_tenant`, switched by `PATCH /tenants/me/settings` (`tenants:update`, audited with before/after) and reported by `GET /tenants/me` as `zoneAccessEnabled`. A router-level dependency `require_zone_access_enabled(tenant)` returns 404 (not 403) when off, so the feature is indistinguishable from absent; a missing permission stays 403. Applied to the access_control and emergency routes; the timeline's `include_zones` follows the caller's toggle. Chosen over an env var so each tenant opts in from Organisation Configs without a deploy; the env var and its `settings` field were removed.

**2. Data model (tenant schema).**
- `zones`: `id`, `branch_id` FK, `building_id` FK null, `floor_id` FK null, `name`, `code`, `description`, `is_active`, `deleted_at`, timestamps. Partial unique `(branch_id, code) WHERE deleted_at IS NULL`.
- `zone_gates`: `zone_id` FK, `gate_id` FK `devices.id` (a security-mode device), composite PK. A gate may serve several zones; a zone may have several gates.
- `visitor_category_zones`: `category_id`, `zone_id`, composite PK (defaults).
- `invitation_zones`: `invitation_id` FK cascade, `zone_id`, `assigned_by_user_id`, `created_at`, composite PK (reception's explicit mapping).
- `zone_access_events` (append-only, `created_at` only): `id`, `invitation_id`, `zone_id`, `gate_id` (device id), `direction` (`entry|exit`), `decision` (`allowed|denied`), `reason` (null when allowed), `scanned_by_user_id`, `occurred_at`. Indexes `(invitation_id, occurred_at)`, `(zone_id, occurred_at)`.
Zone, gate device, building and floor must share the zone's `branch_id`, and a gate must be a live `operating_mode = security` device; the service enforces it, FKs cannot. Approval/active state of the device is not checked. Revised from `security_gates` by migration `d3a7c9e1b5f2` (existing links cleared; `zone_access_events` keeps its rows and gets the new FK `NOT VALID`).

**3. Effective allowed zones.** If the invitation has any `invitation_zones` rows, those are the allowed set; otherwise the visitor category's defaults; otherwise empty (default deny). Per-invitation replaces defaults, not unions with them, so reception can narrow as well as widen. Resolved in one repository query (`WHERE invitation_id = :id`, falling back to one category query), never per zone.

**4. `can_enter(visit, zone, gate, now) -> AccessDecision`.** Pure function in `access_control/decision.py` over already-loaded data (visit, zone, allowed-zone ids, `zone_gate` link, active-badge flag). No I/O, so the matrix is table-driven in tests. `AccessDecision(allowed: bool, reason: DenyReason | None)`. Checks run in fixed order and return the first failure:
1. `zone_inactive` (zone deleted/inactive, or zone not in the visit's branch)
2. `gate_not_linked` (gate is not in `zone_gates` for the zone)
3. `not_checked_in` (`check_in_status != checked_in`; status `checked_out`/`denied`/`archived` also fail here)
4. `not_approved` (status is `pending`, `submitted` or `denied`; `approved_at` is not used because walk-ins and pre-approved visits may not set it)
5. `blacklisted` (`watchlist_flagged` and no `watchlist_override_at`)
6. `outside_time_window` (past `expires_at`, or the tenant-local date is before `preferred_visit_date`; the badge's own same-day check in `resolve_active_badge` already bounds the other side)
7. `zone_not_allowed` (zone not in the effective allowed set)
Order puts cheap structural failures first and the most security-relevant reason (`blacklisted`) ahead of the generic `zone_not_allowed`, so an alert names the real cause. Reason strings are the stable enum values; the client message is generic.

**5. Gate scan endpoint.** `POST /api/v1/access/scan` body `{token, gateId, zoneId, direction}`; `require_permission("access:scan")`; tenant from the JWT, and the badge token's `tenant_id` must equal it (else the generic invalid-token `400`, same as `invalid_token()`). `access:scan` is checked against the visit's branch (`user.has_permission(..., branch_id=visit.branch_id)`) after the token resolves, because roles are branch-scoped; the route dependency only requires the grant at any branch. Reuses `verify_badge_token` and `resolve_active_badge` (token valid, jti active, day is today). Rate limited with a new `settings.zone_scan_rate_limit`, keyed by IP + endpoint like the badge scans. Accepts `Idempotency-Key` (`api-conventions.md` §3) so a retried scan does not log twice. Response: `{allowed, reason, visitorName?}` — no PII beyond a display name needed by the guard; no token echoed. Chosen over making it unauthenticated like `/badge/check-in` because `gateId`/`zoneId` come from the caller.

**6. Exit.** `direction=exit` skips `can_enter`, is always allowed, and is logged. An exit with no open entry is still logged (idempotent, no error). The "currently in zone" state is derived from the latest event per (visit, zone), not stored.

**7. Denied entry.** On deny: (a) `logger.warning("zone_entry_denied", tenant_id, user_id, invitation_id, zone_id, gate_id, reason)` — no token, no ID numbers; (b) `zone_access_events` row; (c) audit `zone_entry_denied` via `BackgroundTasks` + `record_audit_log`; (d) push to the Security role at the visit's branch via `notify_role_at_branch`, enqueued (never inline), deduplicated per (visit, zone, reason) for a short window with `core/notification_dedupe.py` so a guard re-scanning does not spam. The push body names the zone and reason code, not the visitor's identity. Allowed entries/exits write the event row and an INFO log only; the audit entry is for denials and for zone admin changes, to avoid one audit row per door pass (events table already is the ledger).

**8. Who's inside by zone (`emergency/`).** `GET /api/v1/emergency/inside` returns zones with their current occupants and an `unzoned` bucket for checked-in visitors currently in no zone. Occupancy per zone = visits whose latest event for that zone is an allowed `entry`, and whose `check_in_status` is still `checked_in`. One SQL query using `DISTINCT ON (invitation_id, zone_id) ... ORDER BY occurred_at DESC`, joined to invitations and zones, paginated by zone; no per-visit queries. Permission `emergency:view`, branch-scoped to the caller's allowed branches (`org_structure/deps.py::get_branch_context`). Output exposes name, host, badge number — not contact or ID details.

**9. Timeline.** Add `zone_entered`, `zone_exited`, `zone_entry_denied` to `TimelineEventType` and a fourth `UNION ALL` branch over `zone_access_events` in the timeline repository. Depends on `add-visit-timeline` being merged first; if it is not, this task is deferred and nothing else here blocks on it.

**10. Permissions.** `zones:manage` (CRUD + mapping defaults), `zones:view`, `access:scan`, `emergency:view`; per-invitation mapping reuses `invitations:edit`, which reception already holds, so reception needs no new grant to map zones. Zone CRUD checks `zones:manage` at the zone's branch. Tenant migration grants to existing roles (same pattern as earlier `grant_*` migrations).

**11. Layering and docs.** Router → service → repository; repository is the only `AsyncSession` user. Routes declare `response_model=Envelope[...]`, `-> JSONResponse`, `success_response`. Schemas extend `CamelModel`, free text has `max_length`. Routers registered in `api.py`, tags `access_control` and `emergency` added to `_TAGS_METADATA`; `tests/test_api_documentation.py` must pass.

**12. Front-desk check-in as a zone entry (revision).** The public QR / code check-in has no zone or gate in its request, so the zone comes from the calling device: `device-id` header -> a live `operating_mode = security` device linked to **exactly one** live, active zone. With the tenant toggle on, `access_control/checkin_gate.py::enforce_checkin_zone` runs inside `_check_in_resolved` after the usual eligibility, watchlist, date and expiry checks and before the check-in commits. `can_enter` is evaluated against the visit as it will stand once checked in (so the door-scan-only `not_checked_in` rule cannot fire). Allowed: an `entry` event is staged in the same transaction as the check-in. Denied: a `denied` event plus a `zone_entry_denied` audit row are committed, Security is alerted (same deduplicated push), and the check-in is rejected with 403 `Zone entry denied`; the visit stays unchecked in. A device that is absent, not in security mode, or linked to zero or several zones is not tied to one zone: behavior is unchanged and nothing is logged. The tracking-ID check-in path and check-out are not changed. Unlike the door scan, audit and the alert run inline here (the denial path only, enqueue-only) because this path has no background-task hook.

## Risks / Trade-offs

- **Default deny** may surprise sites that enable the flag before mapping zones → documented; flag defaults off; the guard sees reason `zone_not_allowed`.
- **Latest-event occupancy** is wrong if a guard forgets to scan exit → mitigated by the `check_in_status` filter (a checked-out visit is never "inside") and by logging that exit is not enforced.
- **Gate clock/offline scanning** is not supported; scans are online only.
- **Two sources of "inside"** (`insideNow` dashboard count vs. the zone report) can differ → the zone report's "no zone logged" bucket reconciles them.
- **Timeline coupling** to an unmerged change → isolated to one task, skippable.
- **Alert fatigue** → dedupe window; reason codes only.
