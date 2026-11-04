## Context

Portal-only change; the Flutter guard app is a separate codebase and out of scope (see proposal.md). Follows `.claude/rules/data-api-layer.md` and the clean-architecture layering. Reusable pieces already exist: `ApiClient` merges extra headers (used for `X-Branch-ID`), endpoints use `:param` placeholders, paged responses reuse `PaginationMetaSchema`, `permissions.can(code, branchId?)` drives UI gating, and the visit timeline uses a string `eventType` with a known-types lookup and a generic fallback.

## Goals / Non-Goals

**Goals:** admin CRUD for zones, category default zones, a per-visit zone picker that makes "denied everywhere" obvious, an inside-by-zone emergency view, and zone timeline events, all hidden cleanly when the backend feature is off.

**Non-Goals:** the guard scan screen and push handling; changing the invitation-create payload; offline caching of zones; zone-level analytics.

## Decisions

- **Endpoints**: add `LIST_ZONES`, `CREATE_ZONE`, `GET_ZONE`, `UPDATE_ZONE`, `DELETE_ZONE`, `GET_CATEGORY_ZONES`, `SET_CATEGORY_ZONES` (PUT), `GET_INVITATION_ZONES`, `SET_INVITATION_ZONES` (PUT), `GET_EMERGENCY_INSIDE`, all `hasToken: true`. Endpoint paths are relative to `VITE_API_BASE_URL`, which already ends in `/api/v1`.
- **Schemas** (`src/domain/entities/zone-schema.ts`, `emergency-inside-schema.ts`): camelCase fields; zone `{id, branchId, name, code, buildingId, floorId, gateIds, isActive}` with nullable optionals. Mapping responses carry the zone ids. Inside report `{zones[{zoneId, zoneName, branchId, visitors[...]}], unzoned[], totalInside}`. Inside `enteredAt` stays a string.
- **Tenant switch**: the backend gates zones per tenant (`zoneAccessEnabled`, default off), not by env var. Organisation Configs gets a card using `GET /tenants/me` and `PATCH /tenants/me/settings` (`tenants:update`), mirroring the badge printing card; after a save it calls the feature gate's `recheck()` so navigation updates without a reload.
- **Feature gate**: one `ZoneFeatureProvider`/hook calls `GET /zones` once (page size 1, cached for the session) and exposes `enabled: boolean | 'unknown'`. A 404 `ApiError` sets it to `false`. Sidebar items, category section, visit picker, and the inside page read this. The Zones page itself reuses the result of its list call and shows nothing special on 404. Alternative considered: a separate feature-flags endpoint, rejected because the backend defines 404-on-`/zones` as the signal.
- **Ports/adapters/use cases**: `ZoneRepository` (list, get, create, update, delete, category get/set, invitation get/set) and `EmergencyInsideRepository`; one thin use case per operation family, wired lazily in `composition-root.ts` and exposed on `AppDependencies`.
- **Gates**: a zone's `gateIds` are the `id` (UUID, not the `deviceId` string) of registered devices with `operatingMode=security` from `GET /devices`, the same records the Security Gates page lists; the zone form and table read that list. The API rejects a device that is deleted, not in security mode, or outside the zone's branch with a 422. It does not check a device's approval or active status.
- **Branch scoping**: zone list passes `X-Branch-ID` via the existing header option when a branch is selected; `branchId` stays in the create body only. The edit form omits `branchId` from the PUT body.
- **Replace-set semantics**: category and visit mappings send the full `zoneIds` array. The picker holds a draft, diffs against the loaded set only to enable Save, and always PUTs the whole set. 422 is surfaced inline with the user's selection preserved.
- **Zone picker component**: shared `ZonePicker` (multi-select over zones of one branch, active zones first, inactive ones shown disabled) used by the category page, the visit detail, and the post-registration step. It takes `mode: 'edit' | 'readonly'` and an optional `fallbackZones` (category defaults) so it can render the "defaults apply" and "denied everywhere" states.
- **Effective zones for the warning**: when the visit's own set is empty, the visit view also loads its category's default zones (`GET_CATEGORY_ZONES`); if both are empty, show the denial warning. This needs `zones:view` only.
- **Post-registration zones**: the staff registration flow's success state offers a "Set zones" panel using the new visit id; the PUT happens only after creation succeeds. A failure there never rolls back the visit.
- **Permissions**: add `zones` (`zones:view`), `zonesManage`, and `emergencyInside` (`emergency:view`) to `PAGE_PERMISSIONS`; add `zones:view`/`emergency:view` to the Admin, Reception, Security fallback role grants and `zones:manage` to Admin only. `zones:manage` is added to `ADMIN_AREA_PERMISSIONS` so a manager can reach `/admin/zones`. Reception and Security (view only) reach the zone list read-only from a non-admin entry only if one exists; otherwise the list is admin-area only (open question below).
- **Routes**: `/admin/zones`, `/admin/zones/new`, `/admin/zones/:zoneId/edit`, and `/emergency/inside` (placed under the staff area so Reception and Security can open it).
- **Timeline**: append `zone_entered`, `zone_exited`, `zone_entry_denied` to `KNOWN_TIMELINE_EVENT_TYPES`, with labels and icons in `VisitTimeline.tsx`; denial uses the existing warning colour token.
- **Inside report refresh**: manual refresh button plus the existing live-data refresh interval if the app has one for similar pages; no pagination, render with a scrollable per-zone list.
- **Styling**: Tailwind v4 theme tokens only; icons through `src/assets/icons.ts`.

## Risks / Trade-offs

- [Gate relies on a 404 from `/zones`, which a missing permission could also confuse] → A 403 is treated as "no permission", not "feature off"; only 404 hides the UI.
- [Extra request on app start for the gate] → Single cached call, started only for users holding `zones:view`.
- [Role grants are proposals; `permissionCodes` may lack the new codes on older API builds] → Fallback table covers the proposed defaults; verify against the backend catalog.
- [Full emergency list can be large] → Plain list rendering with per-zone grouping; revisit virtualisation only if it proves slow.
- [Category defaults and visit mapping live in different screens, so users may not see why a visit is denied] → The visit picker shows effective zones and the denial warning.

## Open Questions

- Should Reception and Security (who hold `zones:view` but not `zones:manage`) get a read-only Zones list outside the admin area, or only the pickers? Default: pickers only, and the Zones page lives in the admin area.
