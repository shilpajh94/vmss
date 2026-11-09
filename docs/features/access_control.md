# Zone Access Control

Restricts a checked-in visitor to the areas (zones) reception allowed, decided
at a gate by scanning the visitor's badge QR. Also provides the "who's inside,
by zone" emergency view. **Off by default, per tenant**: until an admin turns the tenant's `zoneAccessEnabled`
toggle on, every route below is a `404` and no existing flow changes. There is no
environment variable for it.

## Concepts

- **Zone** — an area of one branch (optionally one building and floor), with
  one or more **gates** that give entry to it. A gate is a registered **device with
  `operatingMode=security`** (the Security Gates page, `GET /devices`); every
  `gateId`/`gateIds` below is that device's `id` (not its string `deviceId`). Soft-deleted, never hard-deleted.
- **Allowed zones** — set by reception per visit (`invitation_zones`), with
  per-visitor-category defaults (`visitor_category_zones`) as a fallback. A
  visit's own list **replaces** the category default; with neither, every zone
  is **denied** (default deny).
- **Default zone** — each branch may mark one active zone `isDefault`. It is
  **always added** to a visit's allowed zones, whether or not reception assigned
  anything, so a forgotten assignment never locks a visitor out of it (lobby,
  cafeteria). It is not a bypass: gate link, check-in, approval, blacklist and
  time-window checks still apply. Setting a new default clears the old one
  (audited as `zone_default_changed`); the default zone cannot be deleted or
  deactivated (409) until another is chosen or the flag is cleared. A branch with
  no default zone behaves as before.
- **Gate scan** — a Security user or guard app posts the badge QR token with the
  gate, zone and direction. Every scan is recorded in the append-only
  `zone_access_events` ledger.

## Endpoints (all under `/api/v1`)

| Method | Path | Permission | Description |
|---|---|---|---|
| POST | `/zones` | `zones:manage` at the branch | Create a zone (`branchId`, `name`, `code`, optional `buildingId`, `floorId`, `gateIds`, `isDefault`). |
| GET | `/zones` | `zones:view` | Paginated list; `isActive`, `isDefault`, `sortBy` (`name`/`created_at`), `sortOrder`; optional `X-Branch-ID`. |
| GET / PUT / DELETE | `/zones/{zoneId}` | `zones:view` / `zones:manage` | Read, update (branch is immutable; `isDefault` sets/clears the branch default), soft delete. |
| GET / PUT | `/visitor-categories/{id}/zones` | `zones:view` / `zones:manage` | Category default allowed zones. `PUT` replaces the whole set. |
| GET / PUT | `/invitations/{id}/zones` | `zones:view` / `invitations:edit` | Zones reception allows for this visit. `PUT {"zoneIds": [...]}` replaces the set; `[]` clears it so category defaults apply. Every zone must be in the invitation's branch. |
| POST | `/access/scan` | `access:scan` at the visit's branch | Body `{token, gateId, zoneId, direction}`; `direction` is `entry` or `exit`. Rate limited; accepts `Idempotency-Key`. |
| GET | `/emergency/inside` | `emergency:view` | Visitors currently inside, grouped by zone, plus `unzoned`. |

Scan response: `{allowed, reason, visitorName}`. The token is never echoed.
Any token problem (tampered, expired, inactive, another day, another tenant)
is one generic `400 Invalid badge token`.

## The entry decision

`access_control/decision.py::can_enter` is a pure function. Checks run in this
order and the first failure is the reason:

| # | Reason | Fails when |
|---|---|---|
| 1 | `zone_inactive` | zone soft-deleted, `is_active=false`, or not in the visit's branch |
| 2 | `gate_not_linked` | the scanned gate is not linked to the zone |
| 3 | `not_checked_in` | `check_in_status` is not `checked_in`, or status is `checked_out`/`archived` |
| 4 | `not_approved` | status is `pending`, `submitted` or `denied` |
| 5 | `blacklisted` | `watchlist_flagged` with no override recorded |
| 6 | `outside_time_window` | past `expires_at`, or before `preferred_visit_date` (tenant-local) |
| 7 | `zone_not_allowed` | zone not in the effective allowed set |

`blacklisted` reflects `invitations.watchlist_flagged`; no automatic
watchlist/blacklist matching exists yet, so it only fires when that flag has
been set. **Exit is never denied** — it is always allowed and logged, so nobody
is locked in and the inside report stays accurate.

## Front-desk check-in

`PATCH /api/v2/invitations/qr/{token}/check-in` (and the check-in-code endpoint,
which shares the same code path) is also a zone entry when the tenant toggle is
on **and** the request carries a `device-id` header for a security device linked
to exactly one zone. The visit is judged as it will stand once checked in:

- allowed: the visit is checked in and an `entry` event is logged for that zone
  (device as gate);
- not allowed: **403 `Zone entry denied`**, the visit is **not** checked in, and
  the denial is logged, audited and alerted to Security like a door-scan denial.

A request with no device, a non-security device, or a device linked to no zone or
to several zones behaves exactly as before and logs nothing. A repeat scan of an
already checked-in visit is still an idempotent no-op, but the device's zone is
re-judged against the visit's **current** allowed zones: allowed returns 200 and
logs nothing; no longer allowed returns **403 `Zone entry denied`** (denial
logged, audited and alerted) and the visit **stays checked in**. So a zone change
made after entry shows on the next scan, without a check-out first. Check-out and
the tracking-ID check-in are unchanged.

## Denied entry

Every denial: a `zone_entry_denied` WARNING (tenant, user, visit, zone, gate,
reason — no token, no ID numbers), an audit row `zone_entry_denied`, and a push
to the Security role at the visit's branch, deduplicated per visit/zone/reason
for `ZONE_DENIAL_ALERT_DEDUPE_SECONDS`. The push names the zone and reason code,
never the visitor. Audit and push run after the response, off the request path.
With no Security role or holder the denial still succeeds and a WARNING is logged.

## Who's inside

A visit is inside a zone when its latest **allowed** event for that zone is an
`entry` and the visit is still checked in. Denied scans neither add nor remove
occupancy. `unzoned` lists checked-in visits that are in no zone (never scanned,
or exited every zone), so `totalInside` reconciles with the dashboard `insideNow`.
The report is built in a constant number of queries and is not paginated (an
emergency list must be complete). Entries carry name, host and badge number only.
The report is scoped to branches where the caller holds `emergency:view`.

Zone scans also appear in the visit timeline as `zone_entered`, `zone_exited`
and `zone_entry_denied` (only while the toggle is on). Denied events read like
"Zone entry denied: Server Room (zone not permitted for this visitor)".

## Turning it on

`PATCH /api/v1/tenants/me/settings` with `{"zoneAccessEnabled": true}` (permission
`tenants:update`). Only the switches present in the body change, so
`badgePrintFlowEnabled` can be sent alone or together. `GET /api/v1/tenants/me`
returns `zoneAccessEnabled` (any role with `tenants:read`), which is the signal
clients should use to show or hide the zone UI. A missing permission is always
`403`, never `404`.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `ZONE_SCAN_RATE_LIMIT` | `60/minute` | Per-IP limit on `/access/scan`. |
| `ZONE_DENIAL_ALERT_DEDUPE_SECONDS` | `300` | Window in which repeat denials alert Security once. |

## Permissions

`zones:manage` (Admin), `zones:view` (Admin, Reception, Security), `access:scan`
(Admin, Security), `emergency:view` (Admin, Reception, Security). Granted to
existing tenants by migration `b9d4f1a6c3e8`.

## Limitations

- No RFID/biometric/turnstile integration; scans are online API calls.
- No anti-passback, tailgating detection or time-in-zone limits.
- Occupancy relies on guards scanning exit; the `check_in_status` filter keeps a
  checked-out visit from ever showing as inside.
- Zone mapping is set through `PUT /invitations/{id}/zones` (reception calls it
  right after creating/registering the visit); it is not yet a field on the
  invitation-create payload.
- The retention purge deletes a visit's `zone_access_events` with it (FK cascade).
