## Why

Each branch can have a default zone (for example "Main Lobby") that the backend always adds to a visit's allowed zones at check time. A new visitor category should start with that zone ticked, so admins don't have to find and tick it for every category. Today the Add Category form has no zone checklist at all: `admin-visitor-category-form.tsx` renders `ZoneSetSection` only in edit mode, because the zone set is saved with its own `PUT /visitor-categories/{id}/zones` and a new category has no id yet.

## What Changes

- **Add Category form** gains a zone checklist, shown only when the zone feature is on and the user holds `zones:view`. It is held as local form state and saved after the category is created.
- **Pre-selection**: when the form opens, load the branch default with `GET /zones?isDefault=true&isActive=true` (the existing `isDefault` list filter). If a zone comes back, its id starts checked. If the list is empty, nothing is pre-checked. The admin can untick it.
- **Save**: create the category as today, then, if the user may manage zones, call `PUT /visitor-categories/{id}/zones` with `{ "zoneIds": [...] }` using the checked ids. The PUT replaces the whole set, and is skipped when nothing is checked.
- **Failure handling**: the category is already created when the zone PUT runs. A failed PUT keeps the category, shows a clear message, and sends the admin to the Edit page so they can retry (best-effort, as the Reception-workflow step is).
- **Unchanged**: the Edit Category checklist still shows only the explicitly saved zones from `GET /visitor-categories/{id}/zones`. Hiding the checklist when the zone feature is off is unchanged.

Access is not affected by unticking: the backend always adds the branch default zone at check time, whatever the category's saved list contains.

Assumption: the user wrote "the zone checklist on the create form" as if one existed. It does not, so this change adds one for create mode, reusing `ZonePicker`. If a different UI was intended, revisit this before applying.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `admin-visitor-categories`: zone checklist on the create form with the branch default pre-selected, saved after creation.

## Impact

- `src/presentation/pages/admin-visitor-categories/admin-visitor-category-form.tsx` (render a create-mode checklist).
- `src/presentation/pages/admin-visitor-categories/hooks/use-admin-visitor-category-form.ts` (zone draft state, default-zone load, post-create PUT).
- `src/presentation/hooks/use-zone-set.ts` and `src/presentation/components/zones/ZoneSetSection.tsx` only if the draft logic is shared rather than duplicated (see design).
- No new endpoints, schemas, ports, use cases or composition-root changes: `listZonesUseCase` (with `isDefault`) and `setCategoryZonesUseCase` already exist.
- Backend: none. Dev tenants need migration `e5b1a7c3d9f4` applied (done for `tenant_default`).
