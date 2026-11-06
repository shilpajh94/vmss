## Context

Follows `.claude/rules/data-api-layer.md`. The zone stack already exists (see the `add-zone-access-control` change): `ZoneSchema`, `ZoneRepository` port, `HttpZoneRepository`, zone use cases, `useAdminZones`, `useAdminZoneForm`, `ZonePicker`, `ZoneSetSection`, `useZoneSet`. This change extends them; it adds no endpoints and no wiring.

## Goals / Non-Goals

**Goals:** let admins manage a branch default zone; make visit pickers and warnings truthful about the default; handle the new 409/422/403 cases.

**Non-Goals:** guard-app behaviour; category default-zone picker changes; migration.

## Decisions

- **Schema tolerance**: `isDefault: z.boolean().default(false)` on `ZoneSchema`, mirroring how `isActive` is declared. The backend is undeployed, so a response without the field must still parse. `ZoneInput` gains `isDefault?: boolean`.
- **Update semantics**: `PUT /zones/{id}` treats `isDefault` as optional. The zone form always sends the current toggle value on edit and on create, so toggling off on the current default clears it. Moving the default to another zone needs no client-side clearing; the backend does it. After saving, lists reload, so the old default's badge disappears.
- **Filter**: add `isDefault?: boolean` to `ListZonesParams`, forwarded as a query param (`ApiClient` already drops `undefined`). The admin filter panel gets a "Default zone" select (All / Default / Not default).
- **Zone form toggle**: a `ToggleSwitch` row "Default zone" beside Zone Status, helper text "Always allowed for every visitor at this branch. Only one per branch; turning it on moves it from the current default. Still needs a linked gate." Shown on create and edit. Disabled when the zone is inactive (matches the 422 rule; avoids a guaranteed failure). Deactivating a zone whose toggle is on is blocked client-side with the same message the backend gives, and also handled if the backend returns 409 anyway. Visible only to users who can reach the form (`zones:manage`).
- **Error mapping**: a small helper in the zones presentation code maps `ApiError` status 409 to "Choose another default zone first." (used for delete in `useAdminZones` and save in `useAdminZoneForm`). 422 and 403 keep going through `toUserMessage`, which already surfaces the backend message or a fallback.
- **Table**: show a "Default" badge next to the zone name; no new column.
- **Visit picker**: `useZoneSet` already loads the branch's zones for an invitation scope (`listZonesUseCase` with `branchId`, all pages). The default zone is derived from that list (`zone.isDefault && zone.isActive`), so no extra request is needed even though the backend supports `?isDefault=true`. This avoids a second round trip and keeps data consistent with the picker's list. `ZonePicker` renders the default zone in `edit` and `readonly` modes as a non-interactive "Always allowed" chip, excluded from selectable checkboxes and from `draft`/`savedIds`, so it never appears in the PUT body. For a category scope (spans branches) no chip is shown.
- **Warning logic**: `deniesEverything` becomes false when the visit scope has an active default zone; instead of the red "denied" notice, show an info notice "Only the branch default zone is allowed for this visit." when the effective set is empty. The "category defaults apply" notice is unchanged.
- **Clear button**: "Clear (use category defaults)" keeps its meaning; the default zone is unaffected.

## Risks / Trade-offs

- Backend not deployed: `isDefault` is absent, so everything renders as before (no badge, no chip, toggle sends `isDefault: false`). A backend that rejects an unknown field would fail zone saves before deploy; mitigation is to merge this change after the backend deploys, as the backend note already says.
- Disabling the toggle on inactive zones and blocking deactivation client-side duplicates backend rules; the backend remains authoritative and its 409/422 are still handled.
- Deriving the default from the picker list depends on the list including inactive zones (it does) and on the branch having under the fetched total; `fetchAllPages` already covers all pages.
