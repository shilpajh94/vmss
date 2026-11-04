## Why

The backend is adding zone-based access control: sites are split into zones (optionally tied to a building, floor and gates), each visit is allowed into a set of zones, and guards scan badges at zone gates. The portal has no way to define zones, say which zones a visit may enter, or see who is inside which zone during an emergency. Without this, the backend's default is "every zone denied" and staff cannot fix it.

## What Changes

- Add a **Zones** admin screen (list, create, edit, delete) with the fields `branchId`, `name`, `code`, `buildingId?`, `floorId?`, `gateIds?`. The branch is read-only on edit.
- Add **category default zones** to the visitor-category add/edit page (`GET/PUT /visitor-categories/{id}/zones`).
- Add a **zone picker** on a visit (`GET/PUT /invitations/{id}/zones`) that replaces the whole set, with a visible "no zones mapped, every zone is denied" warning when neither the visit nor its category has any mapping.
- After the reception flow creates or registers a visit, call `PUT /invitations/{id}/zones` (zones are not part of the invitation-create payload).
- Add an **inside-by-zone** view backed by `GET /emergency/inside` (zones, `unzoned`, `totalInside`; unpaginated).
- Show the new timeline events `zone_entered`, `zone_exited` and `zone_entry_denied` in the visit timeline panel.
- **Feature gate**: all zone UI is hidden when `GET /zones` returns 404 (the tenant's zone access setting is off). That setting is the per-tenant `zoneAccessEnabled` flag, not an env var, so Organisation Configs gets a "Zone Access Control" toggle (`GET /tenants/me`, `PATCH /tenants/me/settings`).
- Permissions: `zones:view`, `zones:manage`, `emergency:view`, plus the existing `invitations:edit`. Add them to `PAGE_PERMISSIONS` / the fallback role table.

Out of scope: the Flutter guard app's scan screen (`POST /access/scan`, idempotency, denial messages, push alerts). It lives in a separate codebase. This change only confirms that `GET /zones` returns `gateIds`, which the guard app needs.

## Capabilities

### New Capabilities
- `admin-zones`: zone register at `/admin/zones` with CRUD, filters, sorting, pagination and the 404 feature gate.
- `visit-zone-access`: the per-visit zone picker, the empty-mapping warning, the post-registration zone call, and the zone timeline events.
- `emergency-inside-by-zone`: the inside-by-zone report grouped by zone, with an unzoned group and a total.

### Modified Capabilities
- `admin-visitor-categories`: the Add/Edit Category page gains a default-zones section.
- `admin-organisation-configs`: gains the zone access control switch.

## Impact

- New: zone schemas under `src/domain/entities/`; repository ports and use cases under `src/data/`; infrastructure adapters; `API_ENDPOINTS` entries; `AppDependencies` wiring in `src/composition-root.ts`.
- New pages and hooks for zones and the inside report; a shared zone-picker component.
- Changed: `src/presentation/route-permissions.ts`, `src/presentation/utils/permissions.ts`, `src/App.tsx` routes, admin sidebar, `visit-timeline-schema.ts` (known event types), `VisitTimeline.tsx` labels, the visitor-category form, the staff visitor-registration flow, and the invitation detail view.
- Depends on the tenant's zone access setting being on and the proposed role grants (`zones:manage`: Admin; `zones:view` and `emergency:view`: Admin, Reception, Security).
- No new third-party dependencies.
